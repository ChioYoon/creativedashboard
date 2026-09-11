"""pause_tool.ledger.reduce_paused 순수 로직 검증."""
from pause_tool.ledger import reduce_paused

EVENTS = [
    {"ts": "2026-08-14T10:00", "title": "zeus", "key": "A", "mode": "remove", "asset_ids": ["1", "2"]},
    {"ts": "2026-08-14T10:05", "title": "zeus", "key": "B", "mode": "remove", "asset_ids": ["3"]},
    {"ts": "2026-08-14T10:10", "title": "zeus", "key": "A", "mode": "resume", "asset_ids": ["1", "2"]},
    {"ts": "2026-08-14T10:15", "title": "gd", "key": "C", "mode": "remove", "asset_ids": ["9"]},
]


def test_last_event_wins_resume_clears():
    p = reduce_paused(EVENTS, "zeus")
    # A는 remove 후 resume → 활성. B만 중단.
    assert [g["key"] for g in p] == ["B"]
    assert p[0]["asset_ids"] == ["3"]


def test_title_filter():
    assert [g["key"] for g in reduce_paused(EVENTS, "gd")] == ["C"]


def test_partial_resume_keeps_remainder():
    ev = EVENTS[:2] + [{"ts": "2026-08-14T11:00", "title": "zeus", "key": "A", "mode": "resume", "asset_ids": ["1"]}]
    p = reduce_paused(ev, "zeus")
    a = next(g for g in p if g["key"] == "A")
    assert a["asset_ids"] == ["2"]   # 1은 복원, 2는 여전히 중단


def test_empty():
    assert reduce_paused([], "zeus") == []


if __name__ == "__main__":
    for fn in list(globals().values()):
        if callable(fn) and getattr(fn, "__name__", "").startswith("test_"):
            fn()
    print("test_pause_tool_ledger OK")
