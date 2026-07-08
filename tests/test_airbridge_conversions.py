from pipeline.sources.airbridge import parse_actuals_rows


def _row(creative, channel, campaign, reg):
    return {"groupBys": [creative, channel, campaign, "2026-07-01"],
            "values": {"web_custom_complete_registration": {"value": reg},
                       "impressions_channel": {"value": 1000}}}


METRICS = {"conversions": "web_custom_complete_registration", "impressions": "impressions_channel"}


def test_conversions_parsed():
    result = {"actuals": {"data": {"rows": [
        _row("260701_VID_P-Slogan-PreregPV15s-01-PV_ALL_Mixed_KR", "meta.business",
             "Incross_HQ_ZEUS_KR_Meta_NU-Pre_ALL_Conversion_260701", 711)]}}}
    out = parse_actuals_rows(result, METRICS, set(), ua_scope=True)
    assert len(out) == 1
    assert out[0].conversions == 711


def test_ua_scope_skips_branding_rows():
    result = {"actuals": {"data": {"rows": [
        _row("Premium_MO", "criteo_new", "Incross_HQ_zeus_KR_NAVER_BR_MO_Display_260701", 5000),
        _row("260701_VID_P-Slogan-PreregPV15s-01-PV_ALL_Mixed_KR", "meta.business",
             "Incross_HQ_ZEUS_KR_Meta_NU-Pre_ALL_Conversion_260701", 711)]}}}
    out = parse_actuals_rows(result, METRICS, set(), ua_scope=True)
    assert len(out) == 1                       # BR 행 스킵
    assert out[0].creative_name.endswith("PreregPV15s-01-PV_ALL_Mixed_KR")
    assert out[0].conversions == 711


def test_ua_scope_off_keeps_all_rows():
    result = {"actuals": {"data": {"rows": [
        _row("Premium_MO", "criteo_new", "..._BR_MO_Display_260701", 5000)]}}}
    out = parse_actuals_rows(result, METRICS, set(), ua_scope=False)
    assert len(out) == 1                       # 스코프 OFF → 스킵 안 함(하위호환)
