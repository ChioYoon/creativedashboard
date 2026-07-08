from pipeline.mmp_metrics import compute_mmp_quality_scores


def test_registration_scores_3axis_and_convbasis():
    metrics = {
        "a": {"conversions": 300, "d1_cpi": 100.0, "d1_ipm": 20.0},   # 전환↑ CPA↓ IPM↑ = 최상
        "b": {"conversions": 100, "d1_cpi": 300.0, "d1_ipm": 5.0},    # 최하
    }
    out = compute_mmp_quality_scores(metrics, conversion_basis="registration")
    assert out["a"]["total"] > out["b"]["total"]
    assert out["a"]["convBasis"] == "사전예약"
    assert out["a"]["rank"] == 1
    # 3축 균등: a는 세 축 모두 1위 → total 100
    assert out["a"]["total"] == 100.0
    # roas 축 없음 → roas 점수 None
    assert out["a"]["roas"] is None


def test_install_scores_unchanged_default():
    metrics = {
        "a": {"installs": 100, "d1_cpi": 100.0, "d1_ipm": 20.0, "d7_roas": 2.0},
        "b": {"installs": 50, "d1_cpi": 200.0, "d1_ipm": 10.0, "d7_roas": 1.0},
    }
    out = compute_mmp_quality_scores(metrics)      # 기본 install
    assert out["a"]["total"] == 100.0              # 4축 모두 1위
    assert out["a"]["convBasis"] == "설치"
    assert out["a"]["roas"] == 100.0
