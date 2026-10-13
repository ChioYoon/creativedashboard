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


def test_with_retry_retries_transient_then_succeeds():
    from pipeline.main import _with_retry
    calls = []
    def fn():
        calls.append(1)
        if len(calls) < 2:
            raise RuntimeError("Connection aborted")
        return "ok"
    assert _with_retry(fn, "t", delay=0) == "ok" and len(calls) == 2


def test_with_retry_does_not_retry_auth_error():
    import pytest
    from pipeline.main import _with_retry
    class AuthError(Exception):
        pass
    calls = []
    def fn():
        calls.append(1)
        raise AuthError("expired")
    with pytest.raises(AuthError):
        _with_retry(fn, "t", delay=0)
    assert len(calls) == 1
