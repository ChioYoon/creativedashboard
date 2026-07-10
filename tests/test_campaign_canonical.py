"""캠페인명 캐노니컬 파서 단위테스트."""
from pipeline.campaign_canonical import (
    parse_campaign_canonical, campaign_ua_type,
    campaign_country, campaign_os, build_campaign_canonical,
)


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


def test_campaign_country():
    assert campaign_country("HQ_HQ_PH_US-EN_GA_NU_AD_ACA-PU_260429") == "US"
    assert campaign_country("Maximizer_HQ_GD_KR-KR_GA_NU-Pre_AD_ACp_241218") == "KR"
    assert campaign_country("no_country_here") == ""
    assert campaign_country("") == ""


def test_campaign_os():
    assert campaign_os("HQ_HQ_PH_CA-EN_FB_NU_iOS_INSTALL_260122") == "iOS"
    assert campaign_os("HQ_HQ_PH_US-EN_GA_NU_AOS_ACA_260101") == "Android"
    assert campaign_os("x_android_y") == "Android"
    assert campaign_os("a_web_b") == "Web"
    assert campaign_os("no_os_token") == ""
    assert campaign_os("") == ""


def test_campaign_country_positional_single():
    # 위치 country 토큰(단일 KR) — 제우스 GA/Meta 캠페인. 이전엔 XX-XX 아니라 '미상'되던 버그.
    assert campaign_country("Incross_HQ_ZEUS_KR_GA_NU-Pre_AD_ACp_260701") == "KR"
    assert campaign_country("Incross_HQ_ZEUS_KR_Meta_NU-Pre_iOS_MAIA-CPP_260701") == "KR"
    assert campaign_country("Incross_HQ_ZEUS_KR-KR_Meta_NU-Pre_ALL_Conversion_260701") == "KR"


def test_campaign_os_ad_all():
    # AD=Android(제우스 표기), ALL=전체. 이전엔 둘 다 '미상'되던 버그.
    assert campaign_os("Incross_HQ_ZEUS_KR_GA_NU-Pre_AD_ACp_260701") == "Android"
    assert campaign_os("Incross_HQ_ZEUS_KR-KR_Meta_NU-Pre_ALL_Conversion_260701") == "전체"
    assert campaign_os("Incross_HQ_ZEUS_KR_Meta_NU-Pre_iOS_MAIA-CPP_260701") == "iOS"


def test_build_canonical_zeus_ga_kr_android():
    name = "Incross_HQ_ZEUS_KR_GA_NU-Pre_AD_ACp_260701"
    e = build_campaign_canonical([name])[name]
    assert e["country"] == "KR" and e["os"] == "Android" and e["media"] == "GA"


def test_build_campaign_canonical_basic():
    names = ["HQ_HQ_PH_US-EN_GA_NU-Pre_iOS_ACp_260429"]
    m = build_campaign_canonical(names)
    assert set(m.keys()) == set(names)
    e = m[names[0]]
    assert e["ua_type"] == "NU-Pre" and e["country"] == "US" and e["os"] == "iOS"
    assert e["media"] == "GA" and e["product"] == "ACp"
    assert set(e.keys()) == {"ua_type", "country", "os", "media", "product"}


def test_build_campaign_canonical_dedup_and_missing():
    m = build_campaign_canonical(["A_B_C", "A_B_C", "", None])
    assert list(m.keys()) == ["A_B_C"]            # 중복 제거 + 빈/None 제외
    assert m["A_B_C"] == {"ua_type": "", "country": "", "os": "", "media": "", "product": ""}


def test_build_campaign_canonical_empty():
    assert build_campaign_canonical([]) == {}
    assert build_campaign_canonical(None) == {}


def test_dataset_has_campaign_canonical_default():
    from pipeline.schemas import CreativeDataset
    ds = CreativeDataset(title_id="t", generated_at="2026-01-01T00:00:00+09:00")
    payload = ds.model_dump(by_alias=True)
    assert payload["campaign_canonical"] == {}


def test_dataset_serializes_campaign_canonical():
    from pipeline.schemas import CreativeDataset
    m = {"A_B_C_US-EN_GA_NU_AD_ACp": {"ua_type": "NU", "country": "US", "os": "", "media": "GA", "product": "ACp"}}
    ds = CreativeDataset(title_id="t", generated_at="2026-01-01T00:00:00+09:00", campaign_canonical=m)
    assert ds.model_dump(by_alias=True)["campaign_canonical"] == m


def test_collect_campaign_names():
    from pipeline.main import _collect_campaign_names

    class _Row:  # duck-typed (pydantic 모델 불필요)
        def __init__(self, kpi, mmp):
            self.kpi_daily = kpi
            self.mmp_daily = mmp

    class _Daily:
        def __init__(self, cn):
            self.campaign_name = cn

    recs = [
        _Row([_Daily("A_B_C"), _Daily("")], [_Daily("D_E_F")]),
        _Row([_Daily("A_B_C")], []),       # 중복
        _Row([], None),                    # mmp_daily None
    ]
    assert _collect_campaign_names(recs) == {"A_B_C", "D_E_F"}
