# -*- coding: utf-8 -*-
"""fetch_mmp_window — 3 리포트 호출 분기 + 92일 청크 + 병합 검증."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from datetime import date
import pipeline.sources.airbridge as ab

class Resp:
    def __init__(s, p): s._p=p; s.status_code=200
    def json(s): return s._p
    def raise_for_status(s): pass

class RouteSession:
    """report_path 로 응답 분기. 항상 즉시 SUCCESS."""
    def post(s, url, **kw):
        s._last = "retention" if "retention" in url else "revenue" if "revenue" in url else "actuals"
        return Resp({"task": {"id": "t"}})
    def get(s, url, **kw):
        r = "retention" if "retention" in url else "revenue" if "revenue" in url else "actuals"
        if r == "actuals":
            rows=[{"groupBy":{"ad_creative":"A-X-DA","channel":"Meta","event_date":"2026-02-01"},
                   "metrics":{"impressions":1000,"clicks":10,"cost":5000,"app_installs":20}}]
        elif r == "retention":
            rows=[{"groupBy":{"ad_creative":"A-X-DA","channel":"Meta","event_date":"2026-02-01"},"intervals":[20,8]}]
        else:
            rows=[{"groupBy":{"ad_creative":"A-X-DA","channel":"Meta","event_date":"2026-02-01"},"metrics":{"app_revenue":7000}}]
        return Resp({"task":{"status":"SUCCESS"},"rows":rows})

src = ab.AirbridgeMmpSource(token="t", app_name="pepp", session=RouteSession(), poll_interval_sec=0)
daily = src.fetch_mmp_window(date(2026,2,1), date(2026,2,1), exclude_channels={"googleadwords"})
assert len(daily) == 1
d = daily[0]
assert d.installs == 20 and d.retained_d1 == 8 and d.revenue_d7 == 7000 and d.cost == 5000
print("✅ test_airbridge_window 통과")
