# -*- coding: utf-8 -*-
"""Stage 7 — MMP 소재 품질지표 산출 (순수 함수, API 무의존).

지표 정의(⚠️ 업계 표준과 다름 — 분모가 D1 잔존수):
  D1 IPM       = D1 잔존수 / 노출 × 1000      (↑ 좋음)
  D1 CPI       = 비용 / D1 잔존수              (↓ 좋음, 잔존0→None)
  D1 Retention = D1 잔존수 / 설치수 × 100      (↑ 좋음, 0~100)
  D7 ROAS      = D0~D7 누적매출 / 비용         (↑ 좋음, 비용0→None)
"""
from __future__ import annotations

from typing import Optional


def aggregate_creative_mmp(daily: list) -> dict:
    """CreativeMmpDaily 리스트 → 소재별 합계 dict.

    Returns: {creative_name: {impressions, clicks, cost, installs, retained_d1, revenue_d7, channels:set}}
    """
    out: dict[str, dict] = {}
    for d in daily:
        a = out.setdefault(d.creative_name, {
            "impressions": 0, "clicks": 0, "cost": 0,
            "installs": 0, "retained_d1": 0, "revenue_d7": 0, "channels": set(),
        })
        a["impressions"] += d.impressions
        a["clicks"] += d.clicks
        a["cost"] += d.cost
        a["installs"] += d.installs
        a["retained_d1"] += d.retained_d1
        a["revenue_d7"] += d.revenue_d7
        if d.channel:
            a["channels"].add(d.channel)
    return out


def compute_mmp_quality(agg: dict) -> dict:
    """한 소재의 집계 dict → 4 품질지표. 0 분모는 룰대로 0 또는 None."""
    impressions = agg.get("impressions", 0)
    cost = agg.get("cost", 0)
    installs = agg.get("installs", 0)
    retained_d1 = agg.get("retained_d1", 0)
    revenue_d7 = agg.get("revenue_d7", 0)

    d1_ipm = (retained_d1 / impressions) * 1000 if impressions > 0 else 0.0
    d1_cpi: Optional[float] = (cost / retained_d1) if retained_d1 > 0 else None
    d1_retention = (retained_d1 / installs) * 100 if installs > 0 else 0.0
    d7_roas: Optional[float] = (revenue_d7 / cost) if cost > 0 else None

    return {"d1_ipm": d1_ipm, "d1_cpi": d1_cpi, "d1_retention": d1_retention, "d7_roas": d7_roas}
