"""per-title Airbridge app_name 배선 — 멀티타이틀 MMP (zeus 등록)."""


def test_resolve_config_airbridge_app_name(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")  # resolve_config API키 게이트 통과
    from pipeline.main import resolve_config

    class A:
        pass
    a = A()
    for k in ("title", "root", "phase", "type", "limit"):
        setattr(a, k, None)
    for k in ("pilot", "no_cache", "dry_run", "no_fallback", "no_kpi"):
        setattr(a, k, False)

    ov = {
        "id": "zeus",
        "_pipeline_creatives_root": "G:/fake/zeus",
        "_pipeline_mmp_provider": "airbridge",
        "_pipeline_airbridge_enabled": True,
        "_pipeline_airbridge_app_name": "zeuskr",
    }
    cfg = resolve_config(a, title_override=ov)
    assert cfg["airbridge_app_name"] == "zeuskr"
    assert cfg["mmp_provider"] == "airbridge"


def test_resolve_config_airbridge_app_name_absent_default(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    from pipeline.main import resolve_config

    class A:
        pass
    a = A()
    for k in ("title", "root", "phase", "type", "limit"):
        setattr(a, k, None)
    for k in ("pilot", "no_cache", "dry_run", "no_fallback", "no_kpi"):
        setattr(a, k, False)

    ov = {"id": "pepp-us", "_pipeline_creatives_root": "G:/fake/pepp",
          "_pipeline_airbridge_enabled": True}
    cfg = resolve_config(a, title_override=ov)
    assert cfg["airbridge_app_name"] == ""   # 미설정 → 빈 문자열(=> .env 단일앱 사용)
