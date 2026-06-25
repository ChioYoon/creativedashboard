"""resolve_window — Google Ads KPI 윈도우 절대 시작일 확장 단위 테스트."""
from datetime import date, timedelta
from pipeline.sources.google_ads import resolve_window, default_window


def test_resolve_window_no_start_date_equals_default():
    assert resolve_window(159) == default_window(159)
    assert resolve_window(28, None) == default_window(28)


def test_resolve_window_absolute_extends_back():
    # 절대 시작일이 상대 윈도우(30일)보다 과거 → 그 날짜로 확장
    start, end = resolve_window(30, "2025-11-01")
    assert start == date(2025, 11, 1)
    assert end == date.today() - timedelta(days=1)


def test_resolve_window_absolute_later_is_ignored():
    # 절대 시작일이 상대 윈도우 시작보다 나중이면 무시(확장만, 축소 안 함)
    rel_start, _ = default_window(159)
    later = (rel_start + timedelta(days=10)).isoformat()
    start, _end = resolve_window(159, later)
    assert start == rel_start
