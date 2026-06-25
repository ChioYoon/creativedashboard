"""TagCache.get_any (carry-forward 폴백) 단위 테스트."""
from pipeline.cache import TagCache


def test_get_any_returns_latest_non_pilot(tmp_path):
    c = TagCache(tmp_path, "t")
    c.put("sha1", "v3.0-2026.06.10", {"x": 1})
    c.put("sha1", "v3.3-2026.06.13", {"x": 2})
    c.put("sha2", "v3.0-2026.06.10", {"y": 9})
    res = c.get_any("sha1")
    assert res is not None
    payload, ver = res
    assert ver == "v3.3-2026.06.13"
    assert payload == {"x": 2}


def test_get_any_excludes_pilot(tmp_path):
    c = TagCache(tmp_path, "t")
    c.put("sha1", "v3.3-2026.06.13", {"x": 2})
    c.put("sha1", "v9.9-zzz-pilot", {"x": 99})   # pilot 제외 → v3.3 선택
    payload, ver = c.get_any("sha1")
    assert ver == "v3.3-2026.06.13"
    assert payload == {"x": 2}


def test_get_any_exclude_version(tmp_path):
    c = TagCache(tmp_path, "t")
    c.put("sha1", "v3.0-2026.06.10", {"x": 1})
    c.put("sha1", "v3.3-2026.06.13", {"x": 2})
    payload, ver = c.get_any("sha1", exclude_version="v3.3-2026.06.13")
    assert ver == "v3.0-2026.06.10"
    assert payload == {"x": 1}


def test_get_any_none_when_no_match(tmp_path):
    c = TagCache(tmp_path, "t")
    c.put("sha1", "v3.3-2026.06.13", {"x": 2})
    assert c.get_any("nope") is None


def test_get_any_none_when_only_pilot(tmp_path):
    c = TagCache(tmp_path, "t")
    c.put("sha1", "v1-pilot", {"x": 1})
    assert c.get_any("sha1") is None   # pilot만 있으면 폴백 없음
