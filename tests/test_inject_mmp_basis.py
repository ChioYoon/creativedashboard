from pipeline.schemas import CreativeRecord, CreativeMmpDaily
from pipeline.main import inject_mmp_into_records


def _rec(cid):
    return CreativeRecord(creative_id=cid, 소재명=cid, 파일명=f"{cid}.jpg", 유형="VID")


def test_registration_basis_scores_from_conversions():
    # 소재 2개, 등록 기준 — 전환(등록) 많은 쪽이 높은 점수
    recs = [_rec("P-Slogan-A"), _rec("P-Slogan-B")]
    daily = [
        CreativeMmpDaily(creative_name="P-Slogan-A", date="2026-07-01", channel="meta",
                         campaign_name="X_NU-Pre_Y", impressions=10000, cost=20000, conversions=300),
        CreativeMmpDaily(creative_name="P-Slogan-B", date="2026-07-01", channel="meta",
                         campaign_name="X_NU-Pre_Y", impressions=10000, cost=20000, conversions=100),
    ]
    inject_mmp_into_records(recs, daily, source_name="airbridge", conversion_basis="registration")
    a = next(r for r in recs if r.creative_id == "P-Slogan-A")
    b = next(r for r in recs if r.creative_id == "P-Slogan-B")
    assert a.mmp_conversions == 300 and b.mmp_conversions == 100
    assert a.mmp_quality_score is not None
    assert a.mmp_quality_score["convBasis"] == "사전예약"
    assert a.mmp_quality_score["total"] >= b.mmp_quality_score["total"]
