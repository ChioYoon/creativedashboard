# Stage 7-B — Airbridge MMP 백엔드 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Airbridge(MMP) 3개 리포트(Actuals/Revenue/Retention)에서 Google Ads 外 매체의 소재별 데이터를 받아 4개 품질지표(D1 IPM·D1 CPI·D7 ROAS·D1 Retention)를 산출하고 `public/data/{title}.json` 의 신규 `mmp_*` 레이어에 저장한다.

**Architecture:** 순수 산출 로직(`mmp_metrics.py`)과 HTTP 페치(`sources/airbridge.py`)를 분리해 산출은 API 없이 테스트한다. main.py 가 기존 Google Ads join **이후** Airbridge를 추가 페치→소재명 join→`mmp_*` 주입(기존 KPI 불변). 매체 필터로 Google Ads 채널 제외(중복 방지). 비동기 리포트는 POST→폴링→파싱→병합.

**Tech Stack:** Python 3.11+, `requests`(설치됨 2.34.2), Pydantic v2, 기존 KpiSource/KpiCache 패턴. 테스트는 프로젝트 컨벤션인 `scripts/` 독립 검증 스크립트(assert 기반, pytest 미사용).

---

## 설계 메모 (스펙 대비 정정)

- 스펙은 "KpiSource 서브클래스"라 했으나, MMP는 `CreativeKpiDaily`가 아닌 신규 `CreativeMmpDaily`를 반환하므로 **ABC를 상속하지 않는 독립 클래스** `AirbridgeMmpSource`로 구현한다(동일한 `source_name()`/`auth_check()`/`from_env()` 컨벤션은 따름). AppsFlyer 추가 시 공통 ABC 추출은 그때 결정(YAGNI).
- **D7 ROAS는 API의 `app_roas` 비율을 쓰지 않고** 누적 D7 매출(`app_revenue`, intervalsPeriodIndexes:[7], cumulative) + 비용(Actuals)으로 **소재 레벨에서 Σ매출/Σ비용 직접 계산**(비율 평균 오류 회피, 대시보드 ROAS 산식과 일관).
- 비동기 리포트 응답 JSON의 정확한 key 명은 7-A에서 1건 실호출로 최종 확인 → `_parse_*` 함수만 소폭 조정될 수 있음. 본 계획은 [Actuals/Revenue/Retention 레퍼런스](https://help.airbridge.io/en/references/actuals-report) 의 문서화된 구조 기준.

## Prerequisite — Stage 7-A (사용자 작업, 코드 아님)

구현 착수 전 사용자가 완료해야 하나, **Task 1~5(mock 기반)는 토큰 없이 선행 개발 가능**. Task 6의 `mmp.py --metadata-check` 가 7-A 검증 도구를 제공한다.

- [ ] Airbridge 대시보드 [Settings] > [Tokens] 에서 API 토큰 발급 → `.env` 에 `AIRBRIDGE_API_TOKEN`, `AIRBRIDGE_APP_NAME` 기입
- [ ] `python -m pipeline.mmp --metadata-check` 실행 → **Revenue·Retention 리포트의 `ad_creative` groupBy 지원 여부** 확정 (스펙 R1). 미지원 지표는 자동 생략.
- [ ] Airbridge channel 목록에서 **Google Ads 표기명** 확인 (예: "Google Ads"/"googleadwords") → `.env` `AIRBRIDGE_EXCLUDE_CHANNELS` 기입
- [ ] pepp 에 非Google 매체 데이터(설치>0) 존재 확인 (`--metadata-check` 가 함께 출력). 없으면 첫 대상 타이틀 재고.

---

## Task 1: 스키마 — CreativeMmpDaily + CreativeRecord mmp_* 필드

**Files:**
- Modify: `pipeline/schemas.py` (CreativeKpiDaily 클래스 근처에 신규 모델 추가 + CreativeRecord 에 필드 추가)
- Test: `scripts/test_mmp_schema.py` (신규)

- [ ] **Step 1: 실패 테스트 작성**

`scripts/test_mmp_schema.py`:
```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python.exe scripts/test_mmp_schema.py`
Expected: FAIL — `ImportError: cannot import name 'CreativeMmpDaily'`

- [ ] **Step 3: 스키마 구현**

`pipeline/schemas.py` 의 `class CreativeKpiDaily` 정의 **직전**에 추가:
```python
class CreativeMmpDaily(BaseModel):
    """MMP(Airbridge) 일별·채널별 소재 데이터. kpi_daily(Google Ads)와 분리된 레이어.

    date = 코호트 기준 설치일(YYYY-MM-DD). 비용/노출은 해당일, 잔존/매출은 코호트 누적.
    """
    creative_name: str
    date: str
    channel: str                  # 비-Google 매체명 (Meta/TikTok/ASA 등)
    impressions: int = 0
    clicks: int = 0
    cost: int = 0                 # 정수 화폐단위(KRW)
    installs: int = 0            # 코호트 설치수 (Retention interval-0)
    retained_d1: int = 0         # D1 잔존수 (Retention interval-1)
    revenue_d7: int = 0          # D0~D7 누적 인앱매출
```

`pipeline/schemas.py` 의 `class CreativeRecord` 안, `kpi_daily` 필드 **직후**에 추가:
```python
    # ──────────────────────────────────────────────────────────
    # Stage 7: MMP(Airbridge) 소재 품질 레이어 — 非Google 매체. 전부 Optional(graceful).
    # 산출은 코드(pipeline/mmp_metrics.py). 대시보드는 별도 "소재 품질" 레이어로 표시.
    # ──────────────────────────────────────────────────────────
    mmp_source: Optional[str] = Field(None, description="MMP 출처: 'airbridge' | None")
    mmp_channels: list[str] = Field(default_factory=list, description="이 소재가 노출된 비-Google 채널")
    mmp_d1_ipm: Optional[float] = Field(None, description="D1 잔존수/노출×1000 (높을수록 좋음)")
    mmp_d1_cpi: Optional[float] = Field(None, description="비용/D1 잔존수 (낮을수록 좋음, 잔존0→None)")
    mmp_d7_roas: Optional[float] = Field(None, description="D7 누적매출/비용 (높을수록 좋음, 비용0→None)")
    mmp_d1_retention: Optional[float] = Field(None, description="D1 잔존수/설치수 ×100 (0~100)")
    mmp_quality_score: Optional[dict] = Field(None, description="4지표 rank 종합 {total,grade,rank,...} (phase-2)")
    mmp_installs: Optional[int] = None
    mmp_retained_d1: Optional[int] = None
    mmp_cost: Optional[int] = None
    mmp_revenue: Optional[int] = None  # D7 누적매출 합
    mmp_daily: list["CreativeMmpDaily"] = Field(default_factory=list, description="채널별·일별(sparkline)")
```

`CreativeRecord` 가 `CreativeMmpDaily` 를 forward-ref 로 참조하므로, 파일 끝(또는 CreativeRecord 정의 뒤)에 기존 `CreativeRecord.model_rebuild()` 가 있으면 그대로, 없으면 추가:
```python
CreativeRecord.model_rebuild()
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/Scripts/python.exe scripts/test_mmp_schema.py`
Expected: PASS — `✅ test_mmp_schema 통과`

- [ ] **Step 5: 커밋**

```bash
git add pipeline/schemas.py scripts/test_mmp_schema.py
git commit -m "[Stage 7-B] schemas: CreativeMmpDaily + CreativeRecord mmp_* 필드"
```

---

## Task 2: mmp_metrics.py — 집계 + 4 품질지표 (순수 함수)

**Files:**
- Create: `pipeline/mmp_metrics.py`
- Test: `scripts/test_mmp_metrics.py` (신규)

- [ ] **Step 1: 실패 테스트 작성**

`scripts/test_mmp_metrics.py`:
```python
# -*- coding: utf-8 -*-
"""MMP 4지표 산출 검증 (D1 잔존수 분모 품질 철학)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.schemas import CreativeMmpDaily
from pipeline.mmp_metrics import aggregate_creative_mmp, compute_mmp_quality

rows = [
    CreativeMmpDaily(creative_name="A", date="2026-02-01", channel="Meta",
                     impressions=10000, clicks=200, cost=50000, installs=100, retained_d1=40, revenue_d7=60000),
    CreativeMmpDaily(creative_name="A", date="2026-02-02", channel="TikTok",
                     impressions=10000, clicks=100, cost=50000, installs=100, retained_d1=60, revenue_d7=40000),
    CreativeMmpDaily(creative_name="B", date="2026-02-01", channel="Meta",
                     impressions=10000, clicks=50, cost=30000, installs=0, retained_d1=0, revenue_d7=0),
]
agg = aggregate_creative_mmp(rows)
assert agg["A"]["impressions"] == 20000 and agg["A"]["retained_d1"] == 100
assert sorted(agg["A"]["channels"]) == ["Meta", "TikTok"]

qa = compute_mmp_quality(agg["A"])
# D1 IPM = 100/20000*1000 = 5.0
assert abs(qa["d1_ipm"] - 5.0) < 1e-9, qa["d1_ipm"]
# D1 CPI = 100000/100 = 1000.0
assert abs(qa["d1_cpi"] - 1000.0) < 1e-9, qa["d1_cpi"]
# D1 Retention = 100/200*100 = 50.0
assert abs(qa["d1_retention"] - 50.0) < 1e-9, qa["d1_retention"]
# D7 ROAS = 100000/100000 = 1.0
assert abs(qa["d7_roas"] - 1.0) < 1e-9, qa["d7_roas"]

# B: 잔존 0 → ipm 0, cpi None, retention 0, roas 0
qb = compute_mmp_quality(agg["B"])
assert qb["d1_ipm"] == 0.0 and qb["d1_cpi"] is None and qb["d1_retention"] == 0.0 and qb["d7_roas"] == 0.0
print("✅ test_mmp_metrics 통과")
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python.exe scripts/test_mmp_metrics.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.mmp_metrics'`

- [ ] **Step 3: 구현**

`pipeline/mmp_metrics.py`:
```python
# -*- coding: utf-8 -*-
"""Stage 7 — MMP 소재 품질지표 산출 (순수 함수, API 무의존).

지표 정의(⚠️ 업계 표준과 다름 — 분모가 D1 잔존수):
  D1 IPM       = D1 잔존수 / 노출 × 1000      (↑ 좋음)
  D1 CPI       = 비용 / D1 잔존수              (↓ 좋음, 잔존0→None)
  D1 Retention = D1 잔존수 / 설치수 × 100      (↑ 좋음, 0~100)
  D7 ROAS      = D0~D7 누적매출 / 비용         (↑ 좋음, 비용0→None)
"""
from __future__ import annotations

from typing import Optional


def aggregate_creative_mmp(daily: list) -> dict:
    """CreativeMmpDaily 리스트 → 소재별 합계 dict.

    Returns: {creative_name: {impressions, clicks, cost, installs, retained_d1, revenue_d7, channels:set}}
    """
    out: dict[str, dict] = {}
    for d in daily:
        a = out.setdefault(d.creative_name, {
            "impressions": 0, "clicks": 0, "cost": 0,
            "installs": 0, "retained_d1": 0, "revenue_d7": 0, "channels": set(),
        })
        a["impressions"] += d.impressions
        a["clicks"] += d.clicks
        a["cost"] += d.cost
        a["installs"] += d.installs
        a["retained_d1"] += d.retained_d1
        a["revenue_d7"] += d.revenue_d7
        if d.channel:
            a["channels"].add(d.channel)
    return out


def compute_mmp_quality(agg: dict) -> dict:
    """한 소재의 집계 dict → 4 품질지표. 0 분모는 룰대로 0 또는 None."""
    impressions = agg.get("impressions", 0)
    cost = agg.get("cost", 0)
    installs = agg.get("installs", 0)
    retained_d1 = agg.get("retained_d1", 0)
    revenue_d7 = agg.get("revenue_d7", 0)

    d1_ipm = (retained_d1 / impressions) * 1000 if impressions > 0 else 0.0
    d1_cpi: Optional[float] = (cost / retained_d1) if retained_d1 > 0 else None
    d1_retention = (retained_d1 / installs) * 100 if installs > 0 else 0.0
    d7_roas: Optional[float] = (revenue_d7 / cost) if cost > 0 else None

    return {"d1_ipm": d1_ipm, "d1_cpi": d1_cpi, "d1_retention": d1_retention, "d7_roas": d7_roas}
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/Scripts/python.exe scripts/test_mmp_metrics.py`
Expected: PASS — `✅ test_mmp_metrics 통과`

- [ ] **Step 5: 커밋**

```bash
git add pipeline/mmp_metrics.py scripts/test_mmp_metrics.py
git commit -m "[Stage 7-B] mmp_metrics: 집계 + 4 품질지표 (D1 잔존수 분모)"
```

---

## Task 3: airbridge.py — 리포트 응답 파서 (순수 함수, mock fixture)

**Files:**
- Create: `pipeline/sources/airbridge.py` (파서 부분만 — Task 4에서 HTTP 추가)
- Test: `scripts/test_airbridge_parse.py` (신규)

- [ ] **Step 1: 실패 테스트 작성**

`scripts/test_airbridge_parse.py`:
```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python.exe scripts/test_airbridge_parse.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.sources.airbridge'`

- [ ] **Step 3: 파서 구현**

`pipeline/sources/airbridge.py` (HTTP는 Task 4에서 추가; 우선 파서만):
```python
# -*- coding: utf-8 -*-
"""Airbridge MMP Source — Stage 7.

3개 비동기 리포트(Actuals/Revenue/Retention)를 페치→파싱→소재별 CreativeMmpDaily 병합.
HTTP 무의존 파서(parse_*/merge_reports)와 HTTP 클라이언트(AirbridgeMmpSource)를 분리해
파서는 mock fixture로 단위 검증한다.

⚠️ 리포트 응답 JSON key 명은 7-A 1건 실호출로 최종 확인 — parse_* 만 소폭 조정 가능.
레퍼런스: https://help.airbridge.io/en/references/actuals-report
"""
from __future__ import annotations

from typing import Iterable, Optional

from ..schemas import CreativeMmpDaily


def _gb(row: dict) -> tuple[str, str, str]:
    """row 의 groupBy 에서 (creative, channel, date) 추출."""
    g = row.get("groupBy", {})
    return g.get("ad_creative", ""), g.get("channel", ""), g.get("event_date", "")


def parse_actuals(result: dict, exclude_channels: set) -> list[dict]:
    """Actuals 결과 → [{creative, channel, date, impressions, clicks, cost, installs}] (제외채널 필터)."""
    out = []
    for row in result.get("rows", []):
        creative, channel, date = _gb(row)
        if not creative or channel in exclude_channels:
            continue
        m = row.get("metrics", {})
        out.append({
            "creative": creative, "channel": channel, "date": date,
            "impressions": int(m.get("impressions", 0) or 0),
            "clicks": int(m.get("clicks", 0) or 0),
            "cost": int(round(float(m.get("cost", 0) or 0))),
            "installs": int(m.get("app_installs", 0) or 0),
        })
    return out


def parse_retention(result: dict, exclude_channels: set) -> dict:
    """Retention 결과 → {(creative,channel,date): (installs_interval0, retained_d1_interval1)}."""
    out = {}
    for row in result.get("rows", []):
        creative, channel, date = _gb(row)
        if not creative or channel in exclude_channels:
            continue
        intervals = row.get("intervals", []) or []
        installs = int(intervals[0]) if len(intervals) > 0 else 0
        retained_d1 = int(intervals[1]) if len(intervals) > 1 else 0
        out[(creative, channel, date)] = (installs, retained_d1)
    return out


def parse_revenue(result: dict, exclude_channels: set) -> dict:
    """Revenue 결과 → {(creative,channel,date): revenue_d7}. app_revenue(cumulative D7)."""
    out = {}
    for row in result.get("rows", []):
        creative, channel, date = _gb(row)
        if not creative or channel in exclude_channels:
            continue
        m = row.get("metrics", {})
        out[(creative, channel, date)] = int(round(float(m.get("app_revenue", 0) or 0)))
    return out


def merge_reports(actuals: list[dict], retention: dict, revenue: dict) -> list[CreativeMmpDaily]:
    """3 리포트를 (creative,channel,date) 키로 병합 → CreativeMmpDaily 리스트.

    Actuals 가 기준(노출/비용/설치). retention/revenue 는 코호트 기준이라 같은 키로 left-join.
    Retention 미지원(소재 단위 불가) 시 dict 비어 retained_d1=installs_actuals 못 쓰고 0 →
    해당 지표는 산출 시 None/0 처리(스펙 R1: 가용 지표만).
    """
    out = []
    for a in actuals:
        key = (a["creative"], a["channel"], a["date"])
        ret_installs, retained_d1 = retention.get(key, (0, 0))
        # 설치수 base 는 Retention interval-0 우선, 없으면 Actuals app_installs
        installs = ret_installs if ret_installs > 0 else a["installs"]
        out.append(CreativeMmpDaily(
            creative_name=a["creative"], date=a["date"], channel=a["channel"],
            impressions=a["impressions"], clicks=a["clicks"], cost=a["cost"],
            installs=installs, retained_d1=retained_d1,
            revenue_d7=revenue.get(key, 0),
        ))
    return out
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/Scripts/python.exe scripts/test_airbridge_parse.py`
Expected: PASS — `✅ test_airbridge_parse 통과`

- [ ] **Step 5: 커밋**

```bash
git add pipeline/sources/airbridge.py scripts/test_airbridge_parse.py
git commit -m "[Stage 7-B] airbridge: 리포트 파서 + 병합 (非Google 필터)"
```

---

## Task 4: airbridge.py — HTTP 클라이언트 (POST+폴링, from_env, auth_check, fetch_mmp_window)

**Files:**
- Modify: `pipeline/sources/airbridge.py` (파일 상단에 클래스 추가)
- Test: `scripts/test_airbridge_client.py` (신규 — `requests` 를 monkeypatch 한 가짜 세션)

- [ ] **Step 1: 실패 테스트 작성**

`scripts/test_airbridge_client.py`:
```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python.exe scripts/test_airbridge_client.py`
Expected: FAIL — `AttributeError: module 'pipeline.sources.airbridge' has no attribute 'AirbridgeMmpSource'`

- [ ] **Step 3: 클라이언트 구현**

`pipeline/sources/airbridge.py` 파일 **상단**(`from ..schemas import CreativeMmpDaily` 직후)에 추가:
```python
import os
import sys
import time
from datetime import date, timedelta

import requests

from ..base_errors import AuthError, QuotaError  # ← Task 4 Step 3b 참조

API_BASE = "https://api.airbridge.io/reports/api"
REPORT_VERSIONS = {"actuals": "v7", "revenue": "v3", "retention": "v5"}
RETENTION_MAX_DAYS = 92


class AirbridgeMmpSource:
    """Airbridge 3 리포트 비동기 페치 → CreativeMmpDaily 병합. (KpiSource ABC 미상속 — 반환형 상이)"""

    def __init__(self, token: str, app_name: str, session=None,
                 poll_interval_sec: float = 3.0, poll_timeout_sec: float = 180.0):
        self.token = token
        self.app_name = app_name
        self.session = session or requests.Session()
        self.poll_interval_sec = poll_interval_sec
        self.poll_timeout_sec = poll_timeout_sec

    @classmethod
    def from_env(cls) -> "AirbridgeMmpSource":
        token = os.environ.get("AIRBRIDGE_API_TOKEN", "").strip()
        app = os.environ.get("AIRBRIDGE_APP_NAME", "").strip()
        if not token or not app:
            raise FileNotFoundError(
                "AIRBRIDGE_API_TOKEN / AIRBRIDGE_APP_NAME 미설정. "
                ".env 에 추가하세요 (Airbridge 대시보드 Settings>Tokens)."
            )
        return cls(token=token, app_name=app)

    def source_name(self) -> str:
        return "airbridge"

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def _url(self, report_path: str) -> str:
        # report_path 예: "actuals/query" → 버전 prefix 자동
        report = report_path.split("/")[0]
        ver = REPORT_VERSIONS.get(report, "v7")
        return f"{API_BASE}/{ver}/apps/{self.app_name}/{report_path}"

    def _create_and_poll(self, report_path: str, body: dict) -> dict:
        """POST 로 리포트 생성 → taskId → GET 폴링 → SUCCESS 결과 반환."""
        try:
            resp = self.session.post(self._url(report_path), json=body, headers=self._headers(), timeout=30)
            resp.raise_for_status()
        except Exception as e:
            self._raise_classified(e)
        task_id = (resp.json().get("task") or {}).get("id")
        if not task_id:
            raise RuntimeError(f"Airbridge 리포트 생성 응답에 task.id 없음: {resp.json()}")

        poll_url = f"{self._url(report_path)}/{task_id}"
        waited = 0.0
        while waited <= self.poll_timeout_sec:
            try:
                g = self.session.get(poll_url, headers=self._headers(), timeout=30)
                g.raise_for_status()
            except Exception as e:
                self._raise_classified(e)
            payload = g.json()
            status = (payload.get("task") or {}).get("status", "")
            if status == "SUCCESS":
                return payload
            if status in ("FAILURE", "CANCELED"):
                raise RuntimeError(f"Airbridge 리포트 실패: status={status}")
            time.sleep(self.poll_interval_sec)
            waited += self.poll_interval_sec
        raise RuntimeError(f"Airbridge 리포트 폴링 타임아웃 ({self.poll_timeout_sec}s)")

    @staticmethod
    def _raise_classified(e: Exception):
        msg = str(e).lower()
        if "401" in msg or "403" in msg or "unauthorized" in msg:
            raise AuthError(f"Airbridge 인증 실패: {e}")
        if "429" in msg or "too many" in msg:
            raise QuotaError(f"Airbridge rate limit: {e}")
        raise RuntimeError(f"Airbridge HTTP 오류: {e}")

    def auth_check(self) -> bool:
        """cheap call — 최근 1일 Actuals 1행 요청으로 인증·앱 접근 검증."""
        end = date.today() - timedelta(days=1)
        body = {"from": end.isoformat(), "to": end.isoformat(),
                "groupBys": ["event_date"], "metrics": ["impressions"], "filters": [], "sorts": []}
        try:
            self._create_and_poll("actuals/query", body)
            print(f"[airbridge.auth_check] OK (app={self.app_name})", file=sys.stderr)
            return True
        except Exception as e:
            print(f"[airbridge.auth_check] FAIL: {type(e).__name__}: {e}", file=sys.stderr)
            return False
```

- [ ] **Step 3b: 공통 에러 클래스 재배치**

`AuthError`/`QuotaError` 는 현재 `pipeline/sources/base.py` 에 있다. airbridge 가 base(KpiSource ABC)를 import 하면 불필요한 결합이 생기므로, 에러만 별 모듈로 분리한다.

Create `pipeline/base_errors.py`:
```python
# -*- coding: utf-8 -*-
"""매체 소스 공통 예외 (google_ads / airbridge 공용)."""


class AuthError(RuntimeError):
    """OAuth/토큰 인증 실패 (401/403/invalid_grant). batch 전체 중단 대상."""


class QuotaError(RuntimeError):
    """API quota/rate limit 초과. 해당 타이틀만 실패, 다른 타이틀 진행."""
```

Modify `pipeline/sources/base.py` — 기존 `class AuthError`/`class QuotaError` 정의를 **삭제**하고 상단 import 로 교체:
```python
from ..base_errors import AuthError, QuotaError  # re-export (기존 import 경로 호환)
```
(google_ads.py 의 `from .base import AuthError, QuotaError` 는 base 가 re-export 하므로 무변경.)

- [ ] **Step 4: 통과 확인**

Run: `.venv/Scripts/python.exe scripts/test_airbridge_client.py`
그 다음 회귀: `.venv/Scripts/python.exe -c "from pipeline.sources.google_ads import GoogleAdsKpiSource; from pipeline.sources.base import AuthError; print('import OK')"`
Expected: 둘 다 PASS (`✅ test_airbridge_client 통과`, `import OK`)

- [ ] **Step 5: 커밋**

```bash
git add pipeline/sources/airbridge.py pipeline/base_errors.py pipeline/sources/base.py scripts/test_airbridge_client.py
git commit -m "[Stage 7-B] airbridge: HTTP 비동기 폴링 클라이언트 + 공통 에러 분리"
```

---

## Task 5: airbridge.py — fetch_mmp_window 오케스트레이션 + metadata 검증

**Files:**
- Modify: `pipeline/sources/airbridge.py` (AirbridgeMmpSource 에 메서드 추가)
- Test: `scripts/test_airbridge_window.py` (신규 — FakeSession 으로 3 리포트 응답 분기)

- [ ] **Step 1: 실패 테스트 작성**

`scripts/test_airbridge_window.py`:
```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python.exe scripts/test_airbridge_window.py`
Expected: FAIL — `AttributeError: 'AirbridgeMmpSource' object has no attribute 'fetch_mmp_window'`

- [ ] **Step 3: 구현**

`AirbridgeMmpSource` 클래스에 메서드 추가:
```python
    def _date_chunks(self, start: date, end: date, max_days: int):
        cur = start
        while cur <= end:
            chunk_end = min(end, cur + timedelta(days=max_days - 1))
            yield cur, chunk_end
            cur = chunk_end + timedelta(days=1)

    def _actuals_body(self, start, end):
        return {"from": start.isoformat(), "to": end.isoformat(),
                "groupBys": ["ad_creative", "channel", "event_date"],
                "metrics": ["impressions", "clicks", "cost", "app_installs"], "filters": [], "sorts": []}

    def _retention_body(self, start, end):
        return {"from": start.isoformat(), "to": end.isoformat(), "granularity": "day",
                "intervalsPeriod": 1, "groupBy": {"fields": ["ad_creative", "channel", "event_date"]},
                "startEvents": ["app_install"], "returnEvents": ["app_open"],
                "measurementOption": "general_retention"}

    def _revenue_body(self, start, end):
        return {"from": start.isoformat(), "to": end.isoformat(), "granularity": "day",
                "groupBy": {"fields": ["ad_creative", "channel", "event_date"]},
                "startEvents": ["app_install"], "returnEvents": ["app_order_complete"],
                "metric": "app_revenue", "aggregationType": "cumulative", "intervalsPeriodIndexes": [7]}

    def fetch_mmp_window(self, start: date, end: date,
                         exclude_channels: Optional[set] = None) -> list[CreativeMmpDaily]:
        """3 리포트 페치 → 파싱 → 병합. Retention 은 92일 청크 분할.

        Revenue/Retention 이 ad_creative 미지원이면 해당 dict 가 비어 retained_d1/revenue_d7=0 →
        compute_mmp_quality 에서 None/0 (스펙 R1: 가용 지표만).
        """
        exclude = exclude_channels or set()
        # Actuals (최대 400일 — 통으로)
        actuals: list[dict] = []
        ar = self._create_and_poll("actuals/query", self._actuals_body(start, end))
        actuals.extend(parse_actuals(ar, exclude))
        # Revenue (통으로)
        rev: dict = {}
        try:
            rr = self._create_and_poll("revenue/query", self._revenue_body(start, end))
            rev.update(parse_revenue(rr, exclude))
        except Exception as e:
            print(f"   [airbridge] Revenue 리포트 생략: {e}", file=sys.stderr)
        # Retention (92일 청크)
        ret: dict = {}
        for cs, ce in self._date_chunks(start, end, RETENTION_MAX_DAYS):
            try:
                rt = self._create_and_poll("retention/query", self._retention_body(cs, ce))
                ret.update(parse_retention(rt, exclude))
            except Exception as e:
                print(f"   [airbridge] Retention 청크 {cs}~{ce} 생략: {e}", file=sys.stderr)
        return merge_reports(actuals, ret, rev)

    def fetch_metadata_groupbys(self, report: str) -> list:
        """Get Metadata(GroupBy) — 7-A 에서 ad_creative 지원 확인용. report: actuals|revenue|retention."""
        ver = REPORT_VERSIONS.get(report, "v7")
        url = f"{API_BASE}/{ver}/apps/{self.app_name}/{report}/metadata/groupBys"
        try:
            r = self.session.get(url, headers=self._headers(), timeout=30)
            r.raise_for_status()
            data = r.json()
            return data.get("groupBys", data.get("data", []))
        except Exception as e:
            print(f"[airbridge.metadata] {report} 실패: {e}", file=sys.stderr)
            return []
```

(`Optional` 은 파일 상단 `from typing import Iterable, Optional` 에 이미 포함.)

- [ ] **Step 4: 통과 확인**

Run: `.venv/Scripts/python.exe scripts/test_airbridge_window.py`
Expected: PASS — `✅ test_airbridge_window 통과`

- [ ] **Step 5: 커밋**

```bash
git add pipeline/sources/airbridge.py scripts/test_airbridge_window.py
git commit -m "[Stage 7-B] airbridge: fetch_mmp_window 3리포트 오케스트레이션 + 92일 청크 + metadata"
```

---

## Task 6: mmp.py CLI — healthcheck / metadata-check / dry-run / fetch

**Files:**
- Create: `pipeline/mmp.py`
- Test: 수동 (`--metadata-check` 는 실토큰 필요 — 7-A). 본 Task 는 dry-run 경로를 standalone 으로 검증.
- Test: `scripts/test_mmp_cli_dryrun.py` (신규)

- [ ] **Step 1: 실패 테스트 작성**

`scripts/test_mmp_cli_dryrun.py`:
```python
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
```

- [ ] **Step 2: 실패 확인 → 통과 확인**

Run: `.venv/Scripts/python.exe scripts/test_mmp_cli_dryrun.py`
Expected: PASS (Task 5 에서 메서드 이미 구현됨 — 이 테스트는 바디 스펙 회귀 가드).

- [ ] **Step 3: CLI 구현**

`pipeline/mmp.py` (kpi.py 패턴 미러):
```python
# -*- coding: utf-8 -*-
"""MMP(Airbridge) 검증용 CLI — Stage 7.

  python -m pipeline.mmp --healthcheck                  # 토큰·앱 접근 검증
  python -m pipeline.mmp --metadata-check               # 7-A: ad_creative groupBy 지원 확인
  python -m pipeline.mmp --title pepp-us --days 30 --dry-run   # 호출 바디만 출력
  python -m pipeline.mmp --title pepp-us --days 30      # 실 페치 + 소재별 4지표 출력
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv


def _exclude_channels() -> set:
    import os
    raw = os.environ.get("AIRBRIDGE_EXCLUDE_CHANNELS", "googleadwords,Google Ads")
    return {c.strip() for c in raw.split(",") if c.strip()}


def cmd_healthcheck() -> int:
    print("🔍 Airbridge API healthcheck...")
    try:
        from .sources.airbridge import AirbridgeMmpSource
        src = AirbridgeMmpSource.from_env()
    except Exception as e:
        print(f"❌ 초기화 실패: {type(e).__name__}: {e}")
        return 1
    if src.auth_check():
        print(f"✅ Airbridge 인증 OK (app={src.app_name}) → Stage 7-B 진입 조건 충족")
        return 0
    print("❌ 인증 실패. .env 의 AIRBRIDGE_API_TOKEN / AIRBRIDGE_APP_NAME 확인.")
    return 1


def cmd_metadata_check() -> int:
    """7-A 핵심: Revenue·Retention 의 ad_creative groupBy 지원 확인."""
    from .sources.airbridge import AirbridgeMmpSource
    try:
        src = AirbridgeMmpSource.from_env()
    except Exception as e:
        print(f"❌ 초기화 실패: {e}")
        return 1
    print("🔍 ad_creative groupBy 지원 검증 (스펙 R1):")
    ok_all = True
    for report in ("actuals", "revenue", "retention"):
        gbs = src.fetch_metadata_groupbys(report)
        names = {(g.get("name") or g) if isinstance(g, dict) else g for g in gbs}
        supported = "ad_creative" in names
        mark = "✅" if supported else "⚠️ 미지원 → 해당 지표 소재단위 생략"
        print(f"   {report:<10}: ad_creative {mark}")
        if not supported:
            ok_all = False
    print("\n" + ("✅ 3 리포트 전부 소재 단위 지원 — 4지표 전부 산출 가능"
                  if ok_all else "⚠️ 일부 미지원 — 가용 지표만으로 분석(스펙 R1 합의대로)"))
    return 0


def _resolve_title(title_id: str) -> dict:
    path = Path("js/titles.json")
    titles = json.loads(path.read_text(encoding="utf-8"))
    m = next((t for t in titles if t.get("id") == title_id), None)
    if not m:
        sys.exit(f"❌ titles.json 에 title='{title_id}' 없음")
    return m


def cmd_fetch(args) -> int:
    from .sources.airbridge import AirbridgeMmpSource
    from .mmp_metrics import aggregate_creative_mmp, compute_mmp_quality

    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=args.days - 1)
    if args.dry_run:
        src = AirbridgeMmpSource(token="(dry)", app_name="(dry)", session=object())
        print(f"🔍 [DRY-RUN] {start} ~ {end} 호출 바디:")
        print("\n[Actuals]\n", json.dumps(src._actuals_body(start, end), ensure_ascii=False, indent=2))
        print("\n[Revenue]\n", json.dumps(src._revenue_body(start, end), ensure_ascii=False, indent=2))
        print("\n[Retention]\n", json.dumps(src._retention_body(start, end), ensure_ascii=False, indent=2))
        print("\n✅ 실 호출 안 함.")
        return 0

    try:
        src = AirbridgeMmpSource.from_env()
    except Exception as e:
        print(f"❌ 초기화 실패: {e}")
        return 1
    print(f"🔍 Airbridge fetch — app={src.app_name}, {start} ~ {end} (비-Google 매체)")
    daily = src.fetch_mmp_window(start, end, exclude_channels=_exclude_channels())
    if not daily:
        print("⚠️ 0행. 토큰/앱/기간/채널필터 확인 (pepp 가 非Google 집행 없었을 수 있음).")
        return 0
    agg = aggregate_creative_mmp(daily)
    items = sorted(agg.items(), key=lambda x: -(x[1]["retained_d1"]))
    if args.limit > 0:
        items = items[: args.limit]
    print(f"\n📊 {len(daily)}행, {len(agg)}개 소재")
    print(f"{'소재명':<44}|{'D1잔존':>7}|{'D1IPM':>7}|{'D1CPI':>9}|{'D7ROAS':>7}|{'D1Ret%':>7}")
    print("-" * 90)
    for name, a in items:
        q = compute_mmp_quality(a)
        cpi = f"{q['d1_cpi']:.0f}" if q["d1_cpi"] is not None else "—"
        roas = f"{q['d7_roas']:.2f}" if q["d7_roas"] is not None else "—"
        print(f"{name[:42]:<44}|{a['retained_d1']:>7,}|{q['d1_ipm']:>7.2f}|{cpi:>9}|{roas:>7}|{q['d1_retention']:>7.1f}")
    print("\n✅ 검증 완료. main.py 통합 시 같은 값이 public/data/{title}.json 의 mmp_* 에 주입됩니다.")
    return 0


def main() -> None:
    load_dotenv()
    p = argparse.ArgumentParser(prog="python -m pipeline.mmp", description="Airbridge MMP 검증 CLI (Stage 7)")
    p.add_argument("--healthcheck", action="store_true")
    p.add_argument("--metadata-check", action="store_true")
    p.add_argument("--title", default=None)
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if args.healthcheck:
        sys.exit(cmd_healthcheck())
    if args.metadata_check:
        sys.exit(cmd_metadata_check())
    sys.exit(cmd_fetch(args))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 컴파일 + dry-run 확인**

Run: `.venv/Scripts/python.exe -m py_compile pipeline/mmp.py && .venv/Scripts/python.exe -m pipeline.mmp --title pepp-us --days 30 --dry-run`
Expected: 3개 리포트 바디 JSON 출력 + `✅ 실 호출 안 함.` (토큰 불필요)

- [ ] **Step 5: 커밋**

```bash
git add pipeline/mmp.py scripts/test_mmp_cli_dryrun.py
git commit -m "[Stage 7-B] mmp.py CLI — healthcheck/metadata-check/dry-run/fetch"
```

---

## Task 7: main.py 통합 — Airbridge 페치 + 소재명 join + mmp_* 주입

**Files:**
- Modify: `pipeline/main.py` (KPI fetch/join 블록 직후 ~L458 `metrics["kpi_status"] = kpi_status` 다음)
- Modify: `pipeline/main.py` (`resolve_config` — airbridge 설정 로드)
- Test: `scripts/test_main_mmp_inject.py` (신규 — 가짜 source 주입)

- [ ] **Step 1: 실패 테스트 작성**

`scripts/test_main_mmp_inject.py`:
```python
# -*- coding: utf-8 -*-
"""main.py 의 mmp 주입 헬퍼(_inject_mmp) 단위 검증 (실 API 무의존)."""
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
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python.exe scripts/test_main_mmp_inject.py`
Expected: FAIL — `ImportError: cannot import name 'inject_mmp_into_records'`

- [ ] **Step 3: 주입 헬퍼 구현**

`pipeline/main.py` 상단 import 에 추가:
```python
from .mmp_metrics import aggregate_creative_mmp, compute_mmp_quality
```

`pipeline/main.py` 에 모듈 레벨 함수 추가 (run 함수 밖, `filename_to_concept` 근처):
```python
def inject_mmp_into_records(records, mmp_daily, source_name="airbridge"):
    """CreativeMmpDaily 리스트를 소재명(concept)으로 join 하여 records 에 mmp_* 주입.

    소재명 매칭: Airbridge ad_creative == 파일명/소재명 컨벤션. concept(폴더명) 기준 join.
    """
    if not mmp_daily:
        return
    # concept(폴더명) 기준 그룹 — Google Ads join 과 동일 키
    by_concept: dict[str, list] = {}
    for d in mmp_daily:
        concept = filename_to_concept(d.creative_name) or d.creative_name.rsplit(".", 1)[0]
        by_concept.setdefault(concept, []).append(d)

    for r in records:
        rows = by_concept.get(r.creative_id) or by_concept.get(r.소재명)
        if not rows:
            continue
        agg = aggregate_creative_mmp(rows)
        # 한 소재만 들어있는 agg — 첫 값
        a = next(iter(agg.values()))
        q = compute_mmp_quality(a)
        r.mmp_source = source_name
        r.mmp_channels = sorted(a["channels"])
        r.mmp_d1_ipm = round(q["d1_ipm"], 3)
        r.mmp_d1_cpi = None if q["d1_cpi"] is None else round(q["d1_cpi"], 1)
        r.mmp_d7_roas = None if q["d7_roas"] is None else round(q["d7_roas"], 4)
        r.mmp_d1_retention = round(q["d1_retention"], 2)
        r.mmp_installs = a["installs"]
        r.mmp_retained_d1 = a["retained_d1"]
        r.mmp_cost = a["cost"]
        r.mmp_revenue = a["revenue_d7"]
        r.mmp_daily = rows
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/Scripts/python.exe scripts/test_main_mmp_inject.py`
Expected: PASS — `✅ test_main_mmp_inject 통과`

- [ ] **Step 5: main.py 페치 블록 배선**

`pipeline/main.py` 의 `metrics["kpi_status"] = kpi_status` (약 L458) **직후**에 삽입:
```python
    # ── 2.6) Stage 7: Airbridge MMP 페치 (非Google 매체 품질 레이어) ──
    mmp_status = "skipped"
    if cfg.get("airbridge_enabled"):
        try:
            from .sources.airbridge import AirbridgeMmpSource
            from datetime import date as _date, timedelta as _td
            mmp_src = AirbridgeMmpSource.from_env()
            _end = _date.today() - _td(days=1)
            _start = _end - _td(days=cfg.get("kpi_window_days", 159) - 1)
            mmp_daily = mmp_src.fetch_mmp_window(
                _start, _end, exclude_channels=set(cfg.get("airbridge_exclude_channels", [])))
            inject_mmp_into_records(records_will_be=None, mmp_daily=mmp_daily) if False else None
            cfg["_mmp_daily"] = mmp_daily   # 레코드 생성 후 주입 (records 는 아래 루프에서 생성됨)
            mmp_status = "success"
            metrics["mmp_rows_fetched"] = len(mmp_daily)
            print(f"   → Airbridge {len(mmp_daily)}행 fetch (非Google 매체)")
        except Exception as e:
            err_type = type(e).__name__
            print(f"\n⚠️  MMP fetch 실패 ({err_type}): {e} → mmp_* 비움, 진행 계속")
            metrics["errors"].append(f"MMP fetch 실패: {e}")
            mmp_status = "auth_failed" if err_type == "AuthError" else "failed"
    metrics["mmp_status"] = mmp_status
```

그리고 `records.append(record)` 루프 종료 후, **Stage 6 점수 산출 블록 직전**에 주입 호출 삽입:
```python
    # Stage 7: 페치해둔 MMP daily 를 records 에 주입 (소재명 join)
    if cfg.get("_mmp_daily"):
        inject_mmp_into_records(records, cfg["_mmp_daily"], source_name="airbridge")
```

- [ ] **Step 6: resolve_config 확장**

`pipeline/main.py` 의 `resolve_config` 에서 titles.json 매니페스트(`matched`)를 읽는 부분에 추가 (google_ads 설정 읽는 근처):
```python
        "airbridge_enabled": bool(matched.get("_pipeline_airbridge_enabled", False)),
        "airbridge_exclude_channels": matched.get("_pipeline_airbridge_exclude_channels",
                                                  ["googleadwords", "Google Ads"]),
```
(단일/배치 두 경로 모두 — Stage 5-D-5 와 동일 위치.)

- [ ] **Step 7: 컴파일 + 회귀**

Run:
```
.venv/Scripts/python.exe -m py_compile pipeline/main.py
.venv/Scripts/python.exe scripts/test_main_mmp_inject.py
.venv/Scripts/python.exe -m pipeline.main --title pepp-us --dry-run
```
Expected: 컴파일 OK + 테스트 PASS + dry-run 정상(60 소재 스캔, MMP 미발동 — dry-run 은 페치 전 종료).

- [ ] **Step 8: 커밋**

```bash
git add pipeline/main.py scripts/test_main_mmp_inject.py
git commit -m "[Stage 7-B] main.py: Airbridge 페치 + 소재명 join + mmp_* 주입 (graceful)"
```

---

## Task 8: 설정 — titles.json + .env.example

**Files:**
- Modify: `js/titles.json` (pepp-us 항목)
- Modify: `.env.example`

- [ ] **Step 1: titles.json pepp-us 에 Airbridge 필드 추가**

`js/titles.json` 의 `"id": "pepp-us"` 객체에 추가 (`_pipeline_kpi_enabled` 근처):
```json
    "_pipeline_airbridge_enabled": true,
    "_pipeline_airbridge_exclude_channels": ["googleadwords", "Google Ads"]
```
(app_name/token 은 .env 에 — 타이틀별 분리 필요 시 차기 `_pipeline_airbridge_app_name` 추가)

- [ ] **Step 2: .env.example 에 AIRBRIDGE 블록 추가**

`.env.example` 끝(SMTP 블록 패턴 모방)에 추가:
```
# ─────────────────────────────────────────────
# Stage 7: Airbridge MMP (소재 품질 레이어 — 非Google 매체)
# Airbridge 대시보드 [Settings] > [Tokens] 에서 발급
# ─────────────────────────────────────────────
AIRBRIDGE_API_TOKEN=
AIRBRIDGE_APP_NAME=
# 제외할 채널(Google Ads 중복 방지) — 쉼표 구분. metadata-check 로 실제 표기명 확인
AIRBRIDGE_EXCLUDE_CHANNELS=googleadwords,Google Ads
```

- [ ] **Step 3: JSON 유효성 확인**

Run: `.venv/Scripts/python.exe -c "import json; json.load(open('js/titles.json', encoding='utf-8')); print('titles.json OK')"`
Expected: `titles.json OK`

- [ ] **Step 4: 커밋**

```bash
git add js/titles.json .env.example
git commit -m "[Stage 7-B] 설정: titles.json airbridge 필드 + .env.example AIRBRIDGE 블록"
```

---

## Task 9 (phase-2): 품질 종합점수

**Files:**
- Modify: `pipeline/mmp_metrics.py` (compute_mmp_quality_scores 추가)
- Modify: `pipeline/main.py` (inject_mmp_into_records 에서 호출)
- Test: `scripts/test_mmp_score.py` (신규)

- [ ] **Step 1: 실패 테스트 작성**

`scripts/test_mmp_score.py`:
```python
# -*- coding: utf-8 -*-
"""MMP 품질 종합점수 — 4지표 rank 종합 (방향: ipm↑ cpi↓ roas↑ retention↑)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.mmp_metrics import compute_mmp_quality_scores

metrics = {
    "A": {"d1_ipm": 5.0, "d1_cpi": 1000.0, "d7_roas": 1.2, "d1_retention": 50.0},
    "B": {"d1_ipm": 2.0, "d1_cpi": 3000.0, "d7_roas": 0.4, "d1_retention": 20.0},
}
scores = compute_mmp_quality_scores(metrics)
# A 가 전 지표 우월 → A.total > B.total, A 등급 최우수
assert scores["A"]["total"] > scores["B"]["total"]
assert scores["A"]["rank"] == 1 and scores["B"]["rank"] == 2
print("✅ test_mmp_score 통과")
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python.exe scripts/test_mmp_score.py`
Expected: FAIL — `ImportError: cannot import name 'compute_mmp_quality_scores'`

- [ ] **Step 3: 구현 (scoring.py rank 헬퍼 재사용)**

`pipeline/mmp_metrics.py` 에 추가:
```python
from .scoring import _assign_rank_with_ties


def compute_mmp_quality_scores(metrics_by_creative: dict) -> dict:
    """소재별 4지표 dict → 품질 종합점수 {total, grade, rank, ipm/cpi/roas/retention 점수}.

    4지표 균등 25%. None 지표는 해당 축 점수 0(최하). rank 점수 = (n-rank+1)/n×100.
    방향: d1_ipm↑, d1_cpi↓, d7_roas↑, d1_retention↑.
    """
    keys = list(metrics_by_creative.keys())
    n = len(keys)
    if n == 0:
        return {}
    items = [{"key": k, **metrics_by_creative[k]} for k in keys]

    def rank_score(field: str, higher_better: bool):
        # None 은 최하위로: higher_better 면 -inf, 아니면 +inf
        def val(it):
            v = it.get(field)
            if v is None:
                return float("-inf") if higher_better else float("inf")
            return v
        ordered = sorted(items, key=val, reverse=higher_better)
        _assign_rank_with_ties(ordered, val)
        for it in ordered:
            none_v = it.get(field) is None
            it[f"_s_{field}"] = 0.0 if none_v else ((n - it["_assignedRank"] + 1) / n) * 100

    rank_score("d1_ipm", True)
    rank_score("d1_cpi", False)
    rank_score("d7_roas", True)
    rank_score("d1_retention", True)

    for it in items:
        it["_total"] = (it["_s_d1_ipm"] + it["_s_d1_cpi"] + it["_s_d7_roas"] + it["_s_d1_retention"]) / 4

    ranked = sorted(items, key=lambda it: it["_total"], reverse=True)
    out = {}
    for i, it in enumerate(ranked):
        t = it["_total"]
        grade = ("최우수" if t >= 80 else "우수" if t >= 60 else "양호" if t >= 40 else "보통" if t >= 20 else "개선필요")
        out[it["key"]] = {
            "total": round(t, 2), "grade": grade, "rank": i + 1,
            "ipm": round(it["_s_d1_ipm"], 1), "cpi": round(it["_s_d1_cpi"], 1),
            "roas": round(it["_s_d7_roas"], 1), "retention": round(it["_s_d1_retention"], 1),
        }
    return out
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/Scripts/python.exe scripts/test_mmp_score.py`
Expected: PASS — `✅ test_mmp_score 통과`

- [ ] **Step 5: main.py 에서 종합점수 주입**

`inject_mmp_into_records` 의 per-record 루프 **후**(함수 끝)에 추가:
```python
    # phase-2: 4지표 보유 소재들로 품질 종합점수 산출 후 주입
    scored_metrics = {
        r.creative_id: {"d1_ipm": r.mmp_d1_ipm, "d1_cpi": r.mmp_d1_cpi,
                        "d7_roas": r.mmp_d7_roas, "d1_retention": r.mmp_d1_retention}
        for r in records if r.mmp_source
    }
    if scored_metrics:
        from .mmp_metrics import compute_mmp_quality_scores
        qscores = compute_mmp_quality_scores(scored_metrics)
        for r in records:
            if r.creative_id in qscores:
                r.mmp_quality_score = qscores[r.creative_id]
```

- [ ] **Step 6: 통과 확인 + 커밋**

Run: `.venv/Scripts/python.exe scripts/test_mmp_score.py && .venv/Scripts/python.exe scripts/test_main_mmp_inject.py`
Expected: 둘 다 PASS
```bash
git add pipeline/mmp_metrics.py pipeline/main.py scripts/test_mmp_score.py
git commit -m "[Stage 7-B phase-2] MMP 품질 종합점수 (4지표 rank 종합)"
```

---

## 자체검토 (Self-Review)

**스펙 커버리지:**
- §3 지표 정의(D1 잔존수 분모) → Task 2 (`compute_mmp_quality`) ✅ — 정확히 D1 IPM=잔존/노출×1000, CPI=비용/잔존, Retention=잔존/설치, D7 ROAS=매출/비용
- §4 아키텍처(3리포트 병합, 非Google 필터) → Task 3·5 ✅
- §5 API 사양(비동기 폴링, 92일 청크) → Task 4·5 ✅
- §6 스키마 → Task 1 ✅
- §7 main.py 통합 → Task 7 ✅
- §9 서브스테이지: 7-A → Prerequisite + Task 6 `--metadata-check`; 7-B → Task 1~9; 7-C(대시보드)·7-D(자동화·E2E) → **별도 후속 계획**(본 계획 범위 외, 명시)
- 종합점수(7-B phase-2) → Task 9 ✅
- R1(ad_creative 미지원) → 가용 지표만(merge_reports 의 빈 dict → None/0), Task 6 검증 ✅
- R2(92일) → Task 5 `_date_chunks` ✅

**Placeholder 스캔:** 없음 — 전 Step 실제 코드·명령·기대출력 포함.

**타입 일관성:** `CreativeMmpDaily`(creative_name·date·channel·impressions·clicks·cost·installs·retained_d1·revenue_d7) — Task 1/3/5/7 동일. `compute_mmp_quality` 반환 키(d1_ipm·d1_cpi·d1_retention·d7_roas) — Task 2/6/7/9 동일. `aggregate_creative_mmp` 반환 키(impressions·cost·installs·retained_d1·revenue_d7·channels) — Task 2/7 동일. `AuthError`/`QuotaError` — base_errors 단일 출처, base.py re-export(google_ads 호환).

**주의(실행 시 확인):** Task 7 Step 5 의 페치 블록은 `cfg["_mmp_daily"]` 에 저장 후 records 생성 후 주입하는 2-단계 — `resolve_config` 가 단일/배치 양 경로에서 airbridge 키를 넣는지 확인. `kpi_window_days` 기본값은 pepp 의 titles.json `_pipeline_google_ads_window_days`(159)와 정합 확인.

## 범위 밖 (후속 계획)

- **7-C (대시보드 "소재 품질" 레이어)**: `step1_integrated.html` 모달 섹션 + 결과표 MMP 컬럼 + `data-source.js` 패스스루. mmp_* 데이터가 JSON 에 생긴 뒤 별도 계획.
- **7-D (자동화·E2E)**: nightly 통합(main.py 에 이미 배선되어 자동 포함) + notify.py mmp_status 표면화 + Airbridge UI 1:1 검증.
- **AppsFlyer 소스**: 공통 ABC 추출 후 동일 패턴.

---

## 실행 완료 (2026-06-17, main 머지 87f1323)

서브에이전트 주도(superpowers) 9 태스크 TDD 실행 → 최종 리뷰(opus) → 머지. 11 커밋.

- **신규 파일**: `pipeline/mmp_metrics.py`(집계+4지표+종합점수), `pipeline/sources/airbridge.py`(3리포트 비동기 클라+파서), `pipeline/base_errors.py`(공통 예외), `pipeline/mmp.py`(CLI), 테스트 8종(`scripts/test_*`).
- **수정**: `schemas.py`(CreativeMmpDaily+mmp_* 12필드), `main.py`(페치+소재명 join+주입, graceful skip), `sources/base.py`(에러 re-export), `titles.json`/`.env.example`(설정).
- **검증**: 8 단위 테스트 + Stage 6 회귀(verify-scoring) 전부 통과. 전 모듈 컴파일 OK.
- **최종 리뷰 수정**: concept 멀티변형 합산 버그(첫 변형만 반영 → 전체 SUM, `aggregate_rows_total`) + minor 정리. 멀티변형 회귀 테스트 추가.
- **graceful**: 토큰 미설정 시 mmp_status="skipped"(무에러). enabled=true 라 토큰 .env 추가 즉시 자동 활성.

### 잔여(후속)
- **7-A (사용자)**: Airbridge 토큰 발급 → `.env` 기입 → `python -m pipeline.mmp --metadata-check` 로 ad_creative groupBy(R1) 검증 → `--healthcheck`/`--dry-run`/실 fetch.
- **7-C**: 대시보드 "소재 품질(MMP)" 레이어 UI (별도 계획).
- **7-D**: nightly 자동 통합은 main.py 배선으로 자동 포함 — notify.py mmp_status 표면화 + Airbridge UI 1:1 검증만 남음.
- 실 API 응답 key 명은 7-A 1건 실호출 후 `parse_*` 소폭 조정 가능성(문서 caveat).
