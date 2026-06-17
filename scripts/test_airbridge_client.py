# -*- coding: utf-8 -*-
"""AirbridgeMmpSource 폴링 + fetch_mmp_window end-to-end (실 형식 mock, requests 대체)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from datetime import date
import pipeline.sources.airbridge as ab


class Resp:
    def __init__(s, p): s._p = p; s.status_code = 200
    def json(s): return s._p
    def raise_for_status(s): pass


class FakeSession:
    """POST → task.taskId / 1번째 GET → RUNNING / 2번째 GET → SUCCESS + 실 형식 rows."""
    def __init__(s): s.gets = 0
    def post(s, url, **kw): return Resp({"task": {"taskId": "t-1", "status": "PENDING"}})
    def get(s, url, **kw):
        s.gets += 1
        if s.gets < 2:
            return Resp({"task": {"status": "RUNNING"}})
        return Resp({"actuals": {"data": {"rows": [
            {"groupBys": ["260123_VID_A-X-FK_V_1080x1920_EN", "facebook.business", "2026-02-10"],
             "values": {"impressions_channel": {"value": 1000.0}, "clicks_channel": {"value": 20.0},
                        "cost_channel": {"value": 500.0}, "app_installs": {"value": 40.0},
                        "retention_app_open_day_1_count": {"value": 12.0}, "custom_revenue_j75a3l": {"value": 60.0}}},
            {"groupBys": ["x", "google.adwords", "2026-02-10"], "values": {"cost_channel": {"value": 9.0}}},
        ]}}, "task": {"taskId": "t-1", "status": "SUCCESS"}})


src = ab.AirbridgeMmpSource(token="t", app_name="pepp", session=FakeSession(), poll_interval_sec=0)
assert src.source_name() == "airbridge"
daily = src.fetch_mmp_window(date(2026, 2, 1), date(2026, 2, 28), exclude_channels={"google.adwords"})
assert len(daily) == 1, f"google 제외 → 1행, 실제 {len(daily)}"
d = daily[0]
assert d.channel == "facebook.business" and d.cost == 500 and d.retained_d1 == 12 and d.revenue_d7 == 60
print("✅ test_airbridge_client 통과")
