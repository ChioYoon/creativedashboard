# -*- coding: utf-8 -*-
"""AppsFlyer MMP Source — Stage 7 (두 번째 MMP 프로바이더).

Airbridge 와 동일 계약: fetch_mmp_window(start, end, exclude) -> list[CreativeMmpDaily].
데이터 = Master API(master-agg-data/v4, GET CSV) 단일 호출: af_ad×pid×c×install_time 로
impressions·clicks·cost·installs·revenue·retention_day_1(D1 잔존수). install_time=설치일별
코호트 분해. 날짜 범위 제한(~3개월) 회피 위해 ≤90일 청크. 파서(extract_master/parse_master_rows)는
HTTP 무의존 — 단위테스트. 라이브 검증 확정(2026-06-26 Starseed JP): 실제 CSV 헤더는
Ad/Media Source/Campaign/Install Time/Impressions/Clicks/Installs/Cost/Revenue/Retention Day 1.

⚠️ 한계: revenue 는 LTV 누적(코호트 D7 정밀화는 후속) → revenue_d7 필드. 비용/노출 결측 행은
분모 가드가 '—' 처리. currency=USD 고정 후 usd_to_krw 로 환산.
"""
from __future__ import annotations

import csv
import io
import os
from datetime import date, timedelta
from typing import Optional

import requests

from ..base_errors import AuthError, QuotaError
from ..schemas import CreativeMmpDaily

MASTER_BASE = "https://hq1.appsflyer.com/api/master-agg-data/v4/app"

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


def _norm_header(h: str) -> str:
    key = (h or "").strip().lower()
    return MASTER_HEADER_MAP.get(key, key)


def _num(v) -> float:
    try:
        return float(str(v).replace(",", "").strip() or 0)
    except (ValueError, AttributeError):
        return 0.0


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
    revenue 는 LTV 누적(D7 정밀화는 후속) → revenue_d7 필드.
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


class AppsFlyerMmpSource:
    """AppsFlyer Master API 로 소재별 MMP 데이터 수집. (KpiSource ABC 미상속 — Airbridge 동일 정책)"""

    MAX_CHUNK_DAYS = 90  # Master API 날짜 범위 제한(~3개월) 회피

    def __init__(self, token: str, app_id: str, usd_to_krw: float = 1.0,
                 session=None, request_timeout: float = 120.0,
                 exclude_media_sources: Optional[set] = None):
        self.token = token
        self.app_id = app_id
        self.usd_to_krw = float(usd_to_krw or 1.0)
        self.session = session or requests.Session()
        self.request_timeout = request_timeout
        self.exclude = {s.lower() for s in (exclude_media_sources or DEFAULT_EXCLUDE_MEDIA_SOURCES)}
        # QA P2-I: Master API(집계)는 Airbridge 류의 절단 신호(hasNext/limit)가 없어 항상 False
        #   유지 — 정확성은 ≤90일 청크 + dedup 이 보장. (향후 행 cap 징후 확인되면 fetch 에서 True 세팅)
        self.last_fetch_truncated = False

    @property
    def currency(self) -> str:
        return "KRW" if self.usd_to_krw and self.usd_to_krw != 1.0 else "USD"

    @classmethod
    def from_env(cls, app_id: str, usd_to_krw: float = 1.0,
                 exclude_media_sources: Optional[set] = None) -> "AppsFlyerMmpSource":
        token = os.environ.get("APPSFLYER_API_TOKEN", "").strip()
        if not token:
            raise FileNotFoundError(
                "APPSFLYER_API_TOKEN 미설정. .env 에 추가하세요 (AppsFlyer 대시보드 > API Token V2.0)."
            )
        if not app_id:
            raise FileNotFoundError("AppsFlyer app_id 미설정 (등록부 'MMP 앱 식별자').")
        return cls(token=token, app_id=app_id, usd_to_krw=usd_to_krw,
                   exclude_media_sources=exclude_media_sources)

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

    def _fetch_master_csv(self, start: date, end: date) -> str:
        """Master API GET → CSV 텍스트. (단위테스트에서 monkeypatch)"""
        url = f"{MASTER_BASE}/{self.app_id}"
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

    def fetch_mmp_window(self, start: date, end: date,
                         exclude_channels: Optional[set] = None) -> list[CreativeMmpDaily]:
        """기간 내 Master API → CreativeMmpDaily. ≤90일 청크 분할·병합·dedup.

        dedup key = (creative_name, channel, campaign_name, date).
        """
        exclude = {s.lower() for s in exclude_channels} if exclude_channels is not None else self.exclude
        out: list[CreativeMmpDaily] = []
        seen: set = set()
        self.last_fetch_truncated = False
        cs = start
        while cs <= end:
            ce = min(cs + timedelta(days=self.MAX_CHUNK_DAYS - 1), end)
            rows = extract_master(self._fetch_master_csv(cs, ce))
            for rec in parse_master_rows(rows, exclude, fx_rate=self.usd_to_krw):
                key = (rec.creative_name, rec.channel, rec.campaign_name, str(rec.date))
                if key not in seen:
                    seen.add(key)
                    out.append(rec)
            cs = ce + timedelta(days=1)
        return out
