"""캠페인명 캐노니컬 파서 단위테스트."""
from pipeline.campaign_canonical import parse_campaign_canonical, campaign_ua_type


def test_ua_type_nupre():
    assert campaign_ua_type("Maximizer_HQ_GD_KR-KR_GA_NU-Pre_AD_ACp_241218") == "NU-Pre"
    assert campaign_ua_type("HQ_HQ_PH_US-EN_GA_NU-Pre_AD_ACp_251104") == "NU-Pre"


def test_ua_type_nu_and_rt():
    assert campaign_ua_type("Maximizer_HQ_GD_KR-KR_GA_NU_AD_ACi_250115") == "NU"
    assert campaign_ua_type("HQ_HQ_PH_US-EN_GA_RT_AD_ACe_250522") == "RT"


def test_ua_type_unparsed_empty():
    assert campaign_ua_type("test_campaign_junk") == ""
    assert campaign_ua_type("") == ""


def test_parse_canonical_full():
    p = parse_campaign_canonical("Maximizer_HQ_GD_KR-KR_GA_NU-Pre_AD_ACp_241218")
    assert p["agency"] == "Maximizer" and p["executor"] == "HQ" and p["title"] == "GD"
    assert p["country"] == "KR-KR" and p["media"] == "GA" and p["ua_type"] == "NU-Pre"
    assert p["os"] == "AD" and p["product"] == "ACp" and p["date"] == "241218"


def test_parse_canonical_no_date():
    p = parse_campaign_canonical("Mobidays_HQ_RUSH_WW-EN_FB_NU_AD_AAA-AEO-Tutorial2")
    assert p["product"] == "AAA-AEO-Tutorial2" and p["date"] is None
    assert p["ua_type"] == "NU"


def test_ua_type_boosting():
    assert campaign_ua_type("Maximizer_HQ_GD_KR-KR_GA_Boosting_AD_ACi_250115") == "Boosting"


def test_parse_canonical_short_segments():
    p = parse_campaign_canonical("A_B_C")
    assert p["agency"] == "A" and p["executor"] == "B" and p["title"] == "C"
    assert p["country"] is None and p["product"] is None and p["date"] is None
