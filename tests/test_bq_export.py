"""BigQuery exporter 설정 로더 테스트."""
from pipeline.bq_export import (
    load_bq_config,
    rows_kpi_daily,
    rows_mmp_daily,
    rows_creatives,
    rows_axis,
    TABLE_SPECS,
    partition_range,
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
