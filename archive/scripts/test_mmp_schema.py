# -*- coding: utf-8 -*-
"""CreativeMmpDaily + CreativeRecord.mmp_* 필드 round-trip 검증."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.schemas import CreativeMmpDaily, CreativeRecord

d = CreativeMmpDaily(creative_name="A-Test01A-DA", date="2026-02-01", channel="Meta",
                     impressions=1000, clicks=50, cost=20000, installs=40, retained_d1=12, revenue_d7=35000)
assert d.retained_d1 == 12 and d.revenue_d7 == 35000

r = CreativeRecord(creative_id="A-Test01A-DA", 소재명="A-Test01A-DA", 파일명="x.png", 유형="BNR")
assert r.mmp_source is None and r.mmp_daily == [] and r.mmp_d1_ipm is None  # 기본값 graceful
r.mmp_source = "airbridge"; r.mmp_d1_ipm = 12.0; r.mmp_daily = [d]
dumped = r.model_dump(by_alias=True)
assert dumped["mmp_source"] == "airbridge" and dumped["mmp_daily"][0]["retained_d1"] == 12
print("✅ test_mmp_schema 통과")
