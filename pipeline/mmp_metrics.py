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

from .scoring import _assign_rank_with_ties


def aggregate_rows_total(rows: list) -> dict:
    """평탄 CreativeMmpDaily 리스트 전체를 1개 집계로 합산 (creative_name 무시).

    한 concept(폴더명)의 모든 변형(L/S/V·채널·일자)을 하나로 합칠 때 사용 — main.py inject.
    Returns: {impressions, clicks, cost, installs, retained_d1, revenue_d7, channels:set}
    """
    total = {
        "impressions": 0, "clicks": 0, "cost": 0,
        "installs": 0, "retained_d1": 0, "revenue_d7": 0, "channels": set(),
    }
    for d in rows:
        total["impressions"] += d.impressions
        total["clicks"] += d.clicks
        total["cost"] += d.cost
        total["installs"] += d.installs
        total["retained_d1"] += d.retained_d1
        total["revenue_d7"] += d.revenue_d7
        if d.channel:
            total["channels"].add(d.channel)
    return total


def aggregate_creative_mmp(daily: list) -> dict:
    """CreativeMmpDaily 리스트 → creative_name별 합계 dict (CLI 표시용).

    Returns: {creative_name: {impressions, clicks, cost, installs, retained_d1, revenue_d7, channels:set}}
    """
    by_name: dict[str, list] = {}
    for d in daily:
        by_name.setdefault(d.creative_name, []).append(d)
    return {name: aggregate_rows_total(rows) for name, rows in by_name.items()}


def compute_mmp_quality(agg: dict) -> dict:
    """한 소재의 집계 dict → 4 품질지표. 0 분모는 None (cost·impressions=0 → '—')."""
    impressions = agg.get("impressions", 0)
    cost = agg.get("cost", 0)
    installs = agg.get("installs", 0)
    retained_d1 = agg.get("retained_d1", 0)
    revenue_d7 = agg.get("revenue_d7", 0)

    d1_ipm: Optional[float] = (retained_d1 / impressions) * 1000 if impressions > 0 else None
    d1_cpi: Optional[float] = (cost / retained_d1) if (retained_d1 > 0 and cost > 0) else None
    d1_retention = (retained_d1 / installs) * 100 if installs > 0 else 0.0
    d7_roas: Optional[float] = (revenue_d7 / cost) if cost > 0 else None

    return {"d1_ipm": d1_ipm, "d1_cpi": d1_cpi, "d1_retention": d1_retention, "d7_roas": d7_roas}


def compute_mmp_quality_scores(metrics_by_creative: dict) -> dict:
    """소재별 4지표 dict → 품질 종합점수 {total, grade, rank, conv/cpi/ipm/roas 점수}.

    Google Ads 종합점수와 동일 4지표 구조(대시보드 일치): 전환(installs)↑·D1 CPI↓·D1 IPM↑·D7 ROAS↑.
    균등 25%. None 지표는 해당 축 점수 0(최하). rank 점수 = (n-rank+1)/n×100.
    (D1 잔존율은 표시용 지표로만 유지 — 점수 축에서는 전환으로 대체)
    """
    keys = list(metrics_by_creative.keys())
    n = len(keys)
    if n == 0:
        return {}
    items = [{"key": k, **metrics_by_creative[k]} for k in keys]

    def rank_score(field: str, higher_better: bool):
        # None 은 최하위로: higher_better 면 -inf, 아니면 +inf
        def val(it):
            v = it.get(field)
            if v is None:
                return float("-inf") if higher_better else float("inf")
            return v
        ordered = sorted(items, key=val, reverse=higher_better)
        _assign_rank_with_ties(ordered, val)
        for it in ordered:
            none_v = it.get(field) is None
            it[f"_s_{field}"] = 0.0 if none_v else ((n - it["_assignedRank"] + 1) / n) * 100

    rank_score("installs", True)
    rank_score("d1_cpi", False)
    rank_score("d1_ipm", True)
    rank_score("d7_roas", True)

    for it in items:
        it["_total"] = (it["_s_installs"] + it["_s_d1_cpi"] + it["_s_d1_ipm"] + it["_s_d7_roas"]) / 4

    ranked = sorted(items, key=lambda it: it["_total"], reverse=True)
    out = {}
    for i, it in enumerate(ranked):
        t = it["_total"]
        grade = ("최우수" if t >= 80 else "우수" if t >= 60 else "양호" if t >= 40 else "보통" if t >= 20 else "개선필요")
        out[it["key"]] = {
            "total": round(t, 2), "grade": grade, "rank": i + 1,
            "conv": round(it["_s_installs"], 1), "cpi": round(it["_s_d1_cpi"], 1),
            "ipm": round(it["_s_d1_ipm"], 1), "roas": round(it["_s_d7_roas"], 1),
        }
    return out
