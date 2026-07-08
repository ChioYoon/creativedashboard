from pipeline.schemas import CreativeMmpDaily, CreativeRecord


def test_creative_mmp_daily_has_conversions_default_zero():
    d = CreativeMmpDaily(creative_name="c", date="2026-07-01", channel="meta.business")
    assert d.conversions == 0
    d2 = CreativeMmpDaily(creative_name="c", date="2026-07-01", channel="x", conversions=15)
    assert d2.conversions == 15


def test_creative_record_has_mmp_conversions_default_none():
    r = CreativeRecord(creative_id="k", 소재명="k", 파일명="k.jpg", 유형="VID")
    assert r.mmp_conversions is None
