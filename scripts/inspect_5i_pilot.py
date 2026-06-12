# -*- coding: utf-8 -*-
r"""Stage 5-I 파일럿 검수 — kpi_reality_check / kpi_percentiles 채움 + 품질 육안.

실행: .\.venv\Scripts\python.exe scripts\inspect_5i_pilot.py
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # cp949 콘솔 크래시 회피

JSON = Path("public/data/pepp-us.json")


def top_label(pct):
    if pct is None:
        return "?"
    return f"상위 {max(1, 100 - pct)}%" if pct >= 50 else f"하위 {max(1, pct)}%"


def main():
    d = json.loads(JSON.read_text(encoding="utf-8"))
    cs = d["creatives"]
    n = len(cs)
    has_kpi = [c for c in cs if c.get("kpi_daily")]
    has_reality = [c for c in cs if c.get("kpi_reality_check")]
    has_pct = [c for c in cs if c.get("kpi_percentiles")]

    print(f"=== 5-I 파일럿 검수 (generated_at={d.get('generated_at')}) ===")
    print(f"총 record: {n}")
    print(f"  kpi_daily 보유:        {len(has_kpi)}")
    print(f"  kpi_reality_check 채움: {len(has_reality)}")
    print(f"  kpi_percentiles 채움:   {len(has_pct)}")
    print()

    # 정합성 체크: KPI 있는데 reality_check 없음 / KPI 없는데 reality_check 있음
    kpi_no_reality = [c for c in has_kpi if not c.get("kpi_reality_check")]
    noKpi_yes_reality = [
        c for c in cs if not c.get("kpi_daily") and c.get("kpi_reality_check")
    ]
    print(f"[정합성] KPI 보유 & reality_check 누락: {len(kpi_no_reality)}건"
          f" {'⚠️' if kpi_no_reality else '✅'}")
    print(f"[정합성] KPI 없음 & reality_check 존재(오작동): {len(noKpi_yes_reality)}건"
          f" {'⚠️' if noKpi_yes_reality else '✅'}")
    print()

    # 백분위 범위 sanity (0-100)
    bad_pct = []
    for c in has_pct:
        for k, v in (c.get("kpi_percentiles") or {}).items():
            if v is not None and not (0 <= v <= 100):
                bad_pct.append((c.get("creative_id"), k, v))
    print(f"[정합성] 백분위 0-100 범위 위반: {len(bad_pct)}건 {'⚠️' if bad_pct else '✅'}")
    print()

    # KPI 보유 소재 상세 (reality_check 품질 + 차별 강점 육안)
    print("=" * 70)
    print("KPI 보유 소재 상세 (reality_check + 강점 육안 검수용)")
    print("=" * 70)
    for c in has_kpi:
        name = c.get("creative_concept") or c.get("creative_id")
        p = c.get("kpi_percentiles") or {}
        ctr = c.get("CTR") or c.get("ctr")
        print(f"\n● {name}")
        print(f"   CTR={ctr}  백분위: CTR {top_label(p.get('ctr'))} / "
              f"CVR {top_label(p.get('cvr'))} / CPA {top_label(p.get('cpa'))}")
        rc = c.get("kpi_reality_check")
        print(f"   📊 reality_check: {rc if rc else '(null)'}")
        strengths = c.get("strengths") or []
        sev = c.get("strength_evidence") or []
        for i, s in enumerate(strengths):
            ev = sev[i] if i < len(sev) else ""
            print(f"   💪 강점: {s}")
            if ev:
                print(f"      └ 근거: {ev}")


if __name__ == "__main__":
    main()
