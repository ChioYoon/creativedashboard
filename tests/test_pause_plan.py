"""pipeline.pause.plan_change 순수 로직 검증 (API 무의존)."""
from pipeline.pause import plan_change


def test_remove_ok():
    assert plan_change(["a", "b", "c"], {"a"}, remove=True) == (["b", "c"], None)


def test_remove_already_absent():
    new, skip = plan_change(["b", "c"], {"a"}, remove=True)
    assert new == ["b", "c"] and skip == "대상이 이미 없음"


def test_remove_min_keep_guard():
    # 마지막 1개 제거 → 0개 < min_keep(1) → skip
    new, skip = plan_change(["a"], {"a"}, remove=True, min_keep=1)
    assert new == [] and skip and "최소" in skip


def test_remove_multi_target():
    assert plan_change(["a", "b", "c"], {"a", "b"}, remove=True) == (["c"], None)


def test_resume_add():
    assert plan_change(["b", "c"], {"a"}, remove=False) == (["a", "b", "c"], None)


def test_resume_already_present():
    new, skip = plan_change(["a", "b"], {"a"}, remove=False)
    assert set(new) == {"a", "b"} and skip == "이미 있음"


if __name__ == "__main__":
    for fn in list(globals().values()):
        if callable(fn) and getattr(fn, "__name__", "").startswith("test_"):
            fn()
    print("test_pause_plan OK")
