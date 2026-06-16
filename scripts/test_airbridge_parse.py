# -*- coding: utf-8 -*-
"""Airbridge 리포트 응답 파서 검증 (mock fixture — 문서화된 row 구조 기준)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.sources.airbridge import parse_actuals, parse_retention, parse_revenue, merge_reports

# Airbridge 리포트 결과는 groupBy 값 배열 + metric 값 배열 형태 (rows).
ACTUALS = {"rows": [
    {"groupBy": {"ad_creative": "A-Test01A-DA", "channel": "Meta", "event_date": "2026-02-01"},
     "metrics": {"impressions": 10000, "clicks": 200, "cost": 50000, "app_installs": 100}},
    {"groupBy": {"ad_creative": "A-Test01A-DA", "channel": "googleadwords", "event_date": "2026-02-01"},
     "metrics": {"impressions": 99999, "clicks": 1, "cost": 1, "app_installs": 1}},  # 제외 대상
]}
RETENTION = {"rows": [
    {"groupBy": {"ad_creative": "A-Test01A-DA", "channel": "Meta", "event_date": "2026-02-01"},
     "intervals": [100, 40]},  # interval0=설치, interval1=D1 잔존
]}
REVENUE = {"rows": [
    {"groupBy": {"ad_creative": "A-Test01A-DA", "channel": "Meta", "event_date": "2026-02-01"},
     "metrics": {"app_revenue": 60000}},  # intervalsPeriodIndexes:[7] cumulative
]}

a = parse_actuals(ACTUALS, exclude_channels={"googleadwords"})
assert len(a) == 1 and a[0]["impressions"] == 10000 and a[0]["installs"] == 100
ret = parse_retention(RETENTION, exclude_channels={"googleadwords"})
assert ret[("A-Test01A-DA", "Meta", "2026-02-01")] == (100, 40)
rev = parse_revenue(REVENUE, exclude_channels={"googleadwords"})
assert rev[("A-Test01A-DA", "Meta", "2026-02-01")] == 60000

merged = merge_reports(a, ret, rev)
assert len(merged) == 1
m = merged[0]
assert m.creative_name == "A-Test01A-DA" and m.installs == 100 and m.retained_d1 == 40 and m.revenue_d7 == 60000
print("✅ test_airbridge_parse 통과")
