# -*- coding: utf-8 -*-
"""Airbridge MMP Source — Stage 7 (7-A 실 API 검증 후 재작성).

설계(2026-06-17 실 API 진단으로 확정):
- 모든 품질 메트릭이 **Actuals 리포트 단일 쿼리**에 존재 → Revenue/Retention 별도 리포트 불필요.
  · 비용/노출/클릭: 채널측 cost_channel·impressions_channel·clicks_channel (광고 네트워크 연동, 4h 갱신)
  · 설치: app_installs
  · D1 잔존수: retention_app_open_day_1_count
  · D7 누적매출: custom_revenue_j75a3l ("Revenue - Sum - D7" — ⚠️ 앱별 custom, titles.json 오버라이드 가능)
- 비동기: POST actuals/query → task.taskId → GET 폴링(task.status SUCCESS).
- 결과: result["actuals"]["data"]["rows"], 각 row = {groupBys:[ad_creative,channel,event_date], values:{metric:{value}}}.
- 非Google 필터: channel 제외 목록(google.adwords + 오가닉/테스트) + ad_creative 비어있는 행(오가닉) 제외.

메트릭/필드 식별자 출처: GET https://api.airbridge.io/dataspec/v2/apps/{app}/actual-report/{metrics,fields}
"""
from __future__ import annotations

import os
import sys
import time
from datetime import date, timedelta
from typing import Optional

import requests

from ..base_errors import AuthError, QuotaError
from ..schemas import CreativeMmpDaily

API_BASE = "https://api.airbridge.io/reports/api"
DATASPEC_BASE = "https://api.airbridge.io/dataspec/v2"
ACTUALS_VER = "v7"

# 품질지표 → Airbridge Actuals 메트릭 key 매핑. 값이 빈 문자열이면 해당 메트릭 생략(→ 0).
# revenue_d7 는 앱별 custom 메트릭이라 env/titles 로 오버라이드 가능.
DEFAULT_METRICS = {
    "impressions": "impressions_channel",
    "clicks": "clicks_channel",
    "cost": "cost_channel",
    "installs": "app_installs",
    "retained_d1": "retention_app_open_day_1_count",
    "revenue_d7": "custom_revenue_j75a3l",
}

# 비-Google 유료 소재 분석이 목적 → Google + 오가닉/테스트 채널 제외.
DEFAULT_EXCLUDE_CHANNELS = ["google.adwords", "unattributed", "appstore", "sns", "airbridge_sdk_test"]


def parse_actuals_rows(result: dict, metrics_map: dict, exclude_channels: set,
                       default_date: str = "", fx_rate: float = 1.0) -> list[CreativeMmpDaily]:
    """Actuals SUCCESS 결과 → CreativeMmpDaily 리스트 (HTTP 무의존, 단위 테스트용).

    row = {"groupBys": [ad_creative, channel, campaign, event_date], "values": {metric_key: {"value": x}}}
    groupBys 순서: gb[0]=ad_creative, gb[1]=channel, gb[2]=campaign, gb[3]=event_date(일자별).
    event_date 미포함(레거시 소재×채널×캠페인 집계)이면 date 는 default_date(윈도우 종료일) 사용.
    ad_creative 가 빈 문자열(오가닉)이거나 channel 이 제외 목록이면 스킵.
    fx_rate: 비용·매출에 곱할 환율(USD→KRW). 1.0 이면 변환 안 함. ROAS 는 비율이라 불변.
    """
    rows = (((result.get("actuals") or {}).get("data") or {}).get("rows")) or []
    out: list[CreativeMmpDaily] = []
    for row in rows:
        gb = row.get("groupBys") or []
        if len(gb) < 2:
            continue
        creative, channel = gb[0], gb[1]
        # groupBys: ["ad_creative", "channel", "campaign", "event_date"]
        campaign_name = gb[2] if len(gb) > 2 else ""
        dt = gb[3] if len(gb) > 3 else default_date  # event_date 있으면 일자별, 없으면 윈도우 종료일
        if not creative or channel in exclude_channels:
            continue
        vals = row.get("values") or {}

        def gv(field: str) -> float:
            key = metrics_map.get(field) or ""
            if not key:
                return 0.0
            cell = vals.get(key) or {}
            return float(cell.get("value", 0) or 0)

        out.append(CreativeMmpDaily(
            creative_name=creative, date=dt, channel=channel, campaign_name=campaign_name,
            impressions=int(round(gv("impressions"))),
            clicks=int(round(gv("clicks"))),
            cost=int(round(gv("cost") * fx_rate)),          # 통화 변환(USD→KRW)
            installs=int(round(gv("installs"))),
            retained_d1=int(round(gv("retained_d1"))),
            revenue_d7=int(round(gv("revenue_d7") * fx_rate)),  # 통화 변환
        ))
    return out


class AirbridgeMmpSource:
    """Airbridge Actuals 단일 쿼리로 소재별 MMP 품질 데이터 수집. (KpiSource ABC 미상속 — 반환형 상이)"""

    def __init__(self, token: str, app_name: str, metrics_map: Optional[dict] = None,
                 usd_to_krw: float = 1.0, session=None, poll_interval_sec: float = 4.0,
                 poll_timeout_sec: float = 300.0, request_timeout: float = 90.0):
        self.token = token
        self.app_name = app_name
        self.metrics_map = dict(metrics_map) if metrics_map else dict(DEFAULT_METRICS)
        self.usd_to_krw = float(usd_to_krw or 1.0)  # 비용·매출 통화 변환 환율(USD→KRW), 1.0=변환 안 함
        self.session = session or requests.Session()
        self.poll_interval_sec = poll_interval_sec
        self.poll_timeout_sec = poll_timeout_sec
        self.request_timeout = request_timeout
        self.last_fetch_truncated: bool = False  # 마지막 fetch에서 100행 cap 초과 여부

    @property
    def currency(self) -> str:
        return "KRW" if self.usd_to_krw and self.usd_to_krw != 1.0 else "USD"

    @classmethod
    def from_env(cls) -> "AirbridgeMmpSource":
        token = os.environ.get("AIRBRIDGE_API_TOKEN", "").strip()
        app = os.environ.get("AIRBRIDGE_APP_NAME", "").strip()
        if not token or not app:
            raise FileNotFoundError(
                "AIRBRIDGE_API_TOKEN / AIRBRIDGE_APP_NAME 미설정. "
                ".env 에 추가하세요 (Airbridge 대시보드 토큰 관리 > API Token)."
            )
        metrics = dict(DEFAULT_METRICS)
        # D7 매출 custom 메트릭은 앱별로 다름 — 오버라이드 허용 (빈 문자열이면 매출 생략)
        rev = os.environ.get("AIRBRIDGE_REVENUE_D7_METRIC")
        if rev is not None:
            metrics["revenue_d7"] = rev.strip()
        try:
            fx = float(os.environ.get("AIRBRIDGE_USD_TO_KRW", "1.0") or "1.0")
        except ValueError:
            fx = 1.0
        return cls(token=token, app_name=app, metrics_map=metrics, usd_to_krw=fx)

    def source_name(self) -> str:
        return "airbridge"

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def _actuals_url(self) -> str:
        return f"{API_BASE}/{ACTUALS_VER}/apps/{self.app_name}/actuals/query"

    def _query_metrics(self) -> list[str]:
        """매핑에서 빈 값 제외한 실제 메트릭 key 목록 (중복 제거, 순서 보존)."""
        seen, out = set(), []
        for k in ("impressions", "clicks", "cost", "installs", "retained_d1", "revenue_d7"):
            m = self.metrics_map.get(k) or ""
            if m and m not in seen:
                seen.add(m); out.append(m)
        return out

    def _create_task(self, body: dict) -> str:
        """POST actuals/query → task.taskId 반환."""
        try:
            resp = self.session.post(self._actuals_url(), json=body, headers=self._headers(), timeout=self.request_timeout)
            resp.raise_for_status()
        except Exception as e:
            self._raise_classified(e, resp_obj=locals().get("resp"))
        task_id = (resp.json().get("task") or {}).get("taskId")
        if not task_id:
            raise RuntimeError(f"Airbridge 응답에 task.taskId 없음: {resp.json()}")
        return task_id

    def _get_page(self, task_id: str, skip: int = 0, size: int = 100) -> dict:
        """GET actuals/query/{task_id}?skip&size → payload (폴링·페이지네이션 공용).

        skip/size 로 100행씩 페이징. 미지정 시 Airbridge 기본(skip=0, size=100).
        """
        url = f"{self._actuals_url()}/{task_id}"
        params = {"skip": skip, "size": size, "viewFormat": "false"}
        try:
            g = self.session.get(url, headers=self._headers(), params=params, timeout=self.request_timeout)
            g.raise_for_status()
        except Exception as e:
            self._raise_classified(e, resp_obj=locals().get("g"))
        return g.json()

    def _poll_until_success(self, task_id: str) -> dict:
        """GET 첫 페이지(skip=0)를 SUCCESS 까지 폴링 → 페이지 0 payload."""
        waited = 0.0
        while waited <= self.poll_timeout_sec:
            payload = self._get_page(task_id, skip=0)
            status = (payload.get("task") or {}).get("status", "")
            if status == "SUCCESS":
                return payload
            if status in ("FAILURE", "CANCELED"):
                raise RuntimeError(f"Airbridge 리포트 실패: status={status}")
            time.sleep(self.poll_interval_sec)
            waited += self.poll_interval_sec
        raise RuntimeError(f"Airbridge 폴링 타임아웃 ({self.poll_timeout_sec}s)")

    def _create_and_poll(self, body: dict) -> dict:
        """POST → 폴링 → 첫 페이지 SUCCESS payload (단일 페이지용 — auth_check 등)."""
        return self._poll_until_success(self._create_task(body))

    @staticmethod
    def _raise_classified(e: Exception, resp_obj=None):
        code = getattr(getattr(resp_obj, "status_code", None), "__int__", lambda: None)() if resp_obj is not None else None
        msg = str(e).lower()
        if code in (401, 403) or "401" in msg or "403" in msg or "unauthorized" in msg:
            raise AuthError(f"Airbridge 인증 실패: {e}")
        if code == 429 or "429" in msg or "too many" in msg:
            raise QuotaError(f"Airbridge rate limit: {e}")
        raise RuntimeError(f"Airbridge HTTP 오류: {e}")

    def auth_check(self) -> bool:
        """cheap call — 최근 1일 Actuals(event_date, impressions_channel) 로 인증·앱 검증."""
        end = date.today() - timedelta(days=1)
        body = {"from": end.isoformat(), "to": end.isoformat(),
                "groupBys": ["event_date"], "metrics": ["impressions_channel"], "filters": [], "sorts": []}
        try:
            self._create_and_poll(body)
            print(f"[airbridge.auth_check] OK (app={self.app_name})", file=sys.stderr)
            return True
        except Exception as e:
            print(f"[airbridge.auth_check] FAIL: {type(e).__name__}: {e}", file=sys.stderr)
            return False

    def fetch_mmp_window(self, start: date, end: date,
                         exclude_channels: Optional[set] = None) -> list[CreativeMmpDaily]:
        """기간 내 ad_creative×channel×campaign×event_date Actuals → CreativeMmpDaily 리스트.

        non-Google + 유료 소재만(오가닉/제외채널/빈 ad_creative 스킵). 최대 400일.
        event_date 를 groupBys 에 포함 → 일자별 분해. skip/size=100 페이지네이션으로
        100행 응답 cap 우회(보고서당 최대 10,000행 — 초과 시 last_fetch_truncated=True).
        """
        exclude = set(exclude_channels) if exclude_channels else set(DEFAULT_EXCLUDE_CHANNELS)
        body = {
            "from": start.isoformat(), "to": end.isoformat(),
            "groupBys": ["ad_creative", "channel", "campaign", "event_date"],
            "metrics": self._query_metrics(), "filters": [], "sorts": [],
        }
        task_id = self._create_task(body)
        page = self._poll_until_success(task_id)  # 페이지 0 (skip=0)

        out: list[CreativeMmpDaily] = []
        PAGE_SIZE = 100
        MAX_PAGES = 100  # 10,000행 / 100 안전상한 (Airbridge 보고서 상한과 일치)
        skip = 0
        pages = 0
        end_iso = end.isoformat()
        while True:
            out += parse_actuals_rows(page, self.metrics_map, exclude,
                                      default_date=end_iso, fx_rate=self.usd_to_krw)
            pages += 1
            pg = page.get("pagination") or {}
            if not pg.get("hasNext") or pages >= MAX_PAGES:
                break
            skip += PAGE_SIZE
            page = self._get_page(task_id, skip=skip, size=PAGE_SIZE)

        pg = page.get("pagination") or {}
        self.last_fetch_truncated = bool(pg.get("hasNext"))  # MAX_PAGES(=1만행) 도달 시에만
        if self.last_fetch_truncated:
            print(f"   [airbridge] ⚠️ 결과 {pg.get('totalCount')}행 중 {pages * PAGE_SIZE}행만 수신 "
                  f"(10,000행 상한 도달) — Raw Data Export 필요.", file=sys.stderr)
        return out

    def fetch_dataspec(self, kind: str) -> list[str]:
        """GET dataspec actual-report/{kind} → key 목록 (kind: 'metrics' | 'fields'). 7-A 검증용."""
        url = f"{DATASPEC_BASE}/apps/{self.app_name}/actual-report/{kind}"
        try:
            r = self.session.get(url, headers={"Authorization": f"Bearer {self.token}"}, timeout=self.request_timeout)
            r.raise_for_status()
            data = r.json()
            return [f.get("key") for g in data.get("data", []) for f in g.get("fields", []) if f.get("key")]
        except Exception as e:
            print(f"[airbridge.dataspec] {kind} 실패: {e}", file=sys.stderr)
            return []
