# BigQuery Exporter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `public/data/*.json`을 BigQuery 4테이블(kpi_daily·mmp_daily·creatives·axis)에 파티션 교체로 병행 적재하는 decoupled exporter를 만든다. 파이프라인·대시보드 무변경.

**Architecture:** 신규 모듈 `pipeline/bq_export.py` — 파일 스캔 → 순수 행 변환 → (주입된) BQ 클라이언트로 파티션 삭제+로드. nightly git push 뒤 실행. BQ 클라이언트는 인자 주입이라 테스트는 fake로 네트워크 0.

**Tech Stack:** Python 3.12, google-cloud-bigquery, 기존 Pydantic 스키마(pipeline/schemas.py), pytest.

## Global Constraints

- 모든 주석·문서 한국어(코드/식별자 예외). CLAUDE.md.
- 파이프라인(main.py)·대시보드 경로 **무변경**. exporter는 산출 JSON만 읽는다(decoupled).
- 순수 함수와 I/O 분리: 행 변환·스키마·파티션범위 계산은 순수(테스트 대상), BQ 클라이언트는 인자 주입.
- graceful 게이팅: `BQ_EXPORT_ENABLED`≠"1" 또는 키 파일 없음 → 조용히 스킵(로그만), 예외 던지지 말 것.
- 테이블별 독립 try/except — 한 테이블 실패가 나머지 안 막음.
- 파티션 교체: 시계열(kpi/mmp)=행 date min..max 파티션 DELETE 후 load, 스냅샷(creatives/axis)=오늘 snapshot_date 파티션. DELETE는 load job 성공 후.
- 시크릿(.env·.secrets/bq_sa.json) 저장소 유입 금지 — .gitignore 확인.
- 어시스턴트는 라이브 BQ 미실행 — 모든 테스트는 fake client, 네트워크 0.
- 커밋 trailer: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- 데이터셋 이름 등은 env: `BQ_PROJECT`, `BQ_DATASET`(기본 "cloop"), `GOOGLE_APPLICATION_CREDENTIALS`, `BQ_EXPORT_ENABLED`.

---

### Task 1: 설정 로더 + 게이팅

**Files:**
- Create: `pipeline/bq_export.py` (모듈 시작 — config 부분만)
- Test: `tests/test_bq_export.py`

**Interfaces:**
- Produces: `load_bq_config(env: dict | None = None) -> dict | None` — env에서 project/dataset/creds 읽어 dict 반환. `BQ_EXPORT_ENABLED`≠"1"이거나 creds 파일 경로 없음/미존재 → `None`(스킵 신호).

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_bq_export.py
from pipeline.bq_export import load_bq_config

def test_gating_disabled_returns_none():
    assert load_bq_config({}) is None
    assert load_bq_config({"BQ_EXPORT_ENABLED": "0"}) is None

def test_gating_missing_creds_returns_none(tmp_path):
    env = {"BQ_EXPORT_ENABLED": "1", "BQ_PROJECT": "p", "BQ_DATASET": "cloop",
           "GOOGLE_APPLICATION_CREDENTIALS": str(tmp_path / "nope.json")}
    assert load_bq_config(env) is None  # 키 파일 부재

def test_config_ok(tmp_path):
    key = tmp_path / "sa.json"; key.write_text("{}", encoding="utf-8")
    env = {"BQ_EXPORT_ENABLED": "1", "BQ_PROJECT": "proj", "BQ_DATASET": "cloop",
           "GOOGLE_APPLICATION_CREDENTIALS": str(key)}
    cfg = load_bq_config(env)
    assert cfg["project"] == "proj" and cfg["dataset"] == "cloop" and cfg["credentials_path"] == str(key)
```

- [ ] **Step 2: 실행해 실패 확인**

Run: `python -m pytest tests/test_bq_export.py -q`
Expected: FAIL (ModuleNotFoundError / load_bq_config 없음)

- [ ] **Step 3: 구현**

```python
# pipeline/bq_export.py
"""CLOOP JSON → BigQuery 병행 적재 (B안 decoupled exporter).

public/data/{title}.json(+_axis.json)을 읽어 BQ 4테이블에 파티션 교체로 적재.
파이프라인·대시보드 무변경. nightly git push 뒤 실행. 게이팅·격리·graceful.
"""
from __future__ import annotations
import os
from pathlib import Path

DEFAULT_DATASET = "cloop"


def load_bq_config(env: dict | None = None) -> dict | None:
    """env → BQ 설정 dict. 비활성/키부재면 None(스킵). 순수(파일 존재만 확인)."""
    e = env if env is not None else os.environ
    if (e.get("BQ_EXPORT_ENABLED") or "") != "1":
        return None
    creds = e.get("GOOGLE_APPLICATION_CREDENTIALS") or ""
    if not creds or not Path(creds).exists():
        return None
    project = e.get("BQ_PROJECT") or ""
    if not project:
        return None
    return {
        "project": project,
        "dataset": e.get("BQ_DATASET") or DEFAULT_DATASET,
        "credentials_path": creds,
    }
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/test_bq_export.py -q`
Expected: 3 passed

- [ ] **Step 5: 커밋**

```bash
git add pipeline/bq_export.py tests/test_bq_export.py
git commit -m "feat(bq_export): 설정 로더·게이팅

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: 행 변환 (순수) — 4테이블

**Files:**
- Modify: `pipeline/bq_export.py`
- Test: `tests/test_bq_export.py`

**Interfaces:**
- Consumes: dataset dict(=`{title}.json` 파싱), axis dict(=`{title}_axis.json` 파싱), `loaded_at: str`(ISO).
- Produces:
  - `rows_kpi_daily(dataset: dict, loaded_at: str) -> list[dict]`
  - `rows_mmp_daily(dataset: dict, loaded_at: str) -> list[dict]`
  - `rows_creatives(dataset: dict, loaded_at: str) -> list[dict]` (snapshot_date = generated_at 날짜)
  - `rows_axis(axis: dict, title_id: str, loaded_at: str) -> list[dict]` (stages.L/P 평탄화, snapshot_date = generated_at 날짜)

- [ ] **Step 1: 실패 테스트 작성**

```python
from pipeline.bq_export import rows_kpi_daily, rows_mmp_daily, rows_creatives, rows_axis

_DS = {
  "title_id": "zeus", "generated_at": "2026-09-18T13:00:00+09:00",
  "creatives": [
    {"creative_id": "c1", "소재명": "c1", "유형": "BNR",
     "theme_primary": "전투 쾌감", "theme_secondary": ["그래픽·비주얼"],
     "USP": "전략경쟁형", "intent_axis": None, "theme_flags": [],
     "kpi_daily": [
        {"creative_name": "c1", "date": "2026-09-10", "source": "google_ads",
         "customer_id": "123", "campaign_name": "camp", "ad_group_name": "ag",
         "impressions": 100, "clicks": 5, "cost_micros": 2000000, "cost": 2.0,
         "conversions": 1.0, "conversions_value": 10.0, "asset_url": None,
         "asset_type": None, "asset_id": None}],
     "mmp_daily": [
        {"creative_name": "c1", "date": "2026-09-09", "channel": "Meta",
         "campaign_name": "m", "impressions": 50, "clicks": 3, "cost": 1000,
         "installs": 4, "retained_d1": 2, "revenue_d7": 5000, "conversions": 0}]}]}

def test_rows_kpi_daily():
    r = rows_kpi_daily(_DS, "2026-09-18T04:00:00Z")
    assert len(r) == 1
    row = r[0]
    assert row["title_id"] == "zeus" and row["date"] == "2026-09-10"
    assert row["creative_name"] == "c1" and row["campaign_name"] == "camp"
    assert row["impressions"] == 100 and row["cost"] == 2.0 and row["conversions"] == 1.0
    assert row["loaded_at"] == "2026-09-18T04:00:00Z"

def test_rows_mmp_daily():
    r = rows_mmp_daily(_DS, "2026-09-18T04:00:00Z")
    assert r[0]["channel"] == "Meta" and r[0]["revenue_d7"] == 5000 and r[0]["title_id"] == "zeus"
    assert r[0]["loaded_at"] == "2026-09-18T04:00:00Z"

def test_rows_creatives_snapshot():
    r = rows_creatives(_DS, "2026-09-18T04:00:00Z")
    assert r[0]["title_id"] == "zeus" and r[0]["creative_name"] == "c1"
    assert r[0]["theme_primary"] == "전투 쾌감" and r[0]["snapshot_date"] == "2026-09-18"
    assert r[0]["theme_secondary"] == ["그래픽·비주얼"] and r[0]["core_usp"] == "전략경쟁형"

_AX = {"title": "zeus", "generated_at": "2026-09-14T11:16:10",
       "period": {"from": "2026-08-06", "to": "2026-09-04"},
       "stages": {"L": [{"axis": "전투 쾌감", "status": "검증", "n": 5, "cost": 100,
                         "ipm": 2.1, "cvr": 0.4, "roas7": None, "ga_roas": 3.0,
                         "delta": {"ipm_pct": None}, "reason": ""}],
                  "P": []}}

def test_rows_axis_flatten():
    r = rows_axis(_AX, "zeus", "2026-09-18T04:00:00Z")
    assert len(r) == 1
    assert r[0]["stage"] == "L" and r[0]["axis"] == "전투 쾌감" and r[0]["status"] == "검증"
    assert r[0]["title_id"] == "zeus" and r[0]["snapshot_date"] == "2026-09-14"
    assert r[0]["period_from"] == "2026-08-06" and r[0]["n"] == 5
```

- [ ] **Step 2: 실행해 실패 확인**

Run: `python -m pytest tests/test_bq_export.py -q`
Expected: FAIL (함수 미정의)

- [ ] **Step 3: 구현**

`pipeline/bq_export.py`에 추가:

```python
def _snapshot_date(dataset_or_axis: dict) -> str:
    """generated_at(ISO)에서 날짜(YYYY-MM-DD)만."""
    g = dataset_or_axis.get("generated_at") or ""
    return g[:10] if len(g) >= 10 else ""


def rows_kpi_daily(dataset: dict, loaded_at: str) -> list[dict]:
    tid = dataset.get("title_id", "")
    out = []
    for c in dataset.get("creatives", []) or []:
        for k in c.get("kpi_daily", []) or []:
            out.append({
                "title_id": tid,
                "creative_name": k.get("creative_name", ""),
                "date": k.get("date", ""),
                "source": k.get("source", ""),
                "customer_id": k.get("customer_id", ""),
                "campaign_name": k.get("campaign_name", ""),
                "ad_group_name": k.get("ad_group_name", ""),
                "asset_url": k.get("asset_url"),
                "asset_type": k.get("asset_type"),
                "asset_id": k.get("asset_id"),
                "impressions": k.get("impressions", 0),
                "clicks": k.get("clicks", 0),
                "cost_micros": k.get("cost_micros", 0),
                "cost": k.get("cost", 0.0),
                "conversions": k.get("conversions", 0.0),
                "conversions_value": k.get("conversions_value", 0.0),
                "loaded_at": loaded_at,
            })
    return out


def rows_mmp_daily(dataset: dict, loaded_at: str) -> list[dict]:
    tid = dataset.get("title_id", "")
    out = []
    for c in dataset.get("creatives", []) or []:
        for m in c.get("mmp_daily", []) or []:
            out.append({
                "title_id": tid,
                "creative_name": m.get("creative_name", ""),
                "date": m.get("date", ""),
                "channel": m.get("channel", ""),
                "campaign_name": m.get("campaign_name", ""),
                "impressions": m.get("impressions", 0),
                "clicks": m.get("clicks", 0),
                "cost": m.get("cost", 0),
                "installs": m.get("installs", 0),
                "retained_d1": m.get("retained_d1", 0),
                "revenue_d7": m.get("revenue_d7", 0),
                "conversions": m.get("conversions", 0),
                "loaded_at": loaded_at,
            })
    return out


# creatives 스냅샷 태그 컬럼(성과 제외)
_CREATIVE_COLS = [
    "creative_id", "소재명", "파일명", "유형", "creative_concept",
    "theme_primary", "theme_reviewed", "launch_date_variant", "theme_partner",
    "intent_axis", "hooking_strategy", "art_style", "player_motivation",
    "color_tone", "cta_type", "one_line_insight",
]


def rows_creatives(dataset: dict, loaded_at: str) -> list[dict]:
    tid = dataset.get("title_id", "")
    snap = _snapshot_date(dataset)
    out = []
    for c in dataset.get("creatives", []) or []:
        row = {"title_id": tid, "snapshot_date": snap, "loaded_at": loaded_at,
               "creative_name": c.get("소재명") or c.get("creative_id", "")}
        for col in _CREATIVE_COLS:
            row[col] = c.get(col)
        # 리스트 필드는 REPEATED로 별도 보존
        row["theme_secondary"] = list(c.get("theme_secondary", []) or [])
        row["theme_flags"] = list(c.get("theme_flags", []) or [])
        row["core_usp"] = c.get("USP")  # 스키마상 USP alias → core_usp 컬럼
        out.append(row)
    return out


def rows_axis(axis: dict, title_id: str, loaded_at: str) -> list[dict]:
    snap = _snapshot_date(axis)
    period = axis.get("period", {}) or {}
    out = []
    for stage, arr in (axis.get("stages", {}) or {}).items():
        for a in arr or []:
            delta = a.get("delta", {}) or {}
            out.append({
                "title_id": title_id,
                "snapshot_date": snap,
                "stage": stage,
                "axis": a.get("axis", ""),
                "status": a.get("status", ""),
                "n": a.get("n", 0),
                "cost": a.get("cost", 0),
                "ipm": a.get("ipm"),
                "cvr": a.get("cvr"),
                "roas7": a.get("roas7"),
                "ga_roas": a.get("ga_roas"),
                "delta_ipm_pct": delta.get("ipm_pct"),
                "reason": a.get("reason", ""),
                "period_from": period.get("from", ""),
                "period_to": period.get("to", ""),
                "loaded_at": loaded_at,
            })
    return out
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/test_bq_export.py -q`
Expected: 모두 passed

- [ ] **Step 5: 커밋**

```bash
git add pipeline/bq_export.py tests/test_bq_export.py
git commit -m "feat(bq_export): JSON→행 변환 4테이블(순수)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: BQ 스키마 + 파티션 범위 계산 (순수)

**Files:**
- Modify: `pipeline/bq_export.py`
- Test: `tests/test_bq_export.py`

**Interfaces:**
- Produces:
  - `TABLE_SPECS: dict[str, dict]` — 테이블별 {schema: list[bigquery.SchemaField], partition_field, clustering: list[str]}.
  - `partition_range(rows: list[dict], field: str) -> tuple[str, str] | None` — 행들의 field(min..max). 빈 리스트 None.

- [ ] **Step 1: 실패 테스트**

```python
from pipeline.bq_export import TABLE_SPECS, partition_range

def test_table_specs_present():
    for t in ("kpi_daily", "mmp_daily", "creatives", "axis"):
        spec = TABLE_SPECS[t]
        assert spec["partition_field"] in ("date", "snapshot_date")
        assert isinstance(spec["clustering"], list) and spec["clustering"]
        names = [f.name for f in spec["schema"]]
        assert "title_id" in names and "loaded_at" in names

def test_kpi_schema_has_core_fields():
    names = [f.name for f in TABLE_SPECS["kpi_daily"]["schema"]]
    for n in ("date", "creative_name", "campaign_name", "impressions", "cost", "conversions"):
        assert n in names

def test_partition_range():
    rows = [{"date": "2026-09-10"}, {"date": "2026-08-21"}, {"date": "2026-09-04"}]
    assert partition_range(rows, "date") == ("2026-08-21", "2026-09-10")
    assert partition_range([], "date") is None
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_bq_export.py -q`
Expected: FAIL

- [ ] **Step 3: 구현**

`pipeline/bq_export.py` 상단 import에 추가하고 스펙 정의:

```python
from google.cloud import bigquery

_SF = bigquery.SchemaField

TABLE_SPECS: dict[str, dict] = {
    "kpi_daily": {
        "partition_field": "date",
        "clustering": ["title_id", "creative_name", "campaign_name"],
        "schema": [
            _SF("title_id", "STRING"), _SF("creative_name", "STRING"),
            _SF("date", "DATE"), _SF("source", "STRING"), _SF("customer_id", "STRING"),
            _SF("campaign_name", "STRING"), _SF("ad_group_name", "STRING"),
            _SF("asset_url", "STRING"), _SF("asset_type", "STRING"), _SF("asset_id", "STRING"),
            _SF("impressions", "INT64"), _SF("clicks", "INT64"),
            _SF("cost_micros", "INT64"), _SF("cost", "FLOAT64"),
            _SF("conversions", "FLOAT64"), _SF("conversions_value", "FLOAT64"),
            _SF("loaded_at", "TIMESTAMP"),
        ],
    },
    "mmp_daily": {
        "partition_field": "date",
        "clustering": ["title_id", "channel", "creative_name"],
        "schema": [
            _SF("title_id", "STRING"), _SF("creative_name", "STRING"),
            _SF("date", "DATE"), _SF("channel", "STRING"), _SF("campaign_name", "STRING"),
            _SF("impressions", "INT64"), _SF("clicks", "INT64"), _SF("cost", "INT64"),
            _SF("installs", "INT64"), _SF("retained_d1", "INT64"),
            _SF("revenue_d7", "INT64"), _SF("conversions", "INT64"),
            _SF("loaded_at", "TIMESTAMP"),
        ],
    },
    "creatives": {
        "partition_field": "snapshot_date",
        "clustering": ["title_id", "creative_name"],
        "schema": [
            _SF("title_id", "STRING"), _SF("snapshot_date", "DATE"),
            _SF("creative_name", "STRING"), _SF("creative_id", "STRING"),
            _SF("소재명", "STRING"), _SF("파일명", "STRING"), _SF("유형", "STRING"),
            _SF("creative_concept", "STRING"), _SF("theme_primary", "STRING"),
            _SF("theme_secondary", "STRING", mode="REPEATED"),
            _SF("theme_reviewed", "BOOL"), _SF("launch_date_variant", "BOOL"),
            _SF("theme_partner", "STRING"), _SF("intent_axis", "STRING"),
            _SF("theme_flags", "STRING", mode="REPEATED"), _SF("core_usp", "STRING"),
            _SF("hooking_strategy", "STRING"), _SF("art_style", "STRING"),
            _SF("player_motivation", "STRING"), _SF("color_tone", "STRING"),
            _SF("cta_type", "STRING"), _SF("one_line_insight", "STRING"),
            _SF("loaded_at", "TIMESTAMP"),
        ],
    },
    "axis": {
        "partition_field": "snapshot_date",
        "clustering": ["title_id", "axis"],
        "schema": [
            _SF("title_id", "STRING"), _SF("snapshot_date", "DATE"),
            _SF("stage", "STRING"), _SF("axis", "STRING"), _SF("status", "STRING"),
            _SF("n", "INT64"), _SF("cost", "INT64"),
            _SF("ipm", "FLOAT64"), _SF("cvr", "FLOAT64"), _SF("roas7", "FLOAT64"),
            _SF("ga_roas", "FLOAT64"), _SF("delta_ipm_pct", "FLOAT64"),
            _SF("reason", "STRING"), _SF("period_from", "STRING"), _SF("period_to", "STRING"),
            _SF("loaded_at", "TIMESTAMP"),
        ],
    },
}


def partition_range(rows: list[dict], field: str) -> tuple[str, str] | None:
    """행들의 field 값 min..max. 빈 리스트/빈 값 없으면 None."""
    vals = [r[field] for r in rows if r.get(field)]
    if not vals:
        return None
    return (min(vals), max(vals))
```

주의: cost가 INT64인데 실데이터 int 보장(mmp cost·axis cost는 int, kpi cost는 FLOAT64로 분리). axis `n`/`cost`는 int.

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/test_bq_export.py -q`
Expected: 모두 passed (google-cloud-bigquery 설치 필요 — 없으면 `pip install google-cloud-bigquery` 먼저)

- [ ] **Step 5: 커밋**

```bash
git add pipeline/bq_export.py tests/test_bq_export.py
git commit -m "feat(bq_export): BQ 테이블 스키마·파티션 범위 계산

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: 적재 함수 (파티션 교체, client 주입) + fake 테스트

**Files:**
- Modify: `pipeline/bq_export.py`
- Test: `tests/test_bq_export.py`

**Interfaces:**
- Consumes: bigquery client-호환 객체(주입), TABLE_SPECS, partition_range.
- Produces: `replace_partition(client, dataset: str, table: str, rows: list[dict], *, dry_run=False) -> dict` — 삭제 범위 산정 → (dry_run 아니면) DELETE 실행 → load_table_from_json. 반환 {table, deleted_range, loaded}.

- [ ] **Step 1: 실패 테스트 (fake client)**

```python
from pipeline.bq_export import replace_partition

class _FakeJob:
    def result(self): return None

class _FakeClient:
    def __init__(self): self.queries = []; self.loaded = []
    def query(self, sql, *a, **k): self.queries.append(sql); return _FakeJob()
    def load_table_from_json(self, rows, table_ref, *a, **k):
        self.loaded.append((table_ref, list(rows))); return _FakeJob()

def test_replace_partition_deletes_then_loads():
    fc = _FakeClient()
    rows = [{"date": "2026-09-10", "title_id": "zeus"}, {"date": "2026-08-21", "title_id": "zeus"}]
    res = replace_partition(fc, "cloop", "kpi_daily", rows)
    assert res["deleted_range"] == ("2026-08-21", "2026-09-10")
    assert res["loaded"] == 2
    assert len(fc.queries) == 1 and "DELETE" in fc.queries[0].upper()
    assert "2026-08-21" in fc.queries[0] and "2026-09-10" in fc.queries[0]
    assert len(fc.loaded) == 1 and len(fc.loaded[0][1]) == 2

def test_replace_partition_dry_run_no_write():
    fc = _FakeClient()
    rows = [{"snapshot_date": "2026-09-18", "title_id": "zeus"}]
    res = replace_partition(fc, "cloop", "creatives", rows, dry_run=True)
    assert res["loaded"] == 1 and res["deleted_range"] == ("2026-09-18", "2026-09-18")
    assert fc.queries == [] and fc.loaded == []  # 무쓰기

def test_replace_partition_empty_rows_noop():
    fc = _FakeClient()
    res = replace_partition(fc, "cloop", "kpi_daily", [])
    assert res["loaded"] == 0 and res["deleted_range"] is None
    assert fc.queries == [] and fc.loaded == []
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_bq_export.py -q`
Expected: FAIL

- [ ] **Step 3: 구현**

```python
def replace_partition(client, dataset: str, table: str, rows: list[dict],
                      *, dry_run: bool = False) -> dict:
    """파티션 교체: 행 date/snapshot_date 범위 파티션 삭제 후 재삽입.
    DELETE는 load 직전, 빈 rows면 무동작. client는 주입(테스트 fake 가능)."""
    spec = TABLE_SPECS[table]
    field = spec["partition_field"]
    rng = partition_range(rows, field)
    if rng is None:
        return {"table": table, "deleted_range": None, "loaded": 0}
    if dry_run:
        return {"table": table, "deleted_range": rng, "loaded": len(rows)}
    lo, hi = rng
    table_ref = f"{dataset}.{table}"
    # 창/오늘 파티션만 삭제 — 창 밖 과거 무손상
    del_sql = (f"DELETE FROM `{table_ref}` "
               f"WHERE {field} BETWEEN DATE('{lo}') AND DATE('{hi}')")
    client.query(del_sql).result()
    client.load_table_from_json(rows, table_ref).result()
    return {"table": table, "deleted_range": rng, "loaded": len(rows)}
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/test_bq_export.py -q`
Expected: 모두 passed

- [ ] **Step 5: 커밋**

```bash
git add pipeline/bq_export.py tests/test_bq_export.py
git commit -m "feat(bq_export): 파티션 교체 적재(client 주입·dry-run)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: 테이블 부트스트랩 + CLI 오케스트레이션

**Files:**
- Modify: `pipeline/bq_export.py`
- Test: `tests/test_bq_export.py`

**Interfaces:**
- Produces:
  - `ensure_table(client, dataset, table)` — 데이터셋·테이블 없으면 생성(파티션·클러스터 지정, 멱등).
  - `export_title(client, dataset, title_id, data_dir, loaded_at, *, dry_run=False) -> list[dict]` — {title}.json + {title}_axis.json 읽어 4테이블 replace_partition. 테이블별 try/except.
  - `main(argv=None)` — argparse(`--all-titles`/`--title`/`--dry-run`), load_bq_config 게이팅, client 생성, public/data 스캔.

- [ ] **Step 1: 실패 테스트 (fake client, tmp JSON)**

```python
import json
from pipeline.bq_export import export_title

def test_export_title_all_tables(tmp_path):
    dd = tmp_path; (dd / "zeus.json").write_text(json.dumps(_DS, ensure_ascii=False), encoding="utf-8")
    (dd / "zeus_axis.json").write_text(json.dumps(_AX, ensure_ascii=False), encoding="utf-8")
    fc = _FakeClient()
    res = export_title(fc, "cloop", "zeus", str(dd), "2026-09-18T04:00:00Z", dry_run=True)
    tables = {r["table"] for r in res}
    assert tables == {"kpi_daily", "mmp_daily", "creatives", "axis"}
    # dry_run이라 무쓰기
    assert fc.queries == [] and fc.loaded == []

def test_export_title_missing_axis_ok(tmp_path):
    dd = tmp_path; (dd / "gd.json").write_text(json.dumps({"title_id":"gd","generated_at":"2026-09-18T13:00:00+09:00","creatives":[]}, ensure_ascii=False), encoding="utf-8")
    fc = _FakeClient()
    res = export_title(fc, "cloop", "gd", str(dd), "2026-09-18T04:00:00Z", dry_run=True)
    # axis 파일 없어도 예외 없이 3테이블(빈 kpi/mmp/creatives) 처리
    assert any(r["table"] == "kpi_daily" for r in res)
```
(위 테스트는 `_DS`/`_AX`/`_FakeClient`를 Task 2·4에서 정의한 것 재사용 — 같은 파일 상단으로 이동/공유.)

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_bq_export.py -q`
Expected: FAIL

- [ ] **Step 3: 구현**

```python
import argparse
import glob
import json as _json
import logging
from datetime import datetime, timezone

log = logging.getLogger("bq_export")

_TABLE_ROWS = {
    "kpi_daily": lambda ds, ax, tid, la: rows_kpi_daily(ds, la),
    "mmp_daily": lambda ds, ax, tid, la: rows_mmp_daily(ds, la),
    "creatives": lambda ds, ax, tid, la: rows_creatives(ds, la),
    "axis": lambda ds, ax, tid, la: rows_axis(ax, tid, la) if ax else [],
}


def ensure_table(client, dataset: str, table: str) -> None:
    """데이터셋·테이블 멱등 생성(파티션·클러스터)."""
    spec = TABLE_SPECS[table]
    ds_ref = bigquery.Dataset(f"{client.project}.{dataset}")
    client.create_dataset(ds_ref, exists_ok=True)
    t = bigquery.Table(f"{client.project}.{dataset}.{table}", schema=spec["schema"])
    t.time_partitioning = bigquery.TimePartitioning(field=spec["partition_field"])
    t.clustering_fields = spec["clustering"]
    client.create_table(t, exists_ok=True)


def export_title(client, dataset: str, title_id: str, data_dir: str,
                 loaded_at: str, *, dry_run: bool = False) -> list[dict]:
    """한 타이틀 4테이블 적재. 테이블별 독립 try/except."""
    p = Path(data_dir)
    ds_path = p / f"{title_id}.json"
    if not ds_path.exists():
        log.warning("bq_export: %s 없음 — 스킵", ds_path)
        return []
    ds = _json.loads(ds_path.read_text(encoding="utf-8"))
    ax_path = p / f"{title_id}_axis.json"
    ax = _json.loads(ax_path.read_text(encoding="utf-8")) if ax_path.exists() else None
    results = []
    for table, rowfn in _TABLE_ROWS.items():
        try:
            rows = rowfn(ds, ax, title_id, loaded_at)
            if not dry_run:
                ensure_table(client, dataset, table)
            results.append(replace_partition(client, dataset, table, rows, dry_run=dry_run))
        except Exception as e:  # 테이블 격리 — 하나 실패가 나머지 막지 않음
            log.error("bq_export: %s.%s 실패: %s", title_id, table, e)
            results.append({"table": table, "error": str(e)})
    return results


def _title_ids(data_dir: str) -> list[str]:
    out = []
    for f in glob.glob(str(Path(data_dir) / "*.json")):
        name = Path(f).name
        if name.endswith("_axis.json") or name.endswith(".pilot.json"):
            continue
        out.append(name[:-5])  # .json 제거
    return sorted(out)


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser(description="CLOOP JSON → BigQuery 적재")
    ap.add_argument("--all-titles", action="store_true")
    ap.add_argument("--title", default="")
    ap.add_argument("--data-dir", default="public/data")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    cfg = load_bq_config()
    if cfg is None:
        log.info("bq_export: 비활성(BQ_EXPORT_ENABLED≠1 또는 키 부재) — 스킵")
        return 0

    client = bigquery.Client.from_service_account_json(
        cfg["credentials_path"], project=cfg["project"])
    loaded_at = datetime.now(timezone.utc).isoformat()
    titles = _title_ids(args.data_dir) if args.all_titles else (
        [args.title] if args.title else [])
    if not titles:
        log.warning("bq_export: 대상 타이틀 없음")
        return 0
    for tid in titles:
        res = export_title(client, cfg["dataset"], tid, args.data_dir, loaded_at,
                           dry_run=args.dry_run)
        log.info("bq_export %s: %s", tid, res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/test_bq_export.py -q`
Expected: 모두 passed

- [ ] **Step 5: 커밋**

```bash
git add pipeline/bq_export.py tests/test_bq_export.py
git commit -m "feat(bq_export): 테이블 부트스트랩·CLI 오케스트레이션

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: 통합 — 의존·nightly·시크릿·회귀

**Files:**
- Modify: `requirements.txt`
- Modify: `scripts/nightly.ps1`
- Create: `.env.example` (또는 기존에 append)
- Modify: `.gitignore` (확인)
- Test: 전체 pytest

**Interfaces:**
- Consumes: Task 5 `main()`.

- [ ] **Step 1: 의존 추가**

`requirements.txt`에 추가:
```
# BigQuery exporter (pipeline/bq_export.py)
google-cloud-bigquery>=3.25.0,<4.0.0
```

- [ ] **Step 2: .gitignore 시크릿 확인**

`.gitignore`에 없으면 추가:
```
.secrets/
.env
```
Run: `git check-ignore .secrets/bq_sa.json .env` — 둘 다 출력되면 OK.

- [ ] **Step 3: .env.example 안내 추가**

`.env.example`(없으면 생성)에 append:
```
# BigQuery exporter (선택 — 미설정 시 스킵)
BQ_EXPORT_ENABLED=0
BQ_PROJECT=
BQ_DATASET=cloop
GOOGLE_APPLICATION_CREDENTIALS=.secrets/bq_sa.json
```

- [ ] **Step 4: nightly.ps1 단계 추가**

`scripts/nightly.ps1`의 git push 블록 **뒤**(로그 회전 전)에 추가. `$VenvPython` 변수 사용, `-DryRun`이면 스킵:
```powershell
# --- BigQuery export (git push 뒤 · 격리 · 게이팅은 파이썬 내부) ---
if (-not $DryRun) {
    Write-Log INFO "BigQuery export 시작"
    & $VenvPython -m pipeline.bq_export --all-titles 2>&1 | ForEach-Object { Write-Log INFO $_ }
    if ($LASTEXITCODE -ne 0) { Write-Log WARN "bq_export 비정상 종료(대시보드·git 무영향)" }
} else {
    Write-Log INFO "DryRun — BigQuery export 스킵"
}
```

- [ ] **Step 5: 전체 회귀 + 커밋**

Run: `python -m pytest -q`
Expected: 기존 188 + bq_export 신규 테스트 모두 passed

```bash
git add requirements.txt scripts/nightly.ps1 .env.example .gitignore
git commit -m "chore(bq_export): 의존·nightly 통합·시크릿 게이트

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## 검증 요약

- Task 1: 게이팅(env 없음/키 부재 → None).
- Task 2: JSON→행 변환 4종, 중첩 평탄화·snapshot_date·title_id 주입.
- Task 3: BQ 스키마 4테이블·파티션 범위 min..max.
- Task 4: 파티션 교체(DELETE 범위→load, dry-run 무쓰기, 빈 rows noop) — fake client.
- Task 5: 부트스트랩·타이틀 오케스트레이션·CLI·테이블 격리 — fake client.
- Task 6: 의존·nightly 통합·시크릿 gitignore·전체 회귀.
- 라이브 BQ 검증은 사용자: `python -m pipeline.bq_export --all-titles --dry-run` 후 실적재.
