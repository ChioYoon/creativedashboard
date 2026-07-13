# -*- coding: utf-8 -*-
"""fetch_window 집계 키 회귀 테스트.

버그: 집계 키가 (creative_name, campaign, ad_group, date) 4-튜플이라, 같은
youtube_video_title(=creative_name)을 가진 서로 다른 두 영상이 같은
캠페인·광고그룹·날짜에 집행되면 한 행으로 병합되어 두 번째 영상의 asset_url이
사라지고 노출이 합산됨. 수정: 키에 asset_url(에셋 식별자)을 포함.
"""
from datetime import date
from types import SimpleNamespace

from pipeline.sources.google_ads import GoogleAdsKpiSource


def _video_row(video_id, *, title, campaign, ad_group, day, impr=100):
    """ad_group_ad_asset_view YOUTUBE_VIDEO row 모의(proto 속성 접근 흉내)."""
    return SimpleNamespace(
        segments=SimpleNamespace(date=day),
        asset=SimpleNamespace(
            name="",  # VIDEO는 asset.name 공란
            type_=SimpleNamespace(name="YOUTUBE_VIDEO"),
            image_asset=SimpleNamespace(full_size=SimpleNamespace(url="")),
            youtube_video_asset=SimpleNamespace(
                youtube_video_id=video_id, youtube_video_title=title),
        ),
        campaign=SimpleNamespace(name=campaign, id=1),
        ad_group=SimpleNamespace(name=ad_group, id=1),
        metrics=SimpleNamespace(
            impressions=impr, clicks=0, cost_micros=0,
            conversions=0.0, conversions_value=0.0),
    )


class _FakeService:
    def __init__(self, rows): self._rows = rows
    def search_stream(self, customer_id, query):
        return [SimpleNamespace(results=self._rows)]


class _FakeClient:
    login_customer_id = "0000000000"
    def __init__(self, rows): self._svc = _FakeService(rows)
    def get_service(self, name): return self._svc


def _fetch(rows):
    src = GoogleAdsKpiSource(client=_FakeClient(rows))
    return list(src.fetch_window("123", date(2026, 6, 15), date(2026, 7, 12)))


def test_same_title_different_video_stays_split():
    """같은 제목·캠페인·광고그룹·날짜의 서로 다른 두 영상 → 병합되지 않고 2행 유지."""
    rows = [
        _video_row("AAA", title="클래스 소개 나이트", campaign="C1", ad_group="G1", day="2026-06-20", impr=100),
        _video_row("BBB", title="클래스 소개 나이트", campaign="C1", ad_group="G1", day="2026-06-20", impr=80),
    ]
    out = _fetch(rows)
    urls = sorted(d.asset_url for d in out)
    assert urls == ["https://www.youtube.com/watch?v=AAA",
                    "https://www.youtube.com/watch?v=BBB"]
    assert len(out) == 2
    assert {d.impressions for d in out} == {100, 80}  # 노출이 합산되지 않음


def test_same_video_still_merges():
    """같은 영상(같은 video_id)의 동일 4-키 중복 행은 기존대로 합산(회귀 방지)."""
    rows = [
        _video_row("AAA", title="클래스 소개 나이트", campaign="C1", ad_group="G1", day="2026-06-20", impr=100),
        _video_row("AAA", title="클래스 소개 나이트", campaign="C1", ad_group="G1", day="2026-06-20", impr=50),
    ]
    out = _fetch(rows)
    assert len(out) == 1
    assert out[0].impressions == 150
    assert out[0].asset_url == "https://www.youtube.com/watch?v=AAA"
