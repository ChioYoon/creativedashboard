# -*- coding: utf-8 -*-
"""MMP 품질 종합점수 — 4지표 rank 종합 (대시보드 동일 구조: installs↑ d1_cpi↓ d1_ipm↑ d7_roas↑)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.mmp_metrics import compute_mmp_quality_scores

metrics = {
    "A": {"installs": 140, "d1_cpi": 1000.0, "d1_ipm": 5.0, "d7_roas": 1.2},
    "B": {"installs": 40,  "d1_cpi": 3000.0, "d1_ipm": 2.0, "d7_roas": 0.4},
}
scores = compute_mmp_quality_scores(metrics)
# A 가 전 지표 우월 → A.total > B.total, A 등급/순위 1위
assert scores["A"]["total"] > scores["B"]["total"]
assert scores["A"]["rank"] == 1 and scores["B"]["rank"] == 2
# 출력 키는 conv/cpi/ipm/roas (대시보드 scoreMmpItems 와 동일), retention 없음
assert set(scores["A"].keys()) == {"total", "grade", "rank", "conv", "cpi", "ipm", "roas"}, scores["A"].keys()
# A 가 전 축 1위 → 모든 축 점수 100 (n=2 → (2-1+1)/2×100)
assert scores["A"]["conv"] == 100.0 and scores["A"]["cpi"] == 100.0
print("✅ test_mmp_score 통과")
