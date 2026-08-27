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

# 멀티변형 concept: 두 파일명(L/V 변형)이 한 concept 으로 정규화 → 지표는 전체 SUM 이어야 함
# (concept 단위 합산 — 첫 변형만 반영하던 데이터 손실 회귀 가드)
recs2 = [CreativeRecord(creative_id="A-Y-DA", 소재명="A-Y-DA", 파일명="y.png", 유형="BNR")]
daily2 = [
    CreativeMmpDaily(creative_name="251104_BNR_A-Y-DA_L_1200x628_EN.jpg", date="2026-02-01", channel="Meta",
                     impressions=10000, clicks=100, cost=30000, installs=50, retained_d1=50, revenue_d7=20000),
    CreativeMmpDaily(creative_name="251104_VID_A-Y-DA_L_1920x1080_EN.mp4", date="2026-02-01", channel="TikTok",
                     impressions=10000, clicks=80, cost=20000, installs=50, retained_d1=90, revenue_d7=10000),
]
inject_mmp_into_records(recs2, daily2, source_name="airbridge")
r2 = recs2[0]
assert r2.mmp_retained_d1 == 140, r2.mmp_retained_d1       # 50+90 (모든 변형 합산)
assert r2.mmp_cost == 50000 and r2.mmp_revenue == 30000
assert sorted(r2.mmp_channels) == ["Meta", "TikTok"] and len(r2.mmp_daily) == 2

# Facebook _ALL_Mixed_ 형식 파일명도 concept 추출되어 join 되는지 (mmp_concept fallback)
recs3 = [CreativeRecord(creative_id="A-Character-Keyart01A-DA", 소재명="A-Character-Keyart01A-DA", 파일명="z.png", 유형="BNR")]
daily3 = [CreativeMmpDaily(creative_name="251104_BNR_A-Character-Keyart01A-DA_ALL_Mixed_EN", date="2026-02-01",
                           channel="facebook.business", impressions=8000, clicks=50, cost=359, installs=33, retained_d1=7, revenue_d7=21)]
inject_mmp_into_records(recs3, daily3, source_name="airbridge", currency="KRW", fx_rate=1500.0)
r3 = recs3[0]
assert r3.mmp_source == "airbridge" and r3.mmp_retained_d1 == 7, "Facebook _ALL_Mixed_ concept join 실패"
assert "facebook.business" in r3.mmp_channels
assert r3.mmp_currency == "KRW" and r3.mmp_fx_rate == 1500.0  # 통화 메타 기록
print("✅ test_main_mmp_inject 통과")
