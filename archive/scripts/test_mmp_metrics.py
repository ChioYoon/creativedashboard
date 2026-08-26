# -*- coding: utf-8 -*-
"""MMP 4지표 산출 검증 (D1 잔존수 분모 품질 철학)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.schemas import CreativeMmpDaily
from pipeline.mmp_metrics import aggregate_creative_mmp, compute_mmp_quality

rows = [
    CreativeMmpDaily(creative_name="A", date="2026-02-01", channel="Meta",
                     impressions=10000, clicks=200, cost=50000, installs=100, retained_d1=40, revenue_d7=60000),
    CreativeMmpDaily(creative_name="A", date="2026-02-02", channel="TikTok",
                     impressions=10000, clicks=100, cost=50000, installs=100, retained_d1=60, revenue_d7=40000),
    CreativeMmpDaily(creative_name="B", date="2026-02-01", channel="Meta",
                     impressions=10000, clicks=50, cost=30000, installs=0, retained_d1=0, revenue_d7=0),
]
agg = aggregate_creative_mmp(rows)
assert agg["A"]["impressions"] == 20000 and agg["A"]["retained_d1"] == 100
assert sorted(agg["A"]["channels"]) == ["Meta", "TikTok"]

qa = compute_mmp_quality(agg["A"])
# D1 IPM = 100/20000*1000 = 5.0
assert abs(qa["d1_ipm"] - 5.0) < 1e-9, qa["d1_ipm"]
# D1 CPI = 100000/100 = 1000.0
assert abs(qa["d1_cpi"] - 1000.0) < 1e-9, qa["d1_cpi"]
# D1 Retention = 100/200*100 = 50.0
assert abs(qa["d1_retention"] - 50.0) < 1e-9, qa["d1_retention"]
# D7 ROAS = 100000/100000 = 1.0
assert abs(qa["d7_roas"] - 1.0) < 1e-9, qa["d7_roas"]

# B: 잔존 0 → ipm 0, cpi None, retention 0, roas 0
qb = compute_mmp_quality(agg["B"])
assert qb["d1_ipm"] == 0.0 and qb["d1_cpi"] is None and qb["d1_retention"] == 0.0 and qb["d7_roas"] == 0.0
print("✅ test_mmp_metrics 통과")
