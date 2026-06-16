# -*- coding: utf-8 -*-
"""Airbridge MMP Source — Stage 7.

3개 비동기 리포트(Actuals/Revenue/Retention)를 페치→파싱→소재별 CreativeMmpDaily 병합.
HTTP 무의존 파서(parse_*/merge_reports)와 HTTP 클라이언트(AirbridgeMmpSource)를 분리해
파서는 mock fixture로 단위 검증한다.

⚠️ 리포트 응답 JSON key 명은 7-A 1건 실호출로 최종 확인 — parse_* 만 소폭 조정 가능.
레퍼런스: https://help.airbridge.io/en/references/actuals-report
"""
from __future__ import annotations

from typing import Iterable, Optional

from ..schemas import CreativeMmpDaily

import os
import sys
import time
from datetime import date, timedelta

import requests

from ..base_errors import AuthError, QuotaError

API_BASE = "https://api.airbridge.io/reports/api"
REPORT_VERSIONS = {"actuals": "v7", "revenue": "v3", "retention": "v5"}
RETENTION_MAX_DAYS = 92


class AirbridgeMmpSource:
    """Airbridge 3 리포트 비동기 페치 → CreativeMmpDaily 병합. (KpiSource ABC 미상속 — 반환형 상이)"""

    def __init__(self, token: str, app_name: str, session=None,
                 poll_interval_sec: float = 3.0, poll_timeout_sec: float = 180.0):
        self.token = token
        self.app_name = app_name
        self.session = session or requests.Session()
        self.poll_interval_sec = poll_interval_sec
        self.poll_timeout_sec = poll_timeout_sec

    @classmethod
    def from_env(cls) -> "AirbridgeMmpSource":
        token = os.environ.get("AIRBRIDGE_API_TOKEN", "").strip()
        app = os.environ.get("AIRBRIDGE_APP_NAME", "").strip()
        if not token or not app:
            raise FileNotFoundError(
                "AIRBRIDGE_API_TOKEN / AIRBRIDGE_APP_NAME 미설정. "
                ".env 에 추가하세요 (Airbridge 대시보드 Settings>Tokens)."
            )
        return cls(token=token, app_name=app)

    def source_name(self) -> str:
        return "airbridge"

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def _url(self, report_path: str) -> str:
        # report_path 예: "actuals/query" → 버전 prefix 자동
        report = report_path.split("/")[0]
        ver = REPORT_VERSIONS.get(report, "v7")
        return f"{API_BASE}/{ver}/apps/{self.app_name}/{report_path}"

    def _create_and_poll(self, report_path: str, body: dict) -> dict:
        """POST 로 리포트 생성 → taskId → GET 폴링 → SUCCESS 결과 반환."""
        try:
            resp = self.session.post(self._url(report_path), json=body, headers=self._headers(), timeout=30)
            resp.raise_for_status()
        except Exception as e:
            self._raise_classified(e)
        task_id = (resp.json().get("task") or {}).get("id")
        if not task_id:
            raise RuntimeError(f"Airbridge 리포트 생성 응답에 task.id 없음: {resp.json()}")

        poll_url = f"{self._url(report_path)}/{task_id}"
        waited = 0.0
        while waited <= self.poll_timeout_sec:
            try:
                g = self.session.get(poll_url, headers=self._headers(), timeout=30)
                g.raise_for_status()
            except Exception as e:
                self._raise_classified(e)
            payload = g.json()
            status = (payload.get("task") or {}).get("status", "")
            if status == "SUCCESS":
                return payload
            if status in ("FAILURE", "CANCELED"):
                raise RuntimeError(f"Airbridge 리포트 실패: status={status}")
            time.sleep(self.poll_interval_sec)
            waited += self.poll_interval_sec
        raise RuntimeError(f"Airbridge 리포트 폴링 타임아웃 ({self.poll_timeout_sec}s)")

    @staticmethod
    def _raise_classified(e: Exception):
        msg = str(e).lower()
        if "401" in msg or "403" in msg or "unauthorized" in msg:
            raise AuthError(f"Airbridge 인증 실패: {e}")
        if "429" in msg or "too many" in msg:
            raise QuotaError(f"Airbridge rate limit: {e}")
        raise RuntimeError(f"Airbridge HTTP 오류: {e}")

    def auth_check(self) -> bool:
        """cheap call — 최근 1일 Actuals 1행 요청으로 인증·앱 접근 검증."""
        end = date.today() - timedelta(days=1)
        body = {"from": end.isoformat(), "to": end.isoformat(),
                "groupBys": ["event_date"], "metrics": ["impressions"], "filters": [], "sorts": []}
        try:
            self._create_and_poll("actuals/query", body)
            print(f"[airbridge.auth_check] OK (app={self.app_name})", file=sys.stderr)
            return True
        except Exception as e:
            print(f"[airbridge.auth_check] FAIL: {type(e).__name__}: {e}", file=sys.stderr)
            return False


def _gb(row: dict) -> tuple[str, str, str]:
    """row 의 groupBy 에서 (creative, channel, date) 추출."""
    g = row.get("groupBy", {})
    return g.get("ad_creative", ""), g.get("channel", ""), g.get("event_date", "")


def parse_actuals(result: dict, exclude_channels: set) -> list[dict]:
    """Actuals 결과 → [{creative, channel, date, impressions, clicks, cost, installs}] (제외채널 필터)."""
    out = []
    for row in result.get("rows", []):
        creative, channel, date = _gb(row)
        if not creative or channel in exclude_channels:
            continue
        m = row.get("metrics", {})
        out.append({
            "creative": creative, "channel": channel, "date": date,
            "impressions": int(m.get("impressions", 0) or 0),
            "clicks": int(m.get("clicks", 0) or 0),
            "cost": int(round(float(m.get("cost", 0) or 0))),
            "installs": int(m.get("app_installs", 0) or 0),
        })
    return out


def parse_retention(result: dict, exclude_channels: set) -> dict:
    """Retention 결과 → {(creative,channel,date): (installs_interval0, retained_d1_interval1)}."""
    out = {}
    for row in result.get("rows", []):
        creative, channel, date = _gb(row)
        if not creative or channel in exclude_channels:
            continue
        intervals = row.get("intervals", []) or []
        installs = int(intervals[0]) if len(intervals) > 0 else 0
        retained_d1 = int(intervals[1]) if len(intervals) > 1 else 0
        out[(creative, channel, date)] = (installs, retained_d1)
    return out


def parse_revenue(result: dict, exclude_channels: set) -> dict:
    """Revenue 결과 → {(creative,channel,date): revenue_d7}. app_revenue(cumulative D7)."""
    out = {}
    for row in result.get("rows", []):
        creative, channel, date = _gb(row)
        if not creative or channel in exclude_channels:
            continue
        m = row.get("metrics", {})
        out[(creative, channel, date)] = int(round(float(m.get("app_revenue", 0) or 0)))
    return out


def merge_reports(actuals: list[dict], retention: dict, revenue: dict) -> list[CreativeMmpDaily]:
    """3 리포트를 (creative,channel,date) 키로 병합 → CreativeMmpDaily 리스트.

    Actuals 가 기준(노출/비용/설치). retention/revenue 는 코호트 기준이라 같은 키로 left-join.
    Retention 미지원(소재 단위 불가) 시 dict 비어 retained_d1=installs_actuals 못 쓰고 0 →
    해당 지표는 산출 시 None/0 처리(스펙 R1: 가용 지표만).
    """
    out = []
    for a in actuals:
        key = (a["creative"], a["channel"], a["date"])
        ret_installs, retained_d1 = retention.get(key, (0, 0))
        # 설치수 base 는 Retention interval-0 우선, 없으면 Actuals app_installs
        installs = ret_installs if ret_installs > 0 else a["installs"]
        out.append(CreativeMmpDaily(
            creative_name=a["creative"], date=a["date"], channel=a["channel"],
            impressions=a["impressions"], clicks=a["clicks"], cost=a["cost"],
            installs=installs, retained_d1=retained_d1,
            revenue_d7=revenue.get(key, 0),
        ))
    return out
