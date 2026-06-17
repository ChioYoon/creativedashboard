# -*- coding: utf-8 -*-
"""parse_actuals_rows 검증 — 실 Airbridge Actuals 결과 형식 (groupBys 리스트 + values 딕트)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.sources.airbridge import parse_actuals_rows, DEFAULT_METRICS

# 실 API 형식: result.actuals.data.rows[], row = {groupBys:[creative,channel,date], values:{key:{value}}}
RESULT = {"actuals": {"data": {"rows": [
    {"groupBys": ["260123_VID_A-AI-Pinball01A-FK_V_1080x1920_EN", "facebook.business", "2026-02-10"],
     "values": {"impressions_channel": {"value": 5000.0}, "clicks_channel": {"value": 120.0},
                "cost_channel": {"value": 719.0}, "app_installs": {"value": 140.0},
                "retention_app_open_day_1_count": {"value": 9.0}, "custom_revenue_j75a3l": {"value": 3.8}}},
    # google.adwords → 제외 채널
    {"groupBys": ["251104_BNR_A-Character-Keyart01A-DA_ALL_Mixed_EN", "google.adwords", "2026-02-10"],
     "values": {"cost_channel": {"value": 9999.0}, "app_installs": {"value": 500.0}}},
    # ad_creative 빈 문자열(오가닉) → 제외
    {"groupBys": ["", "unattributed", "2026-02-10"],
     "values": {"app_installs": {"value": 44.0}}},
]}}}

rows = parse_actuals_rows(RESULT, DEFAULT_METRICS, exclude_channels={"google.adwords", "unattributed"})
assert len(rows) == 1, f"기대 1행(facebook만), 실제 {len(rows)}"
d = rows[0]
assert d.creative_name == "260123_VID_A-AI-Pinball01A-FK_V_1080x1920_EN"
assert d.channel == "facebook.business" and d.date == "2026-02-10"
assert d.impressions == 5000 and d.clicks == 120 and d.cost == 719
assert d.installs == 140 and d.retained_d1 == 9 and d.revenue_d7 == 4  # 3.8 반올림
print("✅ test_airbridge_parse 통과")
