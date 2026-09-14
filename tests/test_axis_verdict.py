"""축 판정 — 단계분리·자격게이트·코호트 baseline·N/A 제외 검증."""
import datetime
from pipeline.axis_verdict import compute_axis_verdict


def _c(concept, rows):
    """rows: [(date, campaign, impr, conv, cost, val[, clicks])]"""
    kd = []
    for r in rows:
        d, cn, im, cv, co, va = r[:6]
        clk = r[6] if len(r) > 6 else 0
        kd.append({"date": d, "campaign_name": cn, "impressions": im, "clicks": clk,
                   "conversions": cv, "cost": co, "conversions_value": va})
    return {"creative_concept": concept, "kpi_daily": kd}


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
                             win_from="2026-08-06", win_to="2026-09-04")
    assert set(["P", "L"]).issubset(r["stages"].keys())
    assert r["baseline_used"]["L"]["mode"] == "cohort_weighted"
    axes = {a["axis"]: a for a in r["stages"]["L"]}
    assert "전투 쾌감" in axes and "그래픽·비주얼" in axes


def test_L_stage_efficiency_split_roas_cap():
    # L단계: ROAS 부재 → 효율상회=후보cap, 효율하회=소진
    r = compute_axis_verdict(_base(), title="zeus", launch_date="2026-08-26",
                             win_from="2026-08-06", win_to="2026-09-04")
    axes = {a["axis"]: a for a in r["stages"]["L"]}
    assert axes["전투 쾌감"]["status"] == "후보"     # 효율상회·ROAS미확인 → 후보 cap
    assert axes["그래픽·비주얼"]["status"] == "소진"


def test_P_stage_conversion_quality_can_verify():
    # P단계(런칭 전): 품질=전환율(전환/클릭). 효율·전환율 동시상회 → 검증(cap 없음)
    cs = []
    for i in range(3):  # 고효율·고전환율
        cs.append(_c(f"P-Ingame-ClassKnight-0{i}-PV", [("2026-08-10", CN, 1000, 5, 200000, 0, 500)]))
    for i in range(3):  # 저효율·저전환율
        cs.append(_c(f"P-Genre-Region-0{i}-DA", [("2026-08-10", CN, 1000, 1, 200000, 0, 300)]))
    r = compute_axis_verdict(cs, title="zeus", launch_date="2026-08-26",
                             win_from="2026-08-06", win_to="2026-09-04")
    axes = {a["axis"]: a for a in r["stages"]["P"]}
    assert axes["전투 쾌감"]["status"] == "검증"   # P단계는 전환율 품질로 검증 가능
    assert axes["그래픽·비주얼"]["status"] == "소진"


def test_qualification_gate():
    cs = [_c("L-Ingame-ClassKnight-01-PV", [("2026-09-01", CN, 1000, 5, 50000, 0)])]  # n=1, 비용<10만
    r = compute_axis_verdict(cs, title="zeus", launch_date="2026-08-26",
                             win_from="2026-08-06", win_to="2026-09-04")
    assert r["stages"]["L"][0]["status"] == "미검증"


def test_rt_excluded_and_na_ratio():
    cs = _base() + [_c("L-Event-Market1st-01-DA", [("2026-09-01", CN, 1000, 9, 300000, 0)])]  # N/A:고지
    cs += [_c("L-Ingame-ClassKnight-9-PV", [("2026-09-01", RT, 9999, 99, 999999, 0)])]  # RT만 → 창내 판정대상 0
    r = compute_axis_verdict(cs, title="zeus", launch_date="2026-08-26",
                             win_from="2026-08-06", win_to="2026-09-04")
    # Market1st(N/A) 제외 반영, RT-only 소재는 후보군서 빠짐
    assert r["excluded_ratio"] > 0
    axes = {a["axis"]: a for a in r["stages"]["L"]}
    assert "N/A:고지" not in axes  # N/A 축은 집계 제외
