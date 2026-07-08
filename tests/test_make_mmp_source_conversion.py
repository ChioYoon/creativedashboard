import os
import pytest
from pipeline.main import make_mmp_source


def test_airbridge_source_gets_conversion_metric(monkeypatch):
    monkeypatch.setenv("AIRBRIDGE_API_TOKEN", "t")
    monkeypatch.setenv("AIRBRIDGE_APP_NAME", "zeuskr")
    cfg = {"mmp_provider": "airbridge", "airbridge_app_name": "zeuskr",
           "airbridge_conversion_metric": "web_custom_complete_registration"}
    src, provider = make_mmp_source(cfg)
    assert provider == "airbridge"
    assert src.conversion_metric == "web_custom_complete_registration"
    assert src.metrics_map["conversions"] == "web_custom_complete_registration"


def test_airbridge_source_without_conversion_metric(monkeypatch):
    monkeypatch.setenv("AIRBRIDGE_API_TOKEN", "t")
    monkeypatch.setenv("AIRBRIDGE_APP_NAME", "someapp")
    src, provider = make_mmp_source({"mmp_provider": "airbridge"})
    assert src.conversion_metric == ""      # 미설정 → 빈 값(설치 기준)
