# -*- coding: utf-8 -*-
"""mmp.py dry-run 바디 빌더 검증 (토큰 무의존)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from datetime import date
from pipeline.sources.airbridge import AirbridgeMmpSource

src = AirbridgeMmpSource(token="x", app_name="pepp", session=object())
b = src._retention_body(date(2026,2,1), date(2026,2,28))
assert b["intervalsPeriod"] == 1 and "ad_creative" in b["groupBy"]["fields"]
rb = src._revenue_body(date(2026,2,1), date(2026,2,28))
assert rb["intervalsPeriodIndexes"] == [7] and rb["aggregationType"] == "cumulative"
print("✅ test_mmp_cli_dryrun 통과")
