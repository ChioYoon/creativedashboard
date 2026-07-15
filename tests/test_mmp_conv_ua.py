# -*- coding: utf-8 -*-
"""convUa(ua_type별 전환) — 파이프라인이 step1과 동일 기준으로 산출하는지.

전환 = Σ(NU-Pre 행 conversions=사전예약 등록) + Σ(NU 행 retained_d1=D1잔존).
품질점수 = 이 전환 4축(전환↑·CPA↓·IPM↑·D7 ROAS↑) rank — convBasis 라벨은 유지.
"""
from pipeline.schemas import CreativeRecord, CreativeMmpDaily
from pipeline.main import inject_mmp_into_records


def _rec(cid):
    return CreativeRecord(creative_id=cid, 소재명=cid, 파일명=f"{cid}.jpg", 유형="VID")


def _row(name, camp, **kw):
    base = dict(creative_name=name, date="2026-07-01", channel="meta", campaign_name=camp,
                impressions=10000, cost=20000)
    base.update(kw)
    return CreativeMmpDaily(**base)


def test_conv_ua_mixed_nupre_and_nu():
    """NU-Pre 등록 + NU D1잔존 합산이 mmp_conv_ua 로 주입되고 점수가 그 기준으로 랭크됨."""
    recs = [_rec("A"), _rec("B")]
    daily = [
        # A: NU-Pre 등록 10 + NU 잔존 20 → convUa 30
        _row("A", "X_NU-Pre_Y", conversions=10, retained_d1=0),
        _row("A", "X_NU_Y", conversions=0, retained_d1=20, installs=40),
        # B: NU 잔존 5 → convUa 5
        _row("B", "X_NU_Y", conversions=0, retained_d1=5, installs=10),
    ]
    inject_mmp_into_records(recs, daily, source_name="airbridge", conversion_basis="install")
    a = next(r for r in recs if r.creative_id == "A")
    b = next(r for r in recs if r.creative_id == "B")
    assert a.mmp_conv_ua == 30 and b.mmp_conv_ua == 5
    assert a.mmp_impressions == 20000 and b.mmp_impressions == 10000
    assert a.mmp_quality_score["total"] > b.mmp_quality_score["total"]  # convUa 30 > 5 (전 축 우위)


def test_conv_ua_ignores_other_ua_types():
    """RT/BR 등 그 외 캠페인의 전환·잔존은 convUa 에 미포함."""
    recs = [_rec("A")]
    daily = [
        _row("A", "X_RT_Y", conversions=50, retained_d1=50),
        _row("A", "X_NU_Y", conversions=0, retained_d1=7),
    ]
    inject_mmp_into_records(recs, daily, source_name="airbridge", conversion_basis="install")
    assert recs[0].mmp_conv_ua == 7


def test_registration_label_kept():
    """등록 기준 타이틀도 점수는 convUa 4축이되 convBasis 라벨은 '사전예약' 유지."""
    recs = [_rec("A")]
    daily = [_row("A", "X_NU-Pre_Y", conversions=100)]
    inject_mmp_into_records(recs, daily, source_name="airbridge", conversion_basis="registration")
    q = recs[0].mmp_quality_score
    assert recs[0].mmp_conv_ua == 100
    assert q["convBasis"] == "사전예약"
