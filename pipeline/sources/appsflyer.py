# -*- coding: utf-8 -*-
"""AppsFlyer MMP Source — Stage 7 (두 번째 MMP 프로바이더).

Airbridge 와 동일 계약: fetch_mmp_window(start, end, exclude) -> list[CreativeMmpDaily].
데이터 = Master API(master-agg-data/v4, GET CSV): af_ad×pid×c×install_time 로
impressions·clicks·cost·installs·revenue·retention_day_1(D1 잔존수). install_time=설치일별
코호트 분해. Master API 날짜 범위 1~31일(공식 문서) → ≤31일 청크. 파서(extract_master/
parse_master_rows)는 HTTP 무의존 — 단위테스트. 라이브 검증 확정(2026-06-26 Starseed JP): 실제 CSV
헤더는 Ad/Media Source/Campaign/Install Time/Impressions/Clicks/Installs/Cost/Revenue/Retention Day 1.

D7 매출(revenue_d7) — Cohort API 로 교체(Airbridge 코호트 지표와 같은 기준):
  Master API 의 revenue 는 LTV 누적이고, Master 코호트 KPI 는 af_ad(광고) 그룹을 지원하지 않음(공식
  문서 그룹핑 표) → 소재 단위 D7 은 Cohort API(POST cohorts/v1)로만 가능.
  · 같은 단위(af_ad×pid×c×설치일)로 받아 Master 행의 revenue_d7 만 교체(행 매칭은 기존 그대로).
  · 설치일(Day 0)~Day 7 누적 인앱 매출(revenue_type=regular). partial_data=true 로 받아
    Day 7 이내 값이 있는 가장 마지막 날 누적값 사용(설치 8일 미만은 차오르는 중인 값 — Airbridge 와 동일).
  · Cohort 실패·형식 불일치·매칭 0건이면 Master 값 유지 + revenue_source='master_fallback'(실행 미중단).
  ⚠️ Cohort 응답 CSV 열 이름은 공식 문서에 없음 → extract_cohort_revenue 가 여러 형태를 수용.
     첫 라이브 호출로 실제 헤더 확인 후 COHORT_KEY_MAP·_rev_day 확정 필요.
비용/노출 결측 행은 분모 가드가 '—' 처리. currency=USD 고정 후 usd_to_krw 로 환산.
"""
from __future__ import annotations

import csv
import io
import os
import re
from datetime import date, timedelta
from typing import Optional

import requests

from ..base_errors import AuthError, QuotaError
from ..schemas import CreativeMmpDaily

MASTER_BASE = "https://hq1.appsflyer.com/api/master-agg-data/v4/app"
COHORT_BASE = "https://hq1.appsflyer.com/api/cohorts/v1/data/app"
COHORT_MAX_DAY = 7   # D7 = Day 0(설치일)~Day 7 누적

# Google + 오가닉/내부 제외 (AppsFlyer media_source id 체계)
DEFAULT_EXCLUDE_MEDIA_SOURCES = {"googleadwords_int", "organic", "none", ""}

# Master API CSV 헤더 → 정규화 키 (라이브 검증 확정, 2026-06-26 Starseed JP). 소문자·strip 후 매칭.
# 실제 헤더: Ad, Media Source, Campaign, Install Time, Impressions, Clicks, Installs, Cost, Revenue, Retention Day 1
MASTER_HEADER_MAP = {
    "ad": "creative", "af_ad": "creative",
    "media source": "media_source", "pid": "media_source",
    "campaign": "campaign", "c": "campaign",
    "install time": "date", "date": "date",   # 날짜 grouping = install_time → 헤더 "Install Time"
    "impressions": "impressions",
    "clicks": "clicks",
    "installs": "installs",
    "cost": "cost", "total cost": "cost",
    "revenue": "revenue", "total revenue": "revenue",
    "retention day 1": "retained_d1",          # retention_day_1 kpi = D1 잔존수(count)
}

# Cohort API CSV 그룹 열 → 정규화 키 (미확정 — API 이름/표시 이름 모두 수용)
COHORT_KEY_MAP = {
    "af_ad": "creative", "ad": "creative",
    "pid": "media_source", "media source": "media_source", "media_source": "media_source",
    "c": "campaign", "campaign": "campaign",
    "date": "date", "install time": "date", "install date": "date", "install_date": "date",
    "conversion date": "date", "attribution date": "date",
    "period": "period", "day": "period", "cohort day": "period",
}


class CohortFormatError(ValueError):
    """Cohort 응답에서 D7 매출 열/행을 찾지 못함 → Master 값 유지."""


def _norm_header(h: str) -> str:
    key = (h or "").strip().lower()
    return MASTER_HEADER_MAP.get(key, key)


def _num(v) -> float:
    try:
        return float(str(v).replace(",", "").strip() or 0)
    except (ValueError, AttributeError):
        return 0.0


def _has_num(v) -> bool:
    s = str(v if v is not None else "").replace(",", "").strip()
    if not s or s.lower() in ("n/a", "na", "null", "none", "-"):
        return False
    try:
        float(s)
        return True
    except ValueError:
        return False


def mmp_key(creative: str, media_source: str, campaign: str, day: str) -> tuple:
    """Master·Cohort 행 매칭 키 — (광고, 매체(소문자), 캠페인, 설치일)."""
    return ((creative or "").strip(), (media_source or "").strip().lower(),
            (campaign or "").strip(), (day or "").strip()[:10])


def extract_master(csv_text: str) -> list[dict]:
    """Master API CSV → 정규화 dict 리스트.

    키: creative·media_source·campaign·date·impressions·clicks·installs·cost·revenue (문자열).
    """
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    if not rows:
        return []
    header = [_norm_header(h) for h in rows[0]]
    out: list[dict] = []
    for raw in rows[1:]:
        if not raw:
            continue
        rec = {header[i]: raw[i] for i in range(min(len(header), len(raw)))}
        out.append(rec)
    return out


def parse_master_rows(rows: list[dict], exclude: set, fx_rate: float = 1.0) -> list[CreativeMmpDaily]:
    """정규화 dict 리스트 → CreativeMmpDaily. 빈/None creative·제외 media_source skip.

    cost·revenue 에 fx_rate(USD→KRW) 적용. retained_d1 = Retention Day 1 kpi(count).
    revenue 는 LTV 누적 — Cohort D7 로 교체되기 전 임시값(교체 실패 시 그대로 유지).
    """
    out: list[CreativeMmpDaily] = []
    for r in rows:
        creative = (r.get("creative") or "").strip()
        ms = (r.get("media_source") or "").strip().lower()
        if not creative or creative.lower() == "none" or ms in exclude:
            continue
        out.append(CreativeMmpDaily(
            creative_name=creative,
            date=(r.get("date") or "").strip(),
            channel=ms,
            campaign_name=(r.get("campaign") or "").strip(),
            impressions=int(round(_num(r.get("impressions")))),
            clicks=int(round(_num(r.get("clicks")))),
            cost=int(round(_num(r.get("cost")) * fx_rate)),
            installs=int(round(_num(r.get("installs")))),
            retained_d1=int(round(_num(r.get("retained_d1")))),
            revenue_d7=int(round(_num(r.get("revenue")) * fx_rate)),
        ))
    return out


# ── Cohort API (D7 매출) ──────────────────────────────────────────────

def cohort_request_body(start: date, end: date, max_day: int = COHORT_MAX_DAY) -> dict:
    """Cohort API 요청 본문. Master 와 같은 단위·시간대·통화(UTC·USD 기본)로 맞춰 키가 어긋나지 않게."""
    return {
        "cohort_type": "user_acquisition",          # 신규 유저(리타겟팅 제외)
        "min_cohort_size": 1,
        "preferred_timezone": False,               # Master 요청과 동일(기본 시간대) — 설치일 키 일치
        "preferred_currency": False,               # USD → usd_to_krw 환산(Master 와 동일)
        "from": start.isoformat(), "to": end.isoformat(),
        "groupings": ["af_ad", "pid", "c", "date"],
        "kpis": ["revenue"],
        "aggregation_type": "cumulative",          # Day 0 부터 누적
        "partial_data": True,                       # 미완성 일자 포함 — false 면 청크 전체가 잘림(문서)
        "per_user": False,
        "filters": {"period": list(range(0, max_day + 1)), "revenue_type": ["regular"]},   # 인앱 구매만
    }


_DAY_RE = re.compile(r"(?:day|period|d)[\s_]*(\d{1,3})\b", re.I)


def _rev_day(header: str) -> Optional[int]:
    """와이드형 열 이름에서 '누적 매출 Day N' 이면 N, 아니면 None.

    예상 형태: revenue_sum_day_7 / Revenue Sum Day 7 / sum_revenue_day_7 / revenue_day_7 …
    (count·cvr·per user·event·users 열은 제외)
    """
    h = (header or "").strip().lower()
    if "revenue" not in h:
        return None
    if any(x in h for x in ("count", "cvr", "rate", "per user", "per_user", "users", "roas", "roi", "event")):
        return None
    m = _DAY_RE.search(h)
    return int(m.group(1)) if m else None


def extract_cohort_revenue(csv_text: str, max_day: int = COHORT_MAX_DAY) -> dict:
    """Cohort CSV → {mmp_key: Day≤max_day 중 값이 있는 마지막 날의 누적 매출(USD)}.

    와이드형(행=코호트, 열=Day 별 매출)과 롱형(period 열 + 매출 열) 모두 수용.
    매출 열을 찾지 못하면 CohortFormatError.
    """
    rows = list(csv.reader(io.StringIO(csv_text or "")))
    if not rows:
        return {}
    raw_header = rows[0]
    header = [COHORT_KEY_MAP.get(h.strip().lower(), h.strip().lower()) for h in raw_header]
    if "creative" not in header or "date" not in header:
        raise CohortFormatError(f"그룹 열(af_ad·date) 없음: {raw_header[:8]}")
    day_cols = {i: d for i, h in enumerate(raw_header) if (d := _rev_day(h)) is not None and d <= max_day}
    long_rev = [i for i, h in enumerate(raw_header) if "revenue" in h.lower() and _rev_day(h) is None
                and not any(x in h.lower() for x in ("count", "cvr", "users", "roas", "roi", "event"))]
    period_i = header.index("period") if "period" in header else None
    if not day_cols and not (period_i is not None and long_rev):
        raise CohortFormatError(f"D7 매출 열 없음: {raw_header}")

    best: dict = {}   # key → (day, value)
    for raw in rows[1:]:
        if not raw:
            continue
        rec = {header[i]: raw[i] for i in range(min(len(header), len(raw)))}
        key = mmp_key(rec.get("creative"), rec.get("media_source"), rec.get("campaign"), rec.get("date"))
        if not key[0] or key[0].lower() == "none":
            continue
        cands = []
        if day_cols:
            cands = [(d, _num(raw[i])) for i, d in day_cols.items() if i < len(raw) and _has_num(raw[i])]
        elif period_i is not None and period_i < len(raw) and _has_num(raw[period_i]):
            d = int(_num(raw[period_i]))
            if d <= max_day and long_rev[0] < len(raw) and _has_num(raw[long_rev[0]]):
                cands = [(d, _num(raw[long_rev[0]]))]
        for d, v in cands:
            if key not in best or d > best[key][0]:
                best[key] = (d, v)
    return {k: v for k, (_, v) in best.items()}


def _merge_rows(rows: list[CreativeMmpDaily]) -> list[CreativeMmpDaily]:
    """같은 키(광고·매체·캠페인·설치일) 행을 합산 — 앱이 여러 개(Android+iOS)일 때 소재 단위로 합침."""
    agg: dict = {}
    order: list = []
    fields = ("impressions", "clicks", "cost", "installs", "retained_d1", "revenue_d7", "conversions")
    for r in rows:
        k = mmp_key(r.creative_name, r.channel, r.campaign_name, str(r.date))
        if k not in agg:
            agg[k] = r.model_copy()
            order.append(k)
        else:
            a = agg[k]
            for f in fields:
                setattr(a, f, getattr(a, f) + getattr(r, f))
    return [agg[k] for k in order]


class AppsFlyerMmpSource:
    """AppsFlyer Master API(+Cohort API D7) 로 소재별 MMP 데이터 수집. (KpiSource ABC 미상속 — Airbridge 동일 정책)"""

    MAX_CHUNK_DAYS = 31  # Master·Cohort API 날짜 범위 1~31일(공식 문서)

    def __init__(self, token: str, app_id, usd_to_krw: float = 1.0,
                 session=None, request_timeout: float = 120.0,
                 exclude_media_sources: Optional[set] = None, cohort_d7: bool = False):
        # cohort_d7: 직접 생성 시 기본 꺼짐(테스트가 실수로 네트워크 호출하지 않게). 운영은 from_env 가 켬.
        self.token = token
        # app_id: 문자열(쉼표·줄바꿈 구분 허용) 또는 목록 — SB 처럼 Android+iOS 앱 여러 개
        if isinstance(app_id, (list, tuple)):
            ids = [str(a).strip() for a in app_id]
        else:
            ids = [s.strip() for s in re.split(r"[,\n]", str(app_id or ""))]
        self.app_ids = [a for a in ids if a]
        self.app_id = self.app_ids[0] if self.app_ids else ""
        self.usd_to_krw = float(usd_to_krw or 1.0)
        self.session = session or requests.Session()
        self.request_timeout = request_timeout
        self.exclude = {s.lower() for s in (exclude_media_sources or DEFAULT_EXCLUDE_MEDIA_SOURCES)}
        self.cohort_d7 = cohort_d7
        # QA P2-I: Master API(집계)는 Airbridge 류의 절단 신호(hasNext/limit)가 없어 항상 False
        #   유지 — 정확성은 ≤31일 청크 + 키 병합이 보장. (향후 행 cap 징후 확인되면 fetch 에서 True 세팅)
        self.last_fetch_truncated = False
        # D7 매출 출처 — metrics 로 노출(레포 결과 JSON 만 보고 성공 여부 확인)
        self.revenue_source = "master"          # cohort | master_fallback | master(코호트 비활성)
        self.revenue_fallback_reason = ""
        self.revenue_cohort_matched = 0

    @property
    def currency(self) -> str:
        return "KRW" if self.usd_to_krw and self.usd_to_krw != 1.0 else "USD"

    @classmethod
    def from_env(cls, app_id, usd_to_krw: float = 1.0,
                 exclude_media_sources: Optional[set] = None) -> "AppsFlyerMmpSource":
        token = os.environ.get("APPSFLYER_API_TOKEN", "").strip()
        if not token:
            raise FileNotFoundError(
                "APPSFLYER_API_TOKEN 미설정. .env 에 추가하세요 (AppsFlyer 대시보드 > API Token V2.0)."
            )
        if not app_id or (isinstance(app_id, (list, tuple)) and not any(str(a).strip() for a in app_id)):
            raise FileNotFoundError("AppsFlyer app_id 미설정 (등록부 'MMP 앱 식별자').")
        cohort = (os.environ.get("APPSFLYER_COHORT_D7", "1") or "1").strip() != "0"   # 비상시 끄기
        return cls(token=token, app_id=app_id, usd_to_krw=usd_to_krw,
                   exclude_media_sources=exclude_media_sources, cohort_d7=cohort)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}", "accept": "text/csv"}

    @staticmethod
    def _raise_classified(e: Exception, resp_obj=None):
        code = getattr(resp_obj, "status_code", None)
        msg = str(e).lower()
        if code in (401, 403) or "401" in msg or "403" in msg or "unauthorized" in msg:
            raise AuthError(f"AppsFlyer 인증 실패: {e}")
        if code == 429 or "429" in msg or "too many" in msg:
            raise QuotaError(f"AppsFlyer rate limit: {e}")
        raise RuntimeError(f"AppsFlyer HTTP 오류: {e}")

    def _fetch_master_csv(self, start: date, end: date, app_id: Optional[str] = None) -> str:
        """Master API GET → CSV 텍스트. (단위테스트에서 monkeypatch)"""
        url = f"{MASTER_BASE}/{app_id or self.app_id}"
        params = {
            "from": start.isoformat(), "to": end.isoformat(),
            "groupings": "af_ad,pid,c,install_time",   # install_time = 설치일별 코호트 분해
            "kpis": "impressions,clicks,installs,cost,revenue,retention_day_1",
            "currency": "USD",                          # cost·revenue USD 고정 → usd_to_krw 로 환산
            "format": "csv",
        }
        resp = None
        try:
            resp = self.session.get(url, headers=self._headers(), params=params,
                                    timeout=self.request_timeout)
            resp.raise_for_status()
        except Exception as e:
            self._raise_classified(e, resp_obj=resp)
        return resp.text

    def _fetch_cohort_csv(self, start: date, end: date, app_id: Optional[str] = None) -> str:
        """Cohort API POST → CSV 텍스트. (단위테스트에서 monkeypatch) — 토큰은 Master 와 동일."""
        url = f"{COHORT_BASE}/{app_id or self.app_id}"
        resp = None
        try:
            resp = self.session.post(url, headers=self._headers(), json=cohort_request_body(start, end),
                                     timeout=self.request_timeout)
            resp.raise_for_status()
        except Exception as e:
            self._raise_classified(e, resp_obj=resp)
        return resp.text

    def _chunks(self, start: date, end: date):
        cs = start
        while cs <= end:
            ce = min(cs + timedelta(days=self.MAX_CHUNK_DAYS - 1), end)
            yield cs, ce
            cs = ce + timedelta(days=1)

    def _apply_cohort_d7(self, app_id: str, rows: list[CreativeMmpDaily], start: date, end: date) -> int:
        """앱 하나의 Master 행 revenue_d7 을 Cohort D7 로 교체. 반환: 매칭된 행 수. 실패 시 예외."""
        rev: dict = {}
        for cs, ce in self._chunks(start, end):
            rev.update(extract_cohort_revenue(self._fetch_cohort_csv(cs, ce, app_id)))
        if rev and rows and not any(mmp_key(r.creative_name, r.channel, r.campaign_name, str(r.date)) in rev for r in rows):
            raise CohortFormatError(f"Cohort {len(rev)}행이 Master 행과 하나도 매칭되지 않음(키 형식 불일치)")
        matched = 0
        for r in rows:
            v = rev.get(mmp_key(r.creative_name, r.channel, r.campaign_name, str(r.date)))
            if v is not None:
                matched += 1
            r.revenue_d7 = int(round((v or 0.0) * self.usd_to_krw))   # Cohort 에 없음 = 그 기간 인앱 매출 0
        return matched

    def fetch_mmp_window(self, start: date, end: date,
                         exclude_channels: Optional[set] = None) -> list[CreativeMmpDaily]:
        """기간 내 Master API(+Cohort D7) → CreativeMmpDaily. ≤31일 청크·앱별 수집 후 키 병합.

        병합 키 = (creative_name, channel, campaign_name, date). 여러 앱의 같은 키는 합산.
        """
        exclude = {s.lower() for s in exclude_channels} if exclude_channels is not None else self.exclude
        self.last_fetch_truncated = False
        self.revenue_source = "cohort" if self.cohort_d7 else "master"
        self.revenue_fallback_reason = ""
        self.revenue_cohort_matched = 0
        per_app: list[CreativeMmpDaily] = []
        backups: list[tuple] = []   # (rows, Master revenue_d7) — 실패 시 전 앱 Master 로 되돌리기
        for app_id in (self.app_ids or [self.app_id]):
            rows: list[CreativeMmpDaily] = []
            seen: set = set()
            for cs, ce in self._chunks(start, end):
                for rec in parse_master_rows(extract_master(self._fetch_master_csv(cs, ce, app_id)), exclude,
                                             fx_rate=self.usd_to_krw):
                    k = mmp_key(rec.creative_name, rec.channel, rec.campaign_name, str(rec.date))
                    if k not in seen:
                        seen.add(k)
                        rows.append(rec)
            if self.cohort_d7 and self.revenue_source == "cohort":
                backups.append((rows, [r.revenue_d7 for r in rows]))
                try:
                    self.revenue_cohort_matched += self._apply_cohort_d7(app_id, rows, start, end)
                except Exception as e:   # 인증·한도·형식·매칭 실패 → Master 값 유지, 실행 계속
                    self.revenue_source = "master_fallback"
                    self.revenue_fallback_reason = f"{app_id}: {type(e).__name__}: {e}"[:300]
                    print(f"   ⚠️ AppsFlyer Cohort D7 실패 → Master 매출 유지 ({self.revenue_fallback_reason})")
            per_app.extend(rows)
        if self.revenue_source == "master_fallback":
            # 일부 앱만 교체되면 D7·LTV 기준이 섞이므로, 실패가 하나라도 있으면 전 앱 Master 값으로 통일
            for rows, master_rev in backups:
                for r, v in zip(rows, master_rev):
                    r.revenue_d7 = v
            self.revenue_cohort_matched = 0
        return _merge_rows(per_app)
