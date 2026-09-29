"""BigQuery exporter 설정 로더 테스트."""
import json

from pipeline.bq_export import (
    load_bq_config,
    rows_kpi_daily,
    rows_mmp_daily,
    rows_creatives,
    rows_axis,
    TABLE_SPECS,
    partition_range,
    replace_partition,
    export_title,
    ensure_table,
)


def test_gating_disabled_returns_none():
    """비활성화된 환경(BQ_EXPORT_ENABLED != "1")은 None 반환."""
    assert load_bq_config({}) is None
    assert load_bq_config({"BQ_EXPORT_ENABLED": "0"}) is None


def test_gating_missing_creds_returns_none(tmp_path):
    """크레덴셜 파일이 없거나 경로가 없으면 None 반환."""
    env = {
        "BQ_EXPORT_ENABLED": "1",
        "BQ_PROJECT": "p",
        "BQ_DATASET": "cloop",
        "GOOGLE_APPLICATION_CREDENTIALS": str(tmp_path / "nope.json"),
    }
    assert load_bq_config(env) is None  # 키 파일 부재


def test_config_ok(tmp_path):
    """설정이 완전하면 dict 반환."""
    key = tmp_path / "sa.json"
    key.write_text("{}", encoding="utf-8")
    env = {
        "BQ_EXPORT_ENABLED": "1",
        "BQ_PROJECT": "proj",
        "BQ_DATASET": "cloop",
        "GOOGLE_APPLICATION_CREDENTIALS": str(key),
    }
    cfg = load_bq_config(env)
    assert cfg["project"] == "proj"
    assert cfg["dataset"] == "cloop"
    assert cfg["credentials_path"] == str(key)


# --- 행 변환(순수) 테스트 ---

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


# --- 스키마·파티션 범위(순수) 테스트 ---

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


# --- replace_partition(적재, fake client 주입) 테스트 ---

class _FakeJob:
    def result(self): return None

class _FakeClient:
    def __init__(self):
        self.queries = []; self.loaded = []
        self.project = "proj"  # ensure_table이 f"{client.project}.{dataset}" 조합에 사용
        self.datasets_created = []; self.tables_created = []
    def query(self, sql, *a, **k): self.queries.append(sql); return _FakeJob()
    def load_table_from_json(self, rows, table_ref, *a, **k):
        self.loaded.append((table_ref, list(rows))); return _FakeJob()
    def create_dataset(self, dataset_ref, *a, **k):
        self.datasets_created.append(dataset_ref); return dataset_ref
    def create_table(self, table, *a, **k):
        self.tables_created.append(table); return table

def test_replace_partition_deletes_then_loads():
    fc = _FakeClient()
    rows = [{"date": "2026-09-10", "title_id": "zeus"}, {"date": "2026-08-21", "title_id": "zeus"}]
    res = replace_partition(fc, "cloop", "kpi_daily", rows)
    assert res["deleted_range"] == ("2026-08-21", "2026-09-10")
    assert res["loaded"] == 2
    assert len(fc.queries) == 1 and "DELETE" in fc.queries[0].upper()
    assert "2026-08-21" in fc.queries[0] and "2026-09-10" in fc.queries[0]
    assert "title_id" in fc.queries[0] and "'zeus'" in fc.queries[0]
    assert len(fc.loaded) == 1 and len(fc.loaded[0][1]) == 2

def test_replace_partition_deletes_scoped_to_all_titles_in_rows():
    """공유 테이블: rows에 여러 타이틀이 섞이면 DELETE의 IN 절에 전부 포함."""
    fc = _FakeClient()
    rows = [{"date": "2026-09-10", "title_id": "zeus"},
            {"date": "2026-09-11", "title_id": "tougenanki"}]
    replace_partition(fc, "cloop", "kpi_daily", rows)
    assert "'zeus'" in fc.queries[0] and "'tougenanki'" in fc.queries[0]
    assert "title_id IN" in fc.queries[0]

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


# --- export_title(테이블 부트스트랩 오케스트레이션, fake client 주입) 테스트 ---

def test_export_title_all_tables(tmp_path):
    dd = tmp_path
    (dd / "zeus.json").write_text(json.dumps(_DS, ensure_ascii=False), encoding="utf-8")
    (dd / "zeus_axis.json").write_text(json.dumps(_AX, ensure_ascii=False), encoding="utf-8")
    fc = _FakeClient()
    res = export_title(fc, "cloop", "zeus", str(dd), "2026-09-18T04:00:00Z", dry_run=True)
    tables = {r["table"] for r in res}
    assert tables == {"kpi_daily", "mmp_daily", "creatives", "axis"}
    # dry_run이라 무쓰기
    assert fc.queries == [] and fc.loaded == []


def test_export_title_missing_axis_ok(tmp_path):
    dd = tmp_path
    (dd / "gd.json").write_text(
        json.dumps({"title_id": "gd", "generated_at": "2026-09-18T13:00:00+09:00", "creatives": []},
                   ensure_ascii=False),
        encoding="utf-8")
    fc = _FakeClient()
    res = export_title(fc, "cloop", "gd", str(dd), "2026-09-18T04:00:00Z", dry_run=True)
    # axis 파일 없어도 예외 없이 3테이블(빈 kpi/mmp/creatives) 처리
    assert any(r["table"] == "kpi_daily" for r in res)


# --- ensure_table(파티션·클러스터링 부트스트랩, fake client 주입) 테스트 ---

def test_ensure_table_wires_partition_and_clustering():
    fc = _FakeClient()
    ensure_table(fc, "cloop", "kpi_daily")
    assert len(fc.datasets_created) == 1
    assert len(fc.tables_created) == 1
    table = fc.tables_created[0]
    spec = TABLE_SPECS["kpi_daily"]
    assert table.time_partitioning.field == spec["partition_field"] == "date"
    assert table.clustering_fields == spec["clustering"]


def test_export_title_calls_ensure_table_when_not_dry_run(tmp_path):
    """dry_run=False 실경로에서도 ensure_table이 4테이블 모두에 대해 호출됨."""
    dd = tmp_path
    (dd / "zeus.json").write_text(json.dumps(_DS, ensure_ascii=False), encoding="utf-8")
    fc = _FakeClient()
    export_title(fc, "cloop", "zeus", str(dd), "2026-09-18T04:00:00Z", dry_run=False)
    created_tables = {t.table_id for t in fc.tables_created}
    assert created_tables == {"kpi_daily", "mmp_daily", "creatives", "axis"}


# --- export_title JSON 손상 격리(graceful) 테스트 ---

def test_export_title_malformed_json_isolated(tmp_path):
    """{title}.json이 손상되어도 예외를 던지지 않고 에러 결과만 반환(타이틀 격리)."""
    dd = tmp_path
    (dd / "broken.json").write_text("{not valid json", encoding="utf-8")
    fc = _FakeClient()
    res = export_title(fc, "cloop", "broken", str(dd), "2026-09-18T04:00:00Z", dry_run=True)
    assert len(res) == 1 and res[0]["table"] == "_load" and "error" in res[0]
    assert fc.queries == [] and fc.loaded == []


def test_title_ids_excludes_axis_pilot_sample(tmp_path):
    from pipeline.bq_export import _title_ids
    for n in ["zeus.json", "zeus_axis.json", "gd.pilot.json", "sample.json", "tougenanki.json"]:
        (tmp_path / n).write_text("{}", encoding="utf-8")
    assert _title_ids(str(tmp_path)) == ["tougenanki", "zeus"]  # axis·pilot·sample 제외
