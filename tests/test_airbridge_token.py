from pipeline.main import _resolve_airbridge_token


def test_per_title_token_priority():
    env = {"AIRBRIDGE_API_TOKEN_ZEUS": "ztok", "AIRBRIDGE_API_TOKEN": "deftok"}
    assert _resolve_airbridge_token("zeus", env) == "ztok"


def test_fallback_to_default():
    env = {"AIRBRIDGE_API_TOKEN": "deftok"}
    assert _resolve_airbridge_token("zeus", env) == "deftok"
    assert _resolve_airbridge_token("pepp-us", env) == "deftok"


def test_suffix_normalization():
    env = {"AIRBRIDGE_API_TOKEN_PEPP_US": "ptok", "AIRBRIDGE_API_TOKEN": "deftok"}
    assert _resolve_airbridge_token("pepp-us", env) == "ptok"


def test_empty_when_none_set():
    assert _resolve_airbridge_token("zeus", {}) == ""


def test_trims_whitespace():
    assert _resolve_airbridge_token("zeus", {"AIRBRIDGE_API_TOKEN_ZEUS": "  ztok  "}) == "ztok"
