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
