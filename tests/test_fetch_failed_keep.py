from pipeline.main import _atomic_write_text, _fetch_failed


def test_fetch_failed_states():
    assert _fetch_failed("success", "success") is False
    assert _fetch_failed("skipped", "skipped") is False
    assert _fetch_failed("success", "success_truncated") is False
    assert _fetch_failed("failed", "success") is True
    assert _fetch_failed("auth_failed", "skipped") is True
    assert _fetch_failed("success", "failed") is True


def test_atomic_write_replaces_and_leaves_no_tmp(tmp_path):
    p = tmp_path / "t.json"
    p.write_text("old", encoding="utf-8")
    _atomic_write_text(p, '{"a": 1}')
    assert p.read_text(encoding="utf-8") == '{"a": 1}'
    assert not (tmp_path / "t.json.tmp").exists()
