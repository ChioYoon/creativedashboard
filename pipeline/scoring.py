# -*- coding: utf-8 -*-
"""Stage 6 — UA 스코어러 (대시보드 calculateCreativeScores 의 Python 이식).

step1_integrated.html 의 `calculateCreativeScores` 와 동일한 결과를 산출한다.
- Rank 동점 처리(0.0001 허용오차) · CPA/IPM 0값 최하위 · ROAS 3모드(off/exclude/strict)
- 점수 = (n - Rank + 1) / n × 100 · 가중합 TotalScore · 5등급
- 가중치는 비율(0~1). 대시보드 기본 25/25/25/25 → 0.25 each.

JS 와의 미세 동작까지 일치시킨다(예: Infinity 동점은 abs(inf-inf)=nan<eps=False 라
양쪽 모두 동점으로 묶지 않음 — CPA/IPM 점수는 어차피 0 강제라 무영향).
"""
from __future__ import annotations

from typing import Optional


def _assign_rank_with_ties(sorted_arr, value_getter):
    """JS assignRankWithTies 동일: 값이 0.0001 이내면 직전 Rank 유지, 아니면 index+1."""
    current_rank = 1
    prev = None
    for idx, item in enumerate(sorted_arr):
        v = value_getter(item)
        # JS: Math.abs(v - prev) < 0.0001 — inf-inf=nan 이면 False(동점 아님), 양쪽 동일
        if prev is not None and abs(v - prev) < 0.0001:
            pass  # 동점 → current_rank 유지
        else:
            current_rank = idx + 1
        item["_assignedRank"] = current_rank
        prev = v


def compute_creative_scores(
    creatives: list[dict],
    conv_w: float = 0.25,
    cpa_w: float = 0.25,
    ipm_w: float = 0.25,
    roas_w: float = 0.25,
    roas_mode: str = "auto",
) -> list[dict]:
    """소재 리스트에 점수/등급/Rank 부여 후 TotalScore 내림차순 정렬하여 반환.

    각 dict 은 전환/비용/노출수/클릭수/매출 키를 가져야 한다(없으면 0).
    파생 CPA/IPM/CTR/ROAS 및 *점수/TotalScore/등급/Rank 를 in-place 로 추가한다.
    """
    n = len(creatives)
    if n == 0:
        return []

    # 파생 지표 (대시보드 aggregateCreativeData 와 동일 공식)
    for c in creatives:
        conv = float(c.get("전환", 0) or 0)
        cost = float(c.get("비용", 0) or 0)
        impr = float(c.get("노출수", 0) or 0)
        click = float(c.get("클릭수", 0) or 0)
        rev = float(c.get("매출", c.get("Revenue", 0)) or 0)
        c["전환"], c["비용"], c["노출수"], c["클릭수"], c["매출"] = conv, cost, impr, click, rev
        c["CPA"] = cost / conv if conv > 0 else 0
        c["IPM"] = (conv / impr) * 1000 if impr > 0 else 0
        c["CTR"] = (click / impr) * 100 if impr > 0 else 0
        c["ROAS"] = rev / cost if cost > 0 else 0

    revenue_count = sum(1 for c in creatives if c["매출"] > 0)
    revenue_ratio = revenue_count / n
    has_revenue = revenue_count > 0

    effective = roas_mode
    if roas_mode == "auto":
        if not has_revenue:
            effective = "off"
        elif revenue_ratio < 0.3:
            effective = "exclude"
        else:
            effective = "strict"

    if effective == "off" and roas_w > 0:
        total_other = conv_w + cpa_w + ipm_w
        if total_other > 0:
            ratio = (conv_w + cpa_w + ipm_w + roas_w) / total_other
            conv_w, cpa_w, ipm_w, roas_w = conv_w * ratio, cpa_w * ratio, ipm_w * ratio, 0.0

    # ── Rank 부여 (동점 처리) ──
    conv_sorted = sorted(creatives, key=lambda c: c["전환"], reverse=True)
    _assign_rank_with_ties(conv_sorted, lambda c: c["전환"])
    for c in conv_sorted:
        c["전환Rank"] = c["_assignedRank"]

    # CPA: 전환=0 은 뒤로(최하위), 나머지 CPA 오름차순
    cpa_sorted = sorted(creatives, key=lambda c: (c["전환"] == 0, c["CPA"] if c["전환"] != 0 else 0.0))
    _assign_rank_with_ties(cpa_sorted, lambda c: float("inf") if c["전환"] == 0 else c["CPA"])
    for c in cpa_sorted:
        c["CPARank"] = c["_assignedRank"]

    # IPM: 노출=0 은 뒤로, 나머지 IPM 내림차순
    ipm_sorted = sorted(creatives, key=lambda c: (c["노출수"] == 0, -(c["IPM"]) if c["노출수"] != 0 else 0.0))
    _assign_rank_with_ties(ipm_sorted, lambda c: float("-inf") if c["노출수"] == 0 else c["IPM"])
    for c in ipm_sorted:
        c["IPMRank"] = c["_assignedRank"]

    # ROAS
    if effective == "exclude":
        with_rev = [c for c in creatives if c["매출"] > 0]
        without_rev = [c for c in creatives if c["매출"] == 0]
        roas_sorted = sorted(with_rev, key=lambda c: c["ROAS"], reverse=True)
        _assign_rank_with_ties(roas_sorted, lambda c: c["ROAS"])
        for c in roas_sorted:
            c["ROASRank"] = c["_assignedRank"]
        for c in without_rev:
            c["ROASRank"] = None
            c["_roasExcluded"] = True
    else:
        roas_sorted = sorted(creatives, key=lambda c: c["ROAS"], reverse=True)
        _assign_rank_with_ties(roas_sorted, lambda c: c["ROAS"])
        for c in roas_sorted:
            c["ROASRank"] = c["_assignedRank"]

    # ── Rank → 점수 + TotalScore ──
    for c in creatives:
        c["전환수점수"] = ((n - c["전환Rank"] + 1) / n) * 100
        c["CPA점수"] = 0.0 if c["전환"] == 0 else ((n - c["CPARank"] + 1) / n) * 100
        c["IPM점수"] = 0.0 if c["노출수"] == 0 else ((n - c["IPMRank"] + 1) / n) * 100
        if effective == "exclude" and c.get("_roasExcluded"):
            c["ROAS점수"] = None
            base = conv_w + cpa_w + ipm_w
            if base > 0:
                c["TotalScore"] = (
                    (c["전환수점수"] * conv_w + c["CPA점수"] * cpa_w + c["IPM점수"] * ipm_w)
                    / base * (conv_w + cpa_w + ipm_w + roas_w)
                )
            else:
                c["TotalScore"] = 0.0
        else:
            c["ROAS점수"] = ((n - c["ROASRank"] + 1) / n) * 100 if c["ROASRank"] is not None else 0.0
            c["TotalScore"] = (
                c["전환수점수"] * conv_w + c["CPA점수"] * cpa_w
                + c["IPM점수"] * ipm_w + c["ROAS점수"] * roas_w
            )

    scored = sorted(creatives, key=lambda c: c["TotalScore"], reverse=True)
    for i, c in enumerate(scored):
        c["Rank"] = i + 1
        t = c["TotalScore"]
        c["등급"] = (
            "최우수" if t >= 80 else "우수" if t >= 60 else
            "양호" if t >= 40 else "보통" if t >= 20 else "개선필요"
        )
        c.pop("_assignedRank", None)
        c.pop("_roasExcluded", None)
    return scored
