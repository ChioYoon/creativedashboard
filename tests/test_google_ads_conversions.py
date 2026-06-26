"""Google Ads 전환 기준 분기 단위테스트 (HTTP 무의존)."""
from pipeline.schemas import CreativeKpiDaily
from pipeline.sources.google_ads import _apply_conversion_basis, GoogleAdsKpiSource
from datetime import date

PRE = {"App pre-registration(com.com2us.gd.android.google.global.normal)"}
INS = {"Gods & Demons - Com2uS (Android) first_open"}


def _daily(cn, camp, conv=0.0):
    return CreativeKpiDaily(creative_name=cn, date="2026-01-01", source="google_ads",
                            customer_id="1", campaign_name=camp, conversions=conv)


def test_nupre_campaign_uses_prereg_only():
    key = ("A", "Maximizer_HQ_GD_KR-KR_GA_NU-Pre_AD_ACp_241218", "ag", "2026-01-01")
    agg = {key: _daily("A", key[1])}
    conv = {key: {"App pre-registration(com.com2us.gd.android.google.global.normal)": 100.0,
                  "Gods & Demons - Com2uS (Android) first_open": 5.0}}
    _apply_conversion_basis(agg, conv, PRE, INS)
    assert agg[key].conversions == 100.0


def test_nu_campaign_uses_install_excludes_purchase():
    key = ("B", "Maximizer_HQ_GD_KR-KR_GA_NU_AD_ACa_250115", "ag", "2026-01-01")
    agg = {key: _daily("B", key[1])}
    conv = {key: {"Gods & Demons - Com2uS (Android) first_open": 30.0,
                  "Gods & Demons - Com2uS (Android) in_app_purchase": 110.0}}
    _apply_conversion_basis(agg, conv, PRE, INS)
    assert agg[key].conversions == 30.0   # 설치만, 구매 제외


def test_retargeting_no_target_action_zero():
    key = ("C", "Maximizer_HQ_GD_KR-KR_GA_RT_AD_ACe_250522", "ag", "2026-01-01")
    agg = {key: _daily("C", key[1], conv=99.0)}
    conv = {key: {"Gods & Demons - Com2uS (Android) session_start": 50.0}}
    _apply_conversion_basis(agg, conv, PRE, INS)
    assert agg[key].conversions == 0.0   # 설치/사전예약 액션 없음 → 0


def test_key_with_no_conversions_zero():
    key = ("D", "Maximizer_HQ_GD_KR-KR_GA_NU_AD_ACi_250115", "ag", "2026-01-01")
    agg = {key: _daily("D", key[1], conv=7.0)}
    _apply_conversion_basis(agg, {}, PRE, INS)   # conv_by_key 비어있음
    assert agg[key].conversions == 0.0


def test_build_gaql_conversions_shape():
    q = GoogleAdsKpiSource._build_gaql_conversions(date(2025, 1, 1), date(2025, 1, 31), None, None)
    assert "segments.conversion_action_name" in q
    assert "metrics.conversions" in q
    assert "metrics.impressions" not in q   # 중복 방지 — 노출 미수집
    assert "FROM ad_group_ad_asset_view" in q
