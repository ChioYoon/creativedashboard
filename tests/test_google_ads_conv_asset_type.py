"""_build_gaql_conversions 가 asset.type 필터 포함 — TEXT 등 비-소재 asset over-fetch 방지 (QA P0-D)."""
from datetime import date

from pipeline.sources.google_ads import GoogleAdsKpiSource, SUPPORTED_ASSET_TYPES


def test_conversions_query_filters_asset_type():
    gaql = GoogleAdsKpiSource._build_gaql_conversions(date(2025, 1, 1), date(2025, 1, 31), None, None)
    assert "asset.type IN" in gaql
    for t in SUPPORTED_ASSET_TYPES:
        assert f"'{t}'" in gaql
