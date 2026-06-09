r"""Stage 5-E v2 구조화 신호 ↔ KPI cross-tab 분석.

목적: AI가 도출한 가설(예: '약점=CTA' 소재는 CVR 낮을 것)을 실 KPI 데이터로 검증.

사용법:
    .\.venv\Scripts\python.exe scripts\analyze-signals.py
    .\.venv\Scripts\python.exe scripts\analyze-signals.py --title pepp-us
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

# 가설 ↔ KPI 메타는 schema 옆에 있는 단일 SoT 를 그대로 사용
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.schemas import HYPOTHESIS_KPI_MAP, SIGNAL_FIELDS, signal_distribution  # noqa: E402


# ─────────────────────────────────────────────────────────────
# 단일 패스 aggregator — record list 를 한 번만 walking 해서 imp/clk/conv/cost 동시 산출.
# 이후 ctr/cvr/cpm/cpa 는 이 4 값으로 즉시 계산. 가설별 partition 과 결합해
# O(N * K) 회 sum() 을 O(N) 1회로 줄임.
# ─────────────────────────────────────────────────────────────
def agg(records) -> tuple[int, int, float, int]:
    """returns (impressions, clicks, conversions, cost) — 단일 패스 합산."""
    imp = clk = cost = 0
    conv = 0.0
    for r in records:
        imp += r.get("노출수", 0)
        clk += r.get("클릭수", 0)
        conv += r.get("전환", 0)
        cost += r.get("비용", 0)
    return imp, clk, conv, cost


def metrics(records) -> dict:
    """단일 agg 결과에서 CTR/CVR/CPM/CPA 동시 산출."""
    imp, clk, conv, cost = agg(records)
    return {
        "n": len(records),
        "imp": imp,
        "clk": clk,
        "conv": conv,
        "cost": cost,
        "ctr": (clk / imp * 100) if imp else 0.0,
        "cvr": (conv / imp * 100) if imp else 0.0,
        "cpm": (cost / (imp / 1000)) if imp else 0.0,
        "cpa": (cost / conv) if conv else 0.0,
    }


def group_by_signal(creatives, field: str) -> dict[str, list[dict]]:
    """signal_label → [records with that signal]. 모든 신호를 1 패스로 인덱싱."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in creatives:
        for v in r.get(field) or []:
            groups[v].append(r)
    return dict(groups)


def main():
    # PowerShell cp949 console에서 em-dash(—) 등 unicode 출력 깨짐 방지
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    p = argparse.ArgumentParser()
    p.add_argument("--title", default="pepp-us")
    p.add_argument("--path", default=None)
    args = p.parse_args()

    json_path = Path(args.path) if args.path else Path(f"public/data/{args.title}.json")
    if not json_path.exists():
        sys.exit(f"[X] {json_path} 가 없습니다.")

    d = json.loads(json_path.read_text(encoding="utf-8"))
    creatives = [r for r in d.get("creatives", []) if r.get("노출수", 0) > 0]
    if not creatives:
        sys.exit(f"[!] {json_path} 에 KPI 있는 record 0개. main.py 실행 또는 KPI 활성화 확인.")

    overall = metrics(creatives)
    print(f"분석 대상: {json_path}")
    print(f"KPI 보유 record: {overall['n']}개")
    print(f"전체 노출 합:    {overall['imp']:,}")
    print(f"전체 비용 합:    {overall['cost']:,} KRW")
    print(f"전체 전환 합:    {overall['conv']:,}")
    print(f"전체 CTR:        {overall['ctr']:.2f}%")
    print(f"전체 CVR:        {overall['cvr']:.2f}%")
    print(f"전체 CPM:        {overall['cpm']:,.0f} KRW")
    print(f"전체 CPA:        {overall['cpa']:,.0f} KRW")

    # ── 가설1: 약점 있음 vs 없음 분리 (단일 partition 으로) ──
    print(f"\n{'=' * 70}\n[가설1] 약점 신호별 평균 성과 (있음 vs 없음)\n{'=' * 70}")
    print(f"{'약점 신호':<25}  {'n_w':>4}  {'CTR_w':>7}  {'CTR_wo':>7}  {'CVR_w':>7}  {'CVR_wo':>7}  {'CPA_w':>10}  {'CPA_wo':>10}")
    print("-" * 95)
    weakness_groups = group_by_signal(creatives, "weaknesses")
    weakness_set = set(weakness_groups.keys())
    for wn in sorted(weakness_set):
        with_ws = weakness_groups[wn]
        without_ws = [r for r in creatives if wn not in (r.get("weaknesses") or [])]
        if not without_ws:
            continue
        mw, mo = metrics(with_ws), metrics(without_ws)
        print(
            f"{wn[:23]:<25}  "
            f"{mw['n']:>4}  "
            f"{mw['ctr']:>6.2f}%  {mo['ctr']:>6.2f}%  "
            f"{mw['cvr']:>6.2f}%  {mo['cvr']:>6.2f}%  "
            f"{mw['cpa']:>10,.0f}  {mo['cpa']:>10,.0f}"
        )

    # ── 가설2: 강점 신호별 평균 성과 ──
    print(f"\n{'=' * 70}\n[가설2] 강점 신호별 평균 성과\n{'=' * 70}")
    print(f"{'강점 신호':<25}  {'n':>4}  {'imp_avg':>10}  {'CTR':>7}  {'CVR':>7}  {'CPM':>10}  {'CPA':>10}")
    print("-" * 85)
    strength_groups = group_by_signal(creatives, "strengths")
    # sort: imp 합 내림차순. metrics() 결과를 캐시해서 정렬 비교당 재합산 회피.
    strength_metrics = {sn: metrics(rs) for sn, rs in strength_groups.items()}
    for sn in sorted(strength_metrics, key=lambda k: -strength_metrics[k]["imp"]):
        m = strength_metrics[sn]
        avg_imp = m["imp"] // m["n"] if m["n"] else 0
        print(
            f"{sn[:23]:<25}  "
            f"{m['n']:>4}  "
            f"{avg_imp:>10,}  "
            f"{m['ctr']:>6.2f}%  {m['cvr']:>6.2f}%  "
            f"{m['cpm']:>10,.0f}  {m['cpa']:>10,.0f}"
        )

    # ── 가설3: AI 가설 vs 실 KPI 검증 (메타 매핑 기반) ──
    print(f"\n{'=' * 70}\n[가설3] AI 성과 가설 vs 실 KPI 검증\n{'=' * 70}")
    print(f"전체 평균: CTR={overall['ctr']:.2f}%, CVR={overall['cvr']:.2f}%, CPA={overall['cpa']:,.0f} KRW\n")
    print(f"{'AI 가설':<40}  {'n':>4}  {'CTR':>7}  {'CVR':>7}  {'CPA':>10}  {'판정'}")
    print("-" * 90)
    hypothesis_groups = group_by_signal(creatives, "hypothesis")
    for hn in sorted(hypothesis_groups):
        m = metrics(hypothesis_groups[hn])
        # schema 의 메타 매핑에서 (metric, direction) 조회
        kpi_meta = HYPOTHESIS_KPI_MAP.get(hn)
        verdict = ""
        if kpi_meta:
            metric_name, direction = kpi_meta
            current = m[metric_name.lower()]
            baseline = overall[metric_name.lower()]
            if direction == "high":
                verdict = "✓ 확증" if current > baseline else "✗ 반증"
            elif direction == "low":
                verdict = "✓ 확증" if current < baseline else "✗ 반증"
        print(
            f"{hn[:38]:<40}  "
            f"{m['n']:>4}  "
            f"{m['ctr']:>6.2f}%  {m['cvr']:>6.2f}%  "
            f"{m['cpa']:>10,.0f}  "
            f"{verdict}"
        )

    # ── 가설4: 추천 변주 우선순위 (signal_distribution 재사용) ──
    print(f"\n{'=' * 70}\n[가설4] 다음 회차 제작 To-Do (test_ideas 추천 Top)\n{'=' * 70}")
    distribution = signal_distribution(creatives)
    n_total = overall["n"]
    for t, n in distribution["test_ideas"].most_common(10):
        print(f"  {t:<25}  {n}건 추천 ({n*100//n_total}%)")

    print(f"\n{'=' * 70}")
    print(f"분석 완료. AI 가설 ↔ 실 KPI 일치 여부를 위 [가설3]에서 확인하세요.")


if __name__ == "__main__":
    main()
