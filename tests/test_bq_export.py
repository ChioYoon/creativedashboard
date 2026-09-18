"""BigQuery exporter 설정 로더 테스트."""
from pipeline.bq_export import load_bq_config


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
