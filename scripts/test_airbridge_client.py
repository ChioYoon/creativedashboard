# -*- coding: utf-8 -*-
"""AirbridgeMmpSource HTTP 폴링 로직 검증 (requests monkeypatch)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from datetime import date
import pipeline.sources.airbridge as ab

class FakeResp:
    def __init__(self, payload, status=200): self._p = payload; self.status_code = status
    def json(self): return self._p
    def raise_for_status(self):
        if self.status_code >= 400: raise RuntimeError(f"HTTP {self.status_code}")

class FakeSession:
    """POST → taskId, 1번째 GET → RUNNING, 2번째 GET → SUCCESS+rows."""
    def __init__(self): self.gets = 0
    def post(self, url, **kw): return FakeResp({"task": {"id": "task-123"}})
    def get(self, url, **kw):
        self.gets += 1
        if self.gets < 2:
            return FakeResp({"task": {"status": "RUNNING"}})
        return FakeResp({"task": {"status": "SUCCESS"}, "rows": [
            {"groupBy": {"ad_creative": "A-X-DA", "channel": "Meta", "event_date": "2026-02-01"},
             "metrics": {"impressions": 1000, "clicks": 10, "cost": 5000, "app_installs": 20}}]})

src = ab.AirbridgeMmpSource(token="t", app_name="pepp", session=FakeSession(), poll_interval_sec=0)
rows = src._create_and_poll("actuals/query", {"from": "2026-02-01"})
assert rows["task"]["status"] == "SUCCESS" and len(rows["rows"]) == 1
assert src.source_name() == "airbridge"
print("✅ test_airbridge_client 통과")
