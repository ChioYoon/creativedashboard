# -*- coding: utf-8 -*-
"""Stage 6 동일성 검증 — pipeline.scoring (Python) vs 대시보드 calculateCreativeScores (JS).

scripts/scoring-js-fixture*.json 에 캡처된 대시보드 실행 결과(입력 KPI + JS 점수)를
읽어, 동일 입력·동일 가중치·동일 roas_mode 로 Python 포트를 돌린 뒤 소재별로 비교한다.
3개 ROAS 모드(strict/exclude/off) 전부 검증한다.
합격 기준: 모든 점수 필드가 ±0.1 이내, 등급·Rank 완전 일치.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.scoring import compute_creative_scores

TOL = 0.1
SCORE_FIELDS = ["전환수점수", "CPA점수", "IPM점수", "ROAS점수", "TotalScore"]
HERE = Path(__file__).resolve().parent
FIXTURES = [
    ("strict (auto)", "scoring-js-fixture.json"),
    ("exclude",       "scoring-js-fixture-exclude.json"),
    ("off",           "scoring-js-fixture-off.json"),
]

all_ok = True
for label, fname in FIXTURES:
    fx = json.loads((HERE / fname).read_text(encoding="utf-8"))
    w, rows = fx["weights"], fx["data"]
    eff = fx["roasMeta"]["effectiveMode"]
    print(f"\n=== {label}  (n={fx['n']}, roasMode={fx['roasMode']} → effective={eff}) ===")

    inputs = [{"key": r["key"], "전환": r["전환"], "비용": r["비용"], "노출수": r["노출수"],
               "클릭수": r["클릭수"], "매출": r["매출"]} for r in rows]
    py = compute_creative_scores(inputs, w["conv"], w["cpa"], w["ipm"], w["roas"], fx["roasMode"])
    py_by_key = {c["key"]: c for c in py}

    max_diff, where = 0.0, ""
    score_mm = grade_mm = rank_mm = 0
    detail = []
    for r in rows:
        k, j, p = r["key"], r["js"], py_by_key[r["key"]]
        for f in SCORE_FIELDS:
            jv = j[f] if j[f] is not None else 0.0
            pv = p[f] if p[f] is not None else 0.0
            d = abs(jv - pv)
            if d > max_diff:
                max_diff, where = d, f"{k}.{f}"
            if d > TOL:
                score_mm += 1
                detail.append(f"  ✗ {k}.{f}: JS={jv:.6f} PY={pv:.6f} Δ={d:.6f}")
        if j["등급"] != p["등급"]:
            grade_mm += 1
            detail.append(f"  ✗ {k}.등급: JS={j['등급']} PY={p['등급']}")
        if j["Rank"] != p["Rank"]:
            rank_mm += 1
            detail.append(f"  ✗ {k}.Rank: JS={j['Rank']} PY={p['Rank']}")

    print(f"  최대 점수 오차: {max_diff:.10f}  ({where})")
    print(f"  점수 불일치(>{TOL}): {score_mm} / {len(rows)*len(SCORE_FIELDS)}  ·  등급: {grade_mm}/{len(rows)}  ·  Rank: {rank_mm}/{len(rows)}")
    if detail:
        print("  [불일치]\n" + "\n".join(detail[:30]))
    ok = (max_diff <= TOL) and grade_mm == 0 and rank_mm == 0
    all_ok = all_ok and ok
    print("  " + ("✅ 통과" if ok else "❌ 실패"))

print("\n" + ("=" * 60))
print("✅ 전체 동일성 검증 통과 — Python 포트 = JS (3모드 ±0.1, 등급·Rank 일치)"
      if all_ok else "❌ 일부 모드 불일치 — 포트 수정 필요")
sys.exit(0 if all_ok else 1)
