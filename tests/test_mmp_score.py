"""분모 가드 — 비용/노출 0이면 CPI·IPM·ROAS None 검증."""


def test_compute_mmp_quality_impr_zero_ipm_none():
    from pipeline.mmp_metrics import compute_mmp_quality
    q = compute_mmp_quality({"impressions": 0, "cost": 1000, "installs": 10,
                             "retained_d1": 5, "revenue_d7": 2000})
    assert q["d1_ipm"] is None          # 노출 0 → IPM '—'


def test_compute_mmp_quality_cost_zero_cpi_none():
    from pipeline.mmp_metrics import compute_mmp_quality
    q = compute_mmp_quality({"impressions": 1000, "cost": 0, "installs": 10,
                             "retained_d1": 5, "revenue_d7": 0})
    assert q["d1_cpi"] is None          # 비용 0 → CPI '—'
    assert q["d7_roas"] is None         # 비용 0 → ROAS '—'
