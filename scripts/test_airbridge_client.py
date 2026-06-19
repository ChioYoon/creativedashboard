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
    """POST → task.taskId / 1번째 GET → RUNNING / 2번째 GET(skip=0) → SUCCESS 페이지0(hasNext) /
    3번째 GET(skip=100) → SUCCESS 페이지1(끝). groupBys 4-element(event_date 포함) + 페이지네이션 검증."""
    def __init__(s): s.gets = 0
    def post(s, url, **kw): return Resp({"task": {"taskId": "t-1", "status": "PENDING"}})
    def get(s, url, **kw):
        s.gets += 1
        if s.gets < 2:
            return Resp({"task": {"status": "RUNNING"}})
        if s.gets == 2:  # 페이지0 — 일자별 2행 + google 제외행, hasNext=True
            return Resp({"actuals": {"data": {"rows": [
                {"groupBys": ["260123_VID_A-X-FK_V_1080x1920_EN", "facebook.business", "CAMP_A", "2026-02-10"],
                 "values": {"impressions_channel": {"value": 1000.0}, "clicks_channel": {"value": 20.0},
                            "cost_channel": {"value": 500.0}, "app_installs": {"value": 40.0},
                            "retention_app_open_day_1_count": {"value": 12.0}, "custom_revenue_j75a3l": {"value": 60.0}}},
                {"groupBys": ["x", "google.adwords", "CAMP_A", "2026-02-10"], "values": {"cost_channel": {"value": 9.0}}},
            ]}}, "pagination": {"hasNext": True, "totalCount": 3}, "task": {"taskId": "t-1", "status": "SUCCESS"}})
        # 페이지1 — 다음날 1행, hasNext=False
        return Resp({"actuals": {"data": {"rows": [
            {"groupBys": ["260123_VID_A-X-FK_V_1080x1920_EN", "facebook.business", "CAMP_A", "2026-02-11"],
             "values": {"impressions_channel": {"value": 300.0}, "app_installs": {"value": 5.0}}},
        ]}}, "pagination": {"hasNext": False, "totalCount": 3}, "task": {"taskId": "t-1", "status": "SUCCESS"}})


src = ab.AirbridgeMmpSource(token="t", app_name="pepp", session=FakeSession(), poll_interval_sec=0)
assert src.source_name() == "airbridge"
daily = src.fetch_mmp_window(date(2026, 2, 1), date(2026, 2, 28), exclude_channels={"google.adwords"})
assert len(daily) == 2, f"google 제외 + 2페이지 합산 → 2행, 실제 {len(daily)}"  # 페이지네이션 검증
d0 = next(x for x in daily if x.date == "2026-02-10")
assert d0.channel == "facebook.business" and d0.campaign_name == "CAMP_A"  # gb[2]=campaign
assert d0.cost == 500 and d0.retained_d1 == 12 and d0.revenue_d7 == 60
d1 = next(x for x in daily if x.date == "2026-02-11")  # 페이지1 행 — event_date(gb[3]) 사용
assert d1.impressions == 300 and d1.installs == 5
assert src.last_fetch_truncated is False
print("✅ test_airbridge_client 통과 (페이지네이션 + event_date)")
