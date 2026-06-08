"""
Google Ads API KPI Source — Stage 5.

설계:
- google-ads-python SDK 사용 (`from google.ads.googleads.client import GoogleAdsClient`)
- 인증: .secrets/google_ads.yaml (refresh token 보관)
- 쿼리: GAQL via SearchStream (단일 호출, 페이지 토큰 불필요)
- Entity: ad_group_ad_asset_view (UAC/App Campaign + 일반 캠페인 모두 호환)
  · pepp-us 진단(2026-06-05) 결과: 전 캠페인 MULTI_CHANNEL(UAC)이며 ad_group_ad.ad.name 은
    공란이고 asset.name 에 GDrive 폴더명과 동일 컨벤션이 들어있음 (예:
    `251104_BNR_L-Character-Keyart01A-DA_V_1200x1500_EN.png`).
  · 따라서 매칭 키는 ad.name 이 아닌 **asset.name** 이어야 함.
- 호출 패턴: 타이틀당 1회 batch (asset.name IN(...) 절로 필터링, 50개씩 청크 분할)
- asset.type 필터: IMAGE / YOUTUBE_VIDEO 만 (TEXT 등 비-소재 asset 제외)

레퍼런스:
- GAQL: https://developers.google.com/google-ads/api/docs/query/overview
- ad_group_ad_asset_view: https://developers.google.com/google-ads/api/fields/v20/ad_group_ad_asset_view
- AssetType: https://developers.google.com/google-ads/api/reference/rpc/v20/AssetTypeEnum.AssetType
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Optional, Sequence

from .base import AuthError, KpiSource, QuotaError
from ..schemas import CreativeKpiDaily

# google-ads SDK는 늦은 import (테스트·healthcheck 환경에서 미설치 시 우회)
try:
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException
    _SDK_AVAILABLE = True
except ImportError:
    GoogleAdsClient = None  # type: ignore
    GoogleAdsException = Exception  # type: ignore
    _SDK_AVAILABLE = False


# ─────────────────────────────────────────────────────────────
# 상수
# ─────────────────────────────────────────────────────────────
API_VERSION = "v20"  # SDK v31 기본
CREATIVE_NAMES_CHUNK_SIZE = 50  # GAQL IN(...) 절 제한 회피
COST_MICROS_PER_UNIT = 1_000_000  # 1 currency unit (KRW 등) = 1,000,000 micros

# UAC/Display/Search 모두에서 소재로 매칭 가능한 asset type만 수집.
# (TEXT, CALL_TO_ACTION 등 비-시각 asset은 GDrive 소재와 1:1 대응이 없어 제외)
SUPPORTED_ASSET_TYPES = ("IMAGE", "YOUTUBE_VIDEO", "MEDIA_BUNDLE")


# ─────────────────────────────────────────────────────────────
# 1. Source 구현
# ─────────────────────────────────────────────────────────────
class GoogleAdsKpiSource(KpiSource):
    """Google Ads API에서 ad_group_ad 단위 일별 KPI 조회."""

    def __init__(self, client: "GoogleAdsClient", login_customer_id: Optional[str] = None):
        """
        Args:
            client: 사전 인증된 GoogleAdsClient 인스턴스
            login_customer_id: MCC ID (10자리, 하이픈 없이). None이면 client 설정 사용.
        """
        if not _SDK_AVAILABLE:
            raise RuntimeError(
                "google-ads SDK가 설치되어 있지 않습니다. "
                "requirements.txt를 확인하고 'pip install google-ads' 실행하세요."
            )
        self.client = client
        self.login_customer_id = login_customer_id or client.login_customer_id

    # ── 팩토리 ──
    @classmethod
    def from_env(cls) -> "GoogleAdsKpiSource":
        """환경변수 + .secrets/google_ads.yaml 기반 자동 초기화.

        필요 환경 변수:
            GOOGLE_ADS_CONFIG_PATH=.secrets/google_ads.yaml
        """
        config_path = os.environ.get("GOOGLE_ADS_CONFIG_PATH", ".secrets/google_ads.yaml")
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(
                f"Google Ads 설정 파일 없음: {config_path}\n"
                f"scripts/setup-google-ads.ps1 을 실행하여 발급하거나, "
                f".env 의 GOOGLE_ADS_CONFIG_PATH 경로를 확인하세요."
            )

        if not _SDK_AVAILABLE:
            raise RuntimeError("google-ads SDK 미설치")

        try:
            client = GoogleAdsClient.load_from_storage(str(config_path))
        except Exception as e:
            raise AuthError(
                f"Google Ads SDK 설정 로드 실패 ({config_path}): {e}\n"
                f"YAML 형식 또는 refresh_token 유효성을 확인하세요."
            )

        return cls(client=client)

    # ── KpiSource 인터페이스 구현 ──
    def source_name(self) -> str:
        return "google_ads"

    def auth_check(self) -> bool:
        """LIMIT 1 cheap call로 인증 검증.

        login_customer_id로 LIST_ACCESSIBLE_CUSTOMERS 호출 — 가장 가벼움.
        """
        if not self.login_customer_id:
            print(
                "[google_ads.auth_check] login_customer_id 미설정",
                file=sys.stderr,
            )
            return False

        try:
            service = self.client.get_service("CustomerService")
            accessible = service.list_accessible_customers()
            resource_names = list(accessible.resource_names)
            print(
                f"[google_ads.auth_check] OK — {len(resource_names)}개 accessible customer "
                f"(MCC={self.login_customer_id})",
                file=sys.stderr,
            )
            return True
        except GoogleAdsException as e:
            err_msg = self._format_googleads_exception(e)
            print(f"[google_ads.auth_check] FAIL: {err_msg}", file=sys.stderr)
            return False
        except Exception as e:
            print(f"[google_ads.auth_check] FAIL: {type(e).__name__}: {e}", file=sys.stderr)
            return False

    def fetch_window(
        self,
        customer_id: str,
        start: date,
        end: date,
        creative_names: Optional[Sequence[str]] = None,
        campaign_filter: Optional[Sequence[str]] = None,
    ) -> Iterable[CreativeKpiDaily]:
        """28일 등 윈도우 일별 KPI를 SearchStream으로 fetch.

        creative_names가 50개 초과면 청크 분할 후 합쳐서 반환.
        """
        if not customer_id:
            raise ValueError("customer_id is required")
        customer_id = str(customer_id).replace("-", "").strip()

        # 청크 분할 (소재 IN 절이 너무 길면 GAQL 한도 초과)
        chunks: list[Optional[Sequence[str]]] = []
        if creative_names:
            names_list = list(creative_names)
            for i in range(0, len(names_list), CREATIVE_NAMES_CHUNK_SIZE):
                chunks.append(names_list[i : i + CREATIVE_NAMES_CHUNK_SIZE])
        else:
            chunks.append(None)  # 전체 조회

        # 일자·소재별 합산용 dict (같은 (creative_name, date)가 여러 AdGroup에서
        # 등장할 수 있어 합산이 필요)
        agg: dict[tuple[str, str], CreativeKpiDaily] = {}

        ga_service = self.client.get_service("GoogleAdsService")

        # Stage 5-D: 4-key agg — 같은 소재가 N개 캠페인에서 운영되면 N개 row 분리 보존.
        # key = (creative_name, campaign_name, ad_group_name, date_str)
        # 변경 전(2-key): 캠페인 cross-합산 → UI 단일 캠페인 값과 일치 안 함
        # 변경 후(4-key): 캠페인별 분리 → 대시보드에서 캠페인 필터링 가능, CSV 행 단위와 일치

        for chunk in chunks:
            query = self._build_gaql(start, end, chunk, campaign_filter)
            try:
                stream = ga_service.search_stream(customer_id=customer_id, query=query)
                for batch in stream:
                    for row in batch.results:
                        # creative_name 결정 — VIDEO asset은 asset.name 공란이므로 youtube_video_title fallback.
                        # 이전 코드는 if not asset_name: continue 로 VIDEO 100% 누락하던 버그 해결.
                        creative_name = self._resolve_creative_name(row)
                        if not creative_name:
                            continue
                        date_str = row.segments.date
                        campaign_name = row.campaign.name or ""
                        ad_group_name = row.ad_group.name or ""
                        key = (creative_name, campaign_name, ad_group_name, date_str)
                        existing = agg.get(key)
                        new_daily = self._row_to_daily(row, customer_id, creative_name)
                        if existing is None:
                            agg[key] = new_daily
                        else:
                            existing.impressions += new_daily.impressions
                            existing.clicks += new_daily.clicks
                            existing.cost_micros += new_daily.cost_micros
                            existing.cost += new_daily.cost
                            existing.conversions += new_daily.conversions
                            existing.conversions_value += new_daily.conversions_value
            except GoogleAdsException as e:
                err_msg = self._format_googleads_exception(e)
                if self._is_auth_error(e):
                    raise AuthError(err_msg)
                if self._is_quota_error(e):
                    raise QuotaError(err_msg)
                raise RuntimeError(err_msg)

        return list(agg.values())

    # ── 내부 헬퍼 ──
    @staticmethod
    def _build_gaql(
        start: date,
        end: date,
        creative_names_chunk: Optional[Sequence[str]],
        campaign_filter: Optional[Sequence[str]],
    ) -> str:
        """GAQL 쿼리 빌더 — 외부 의존성 없이 호출 가능 (테스트 용이).

        ad_group_ad_asset_view 사용:
        - UAC(App Campaign)에서 ad.name 이 공란이고 asset.name 만 의미있음
        - 일반 Search/Display 캠페인에서도 asset 단위 metric을 제공
        - asset.type 을 IMAGE/YOUTUBE_VIDEO/MEDIA_BUNDLE 로 제한해 텍스트 asset 제외

        Stage 5-D 변경:
        - YOUTUBE_VIDEO asset은 asset.name이 공란이고 youtube_video_asset.youtube_video_title 에
          실제 파일명 컨벤션이 들어있음 → 매칭 키 필터링 시 asset.name IN(...) 만으로는 누락됨.
          청크 필터는 UI 단위(파일명)이므로 video는 청크 매칭 시도하되 _row_to_daily에서 fallback.
        - IMAGE URL: image_asset.full_size.url + width/height_pixels
        - YOUTUBE URL: youtube_video_asset.youtube_video_id → https://www.youtube.com/watch?v={id}
        - campaign.name, ad_group.name 도 SELECT 에 명시 (4-key agg용)
        """

        def _quote_csv(items: Sequence[str]) -> str:
            # asset.name에 작은따옴표가 들어있을 수 있어 백슬래시 이스케이프
            return ", ".join("'" + x.replace("'", "\\'") + "'" for x in items)

        asset_types_csv = ", ".join(f"'{t}'" for t in SUPPORTED_ASSET_TYPES)
        where_clauses = [
            f"segments.date BETWEEN '{start.isoformat()}' AND '{end.isoformat()}'",
            "ad_group_ad.status != 'REMOVED'",
            f"asset.type IN ({asset_types_csv})",
        ]
        if campaign_filter:
            where_clauses.append(f"campaign.name IN ({_quote_csv(campaign_filter)})")
        if creative_names_chunk:
            # YOUTUBE asset은 asset.name 공란이고 youtube_video_title에 파일명 들어있어 OR 매칭.
            # IMAGE asset은 asset.name과 youtube_video_title 모두 잡힐 수 있어 OR로 wide coverage.
            names_csv = _quote_csv(creative_names_chunk)
            where_clauses.append(
                f"(asset.name IN ({names_csv}) OR asset.youtube_video_asset.youtube_video_title IN ({names_csv}))"
            )

        query = f"""
            SELECT
              segments.date,
              asset.name,
              asset.type,
              asset.image_asset.full_size.url,
              asset.image_asset.full_size.width_pixels,
              asset.image_asset.full_size.height_pixels,
              asset.youtube_video_asset.youtube_video_id,
              asset.youtube_video_asset.youtube_video_title,
              ad_group.name,
              ad_group.id,
              campaign.name,
              campaign.id,
              metrics.impressions,
              metrics.clicks,
              metrics.cost_micros,
              metrics.conversions,
              metrics.conversions_value
            FROM ad_group_ad_asset_view
            WHERE {' AND '.join(where_clauses)}
        """
        return " ".join(query.split())  # 줄바꿈·들여쓰기 normalize

    @staticmethod
    def _resolve_creative_name(row) -> str:
        """asset type별 적절한 식별자 추출.

        - IMAGE/MEDIA_BUNDLE: asset.name (예: 251104_BNR_*_L_1200x628_EN.jpg)
        - YOUTUBE_VIDEO: asset.name 공란이므로 youtube_video_asset.youtube_video_title fallback
                         (예: 251104_VID_A-Character-Combat01A-UA_L_1920x1080_EN)
        - 둘 다 비어있으면 "" 반환 → fetch_window에서 skip
        """
        if row.asset.name:
            return row.asset.name
        # YOUTUBE_VIDEO fallback
        try:
            yt_title = row.asset.youtube_video_asset.youtube_video_title
            if yt_title:
                return yt_title
        except Exception:
            pass
        return ""

    @staticmethod
    def _resolve_asset_url(row, asset_type_name: str) -> Optional[str]:
        """asset type별 미리보기 URL.

        - IMAGE: image_asset.full_size.url (예: https://tpc.googlesyndication.com/simgad/...)
        - YOUTUBE_VIDEO: https://www.youtube.com/watch?v={youtube_video_id}
        - MEDIA_BUNDLE/기타: None
        """
        try:
            if asset_type_name == "IMAGE":
                url = row.asset.image_asset.full_size.url
                return url or None
            if asset_type_name == "YOUTUBE_VIDEO":
                vid = row.asset.youtube_video_asset.youtube_video_id
                if vid:
                    return f"https://www.youtube.com/watch?v={vid}"
        except Exception:
            pass
        return None

    @staticmethod
    def _row_to_daily(row, customer_id: str, creative_name: str) -> CreativeKpiDaily:
        """SearchStream row → CreativeKpiDaily 변환.

        Stage 5-D: campaign_name, ad_group_name, asset_url, asset_type 추가 주입.
        creative_name은 호출자가 _resolve_creative_name으로 미리 결정해 전달 (VIDEO fallback 처리).
        """
        cost_micros = int(row.metrics.cost_micros)
        asset_type_name = row.asset.type_.name
        asset_url = GoogleAdsKpiSource._resolve_asset_url(row, asset_type_name)
        return CreativeKpiDaily(
            creative_name=creative_name,
            date=row.segments.date,
            source="google_ads",
            customer_id=customer_id,
            campaign_name=row.campaign.name or "",
            ad_group_name=row.ad_group.name or "",
            asset_url=asset_url,
            asset_type=asset_type_name,
            impressions=int(row.metrics.impressions),
            clicks=int(row.metrics.clicks),
            cost_micros=cost_micros,
            cost=cost_micros / COST_MICROS_PER_UNIT,
            conversions=float(row.metrics.conversions),
            conversions_value=float(row.metrics.conversions_value),
        )

    @staticmethod
    def _format_googleads_exception(e: "GoogleAdsException") -> str:
        """GoogleAdsException → 사람이 읽기 좋은 한 줄 메시지."""
        try:
            status = e.error.code().name if hasattr(e, "error") else "?"
            errors = []
            for err in e.failure.errors:
                code = err.error_code
                if hasattr(code, "DESCRIPTOR"):
                    detail = err.message
                else:
                    detail = str(err.message)
                errors.append(detail[:200])
            return f"GoogleAdsException [{status}]: {'; '.join(errors)}"
        except Exception:
            return f"GoogleAdsException: {e}"

    @staticmethod
    def _is_auth_error(e: "GoogleAdsException") -> bool:
        """401/403/invalid_grant 등 인증 실패 판별."""
        try:
            for err in e.failure.errors:
                msg = str(err.message).lower()
                if any(s in msg for s in ("invalid_grant", "unauthenticated", "permission_denied", "authentication")):
                    return True
        except Exception:
            pass
        return False

    @staticmethod
    def _is_quota_error(e: "GoogleAdsException") -> bool:
        """RESOURCE_EXHAUSTED 판별."""
        try:
            for err in e.failure.errors:
                msg = str(err.message).lower()
                if any(s in msg for s in ("quota", "resource_exhausted", "rate_limit")):
                    return True
        except Exception:
            pass
        return False


# ─────────────────────────────────────────────────────────────
# 2. Helpers — 외부에서 호출 가능
# ─────────────────────────────────────────────────────────────
def default_window(days: int = 28) -> tuple[date, date]:
    """기본 KPI 윈도우: 어제 - (days-1) ~ 어제.

    Args:
        days: 윈도우 길이 (기본 28일).

    Returns:
        (start, end) — YYYY-MM-DD ISO.
    """
    end = date.today() - timedelta(days=1)  # 어제까지 (오늘 데이터는 미확정)
    start = end - timedelta(days=days - 1)
    return start, end
