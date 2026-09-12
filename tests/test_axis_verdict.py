"""축 판정 — 단계분리·자격게이트·코호트 baseline·N/A 제외 검증."""
import datetime
from pipeline.axis_verdict import compute_axis_verdict


def _c(concept, rows):
    """rows: [(date, campaign, impr, conv, cost, val)]"""
    return {"creative_concept": concept,
            "kpi_daily": [{"date": d, "campaign_name": cn, "impressions": im,
                           "conversions": cv, "cost": co, "conversions_value": va}
                          for (d, cn, im, cv, co, va) in rows]}


CN = "Incross_HQ_ZEUS_KR-KR_GA_NU_AD_ACa_260826"       # 목적=NU (판정대상)
RT = "Incross_HQ_ZEUS_KR-KR_Meta_RT_iOS_RT-traffic_260827"  # 목적=RT (제외)


def _base():
    # 전투 쾌감 3소재(고IPM), 그래픽·비주얼 3소재(저IPM) — L단계(9월)
    cs = []
    for i in range(3):
        cs.append(_c(f"L-Ingame-ClassKnight-0{i}-PV", [("2026-09-01", CN, 1000, 5, 200000, 0)]))
    for i in range(3):
        cs.append(_c(f"L-Genre-Region-0{i}-DA", [("2026-09-01", CN, 1000, 1, 200000, 0)]))
    return cs


def test_structure_and_stage_split():
    r = compute_axis_verdict(_base(), title="zeus", launch_date="2026-08-26",
                             win_from="2026-08-06", win_to="2026-09-04",
                             baseline={"ipm": None, "roas7": None})
    assert set(["P", "L"]).issubset(r["stages"].keys())
    assert r["baseline_used"]["L"]["mode"] == "cohort_median"
    axes = {a["axis"]: a for a in r["stages"]["L"]}
    assert "전투 쾌감" in axes and "그래픽·비주얼" in axes


def test_efficiency_split_by_cohort_median():
    r = compute_axis_verdict(_base(), title="zeus", launch_date="2026-08-26",
                             win_from="2026-08-06", win_to="2026-09-04",
                             baseline={"ipm": None, "roas7": None})
    axes = {a["axis"]: a for a in r["stages"]["L"]}
    # 고IPM=후보(효율상회,품질미확인), 저IPM=소진
    assert axes["전투 쾌감"]["status"] == "후보"
    assert axes["그래픽·비주얼"]["status"] == "소진"


def test_qualification_gate():
    cs = [_c("L-Ingame-ClassKnight-01-PV", [("2026-09-01", CN, 1000, 5, 50000, 0)])]  # n=1, 비용<10만
    r = compute_axis_verdict(cs, title="zeus", launch_date="2026-08-26",
                             win_from="2026-08-06", win_to="2026-09-04",
                             baseline={"ipm": None, "roas7": None})
    assert r["stages"]["L"][0]["status"] == "미검증"


def test_rt_excluded_and_na_ratio():
    cs = _base() + [_c("L-Event-Market1st-01-DA", [("2026-09-01", CN, 1000, 9, 300000, 0)])]  # N/A:고지
    cs += [_c("L-Ingame-ClassKnight-9-PV", [("2026-09-01", RT, 9999, 99, 999999, 0)])]  # RT만 → 창내 판정대상 0
    r = compute_axis_verdict(cs, title="zeus", launch_date="2026-08-26",
                             win_from="2026-08-06", win_to="2026-09-04",
                             baseline={"ipm": None, "roas7": None})
    # Market1st(N/A) 제외 반영, RT-only 소재는 후보군서 빠짐
    assert r["excluded_ratio"] > 0
    axes = {a["axis"]: a for a in r["stages"]["L"]}
    assert "N/A:고지" not in axes  # N/A 축은 집계 제외
