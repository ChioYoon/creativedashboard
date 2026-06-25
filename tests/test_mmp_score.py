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


def test_inject_mmp_none_metrics_no_crash():
    """impressions=0·cost=0 소재 → compute_mmp_quality None 반환, inject 가 round(None) 으로 깨지지 않아야 함 (회귀)."""
    from pipeline.main import inject_mmp_into_records
    from pipeline.schemas import CreativeRecord, CreativeMmpDaily
    rec = CreativeRecord(creative_id="A", 소재명="A", 파일명="A.mp4", 유형="VID")
    daily = [CreativeMmpDaily(creative_name="A", date="2026-06-20", channel="facebook",
                              impressions=0, clicks=0, cost=0, installs=10,
                              retained_d1=0, revenue_d7=0)]
    inject_mmp_into_records([rec], daily, source_name="appsflyer")  # must not raise
    assert rec.mmp_d1_ipm is None
    assert rec.mmp_d1_cpi is None
    assert rec.mmp_d7_roas is None
    assert rec.mmp_source == "appsflyer"
