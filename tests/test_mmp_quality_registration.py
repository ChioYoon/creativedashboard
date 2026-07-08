from pipeline.mmp_metrics import compute_mmp_quality


def test_registration_basis_uses_conversions():
    agg = {"impressions": 10000, "cost": 20000, "conversions": 100,
           "installs": 0, "retained_d1": 0, "revenue_d7": 0}
    q = compute_mmp_quality(agg, conversion_basis="registration")
    assert q["d1_ipm"] == (100 / 10000) * 1000      # 등록 IPM = 10.0
    assert q["d1_cpi"] == 20000 / 100               # CPA = 200
    assert q["d1_retention"] is None                 # 웹 사전예약 N/A
    assert q["d7_roas"] is None                      # N/A


def test_registration_zero_denominators_none():
    q = compute_mmp_quality({"impressions": 0, "cost": 0, "conversions": 0}, conversion_basis="registration")
    assert q["d1_ipm"] is None
    assert q["d1_cpi"] is None


def test_install_basis_unchanged_default():
    agg = {"impressions": 10000, "cost": 20000, "installs": 50, "retained_d1": 40, "revenue_d7": 60000}
    q = compute_mmp_quality(agg)     # 기본 install
    assert q["d1_ipm"] == (40 / 10000) * 1000
    assert q["d1_cpi"] == 20000 / 40
    assert q["d7_roas"] == 60000 / 20000
