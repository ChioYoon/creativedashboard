# -*- coding: utf-8 -*-
"""MMP 품질 종합점수 — 4지표 rank 종합 (방향: ipm↑ cpi↓ roas↑ retention↑)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.mmp_metrics import compute_mmp_quality_scores

metrics = {
    "A": {"d1_ipm": 5.0, "d1_cpi": 1000.0, "d7_roas": 1.2, "d1_retention": 50.0},
    "B": {"d1_ipm": 2.0, "d1_cpi": 3000.0, "d7_roas": 0.4, "d1_retention": 20.0},
}
scores = compute_mmp_quality_scores(metrics)
# A 가 전 지표 우월 → A.total > B.total, A 등급 최우수
assert scores["A"]["total"] > scores["B"]["total"]
assert scores["A"]["rank"] == 1 and scores["B"]["rank"] == 2
print("✅ test_mmp_score 통과")
