from pipeline.schemas import CreativeMmpDaily
from pipeline.mmp_metrics import aggregate_rows_total


def test_aggregate_sums_conversions():
    rows = [
        CreativeMmpDaily(creative_name="c", date="2026-07-01", channel="meta", conversions=100, cost=1000, impressions=5000),
        CreativeMmpDaily(creative_name="c", date="2026-07-02", channel="meta", conversions=50, cost=500, impressions=2500),
    ]
    a = aggregate_rows_total(rows)
    assert a["conversions"] == 150
    assert a["cost"] == 1500
