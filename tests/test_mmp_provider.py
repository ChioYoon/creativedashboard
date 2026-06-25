"""메인 MMP 프로바이더 선택자 단위테스트."""
import os
import pytest
from pipeline.main import make_mmp_source
from pipeline.sources.appsflyer import AppsFlyerMmpSource
from pipeline.sources.airbridge import AirbridgeMmpSource


def test_provider_appsflyer(monkeypatch):
    monkeypatch.setenv("APPSFLYER_API_TOKEN", "tok")
    src, provider = make_mmp_source(
        {"mmp_provider": "appsflyer", "appsflyer_app_id": "com.x", "airbridge_usd_to_krw": 1500})
    assert provider == "appsflyer"
    assert isinstance(src, AppsFlyerMmpSource)
    assert src.app_id == "com.x" and src.usd_to_krw == 1500


def test_provider_airbridge_explicit(monkeypatch):
    monkeypatch.setenv("AIRBRIDGE_API_TOKEN", "tok")
    monkeypatch.setenv("AIRBRIDGE_APP_NAME", "relicheros")
    src, provider = make_mmp_source({"mmp_provider": "airbridge"})
    assert provider == "airbridge"
    assert isinstance(src, AirbridgeMmpSource)


def test_provider_airbridge_fallback(monkeypatch):
    # mmp_provider 미설정 + airbridge_enabled=True → airbridge 폴백(하위호환)
    monkeypatch.setenv("AIRBRIDGE_API_TOKEN", "tok")
    monkeypatch.setenv("AIRBRIDGE_APP_NAME", "relicheros")
    src, provider = make_mmp_source({"airbridge_enabled": True})
    assert provider == "airbridge"
    assert isinstance(src, AirbridgeMmpSource)


def test_provider_none():
    src, provider = make_mmp_source({})
    assert src is None and provider == ""
