# -*- coding: utf-8 -*-
"""main.py 의 mmp 주입 헬퍼(inject_mmp_into_records) 단위 검증 (실 API 무의존)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.schemas import CreativeRecord, CreativeMmpDaily
from pipeline.main import inject_mmp_into_records

recs = [CreativeRecord(creative_id="A-X-DA", 소재명="A-X-DA", 파일명="x.png", 유형="BNR")]
daily = [CreativeMmpDaily(creative_name="A-X-DA", date="2026-02-01", channel="Meta",
                          impressions=10000, clicks=100, cost=50000, installs=100, retained_d1=40, revenue_d7=60000)]
inject_mmp_into_records(recs, daily, source_name="airbridge")
r = recs[0]
assert r.mmp_source == "airbridge" and r.mmp_retained_d1 == 40
assert abs(r.mmp_d1_ipm - 4.0) < 1e-9 and abs(r.mmp_d7_roas - 1.2) < 1e-9
assert "Meta" in r.mmp_channels and len(r.mmp_daily) == 1
print("✅ test_main_mmp_inject 통과")
