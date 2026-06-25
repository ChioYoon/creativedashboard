"""fetch_mmp_window 90일 청크 분할 단위 테스트."""
from datetime import date
from pipeline.sources.airbridge import AirbridgeMmpSource


class _Row:
    def __init__(self, cn, ch, camp, d):
        self.creative_name = cn
        self.channel = ch
        self.campaign_name = camp
        self.date = d


def _src():
    return AirbridgeMmpSource(token="x", app_name="y")


def test_chunks_over_90_days():
    """200일 범위 → 90일 청크 3개로 분할 호출."""
    s = _src()
    calls = []
    s._fetch_window_single = lambda cs, ce, excl: (calls.append((cs, ce)), ([], False))[1]
    s.fetch_mmp_window(date(2025, 11, 1), date(2026, 5, 19), exclude_channels=set())
    assert len(calls) == 3
    assert calls[0] == (date(2025, 11, 1), date(2026, 1, 29))
    assert calls[1] == (date(2026, 1, 30), date(2026, 4, 29))
    assert calls[2] == (date(2026, 4, 30), date(2026, 5, 19))


def test_single_chunk_under_90_days():
    """30일 범위 → 단일 청크(기존 동작)."""
    s = _src()
    calls = []
    s._fetch_window_single = lambda cs, ce, excl: (calls.append((cs, ce)), ([], False))[1]
    s.fetch_mmp_window(date(2026, 5, 1), date(2026, 5, 30), exclude_channels=set())
    assert len(calls) == 1
    assert calls[0] == (date(2026, 5, 1), date(2026, 5, 30))


def test_dedup_across_chunks():
    """청크 경계에서 동일 row 중복 → dedup."""
    s = _src()
    r = _Row("A", "facebook.business", "camp", "2026-01-29")
    seq = [([r], False), ([r], False), ([], False)]
    s._fetch_window_single = lambda cs, ce, excl: seq.pop(0)
    out = s.fetch_mmp_window(date(2025, 11, 1), date(2026, 5, 19), exclude_channels=set())
    assert len(out) == 1


def test_truncated_is_or_of_chunks():
    """청크 중 하나라도 truncated → last_fetch_truncated True."""
    s = _src()
    seq = [([], False), ([], True), ([], False)]
    s._fetch_window_single = lambda cs, ce, excl: seq.pop(0)
    s.fetch_mmp_window(date(2025, 11, 1), date(2026, 5, 19), exclude_channels=set())
    assert s.last_fetch_truncated is True
