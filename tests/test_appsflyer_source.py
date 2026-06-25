"""AppsFlyer MMP 소스 — 파서·제외·graceful·청크 단위테스트."""
from datetime import date
from pipeline.sources.appsflyer import (
    AppsFlyerMmpSource, extract_master, parse_master_rows,
    DEFAULT_EXCLUDE_MEDIA_SOURCES,
)


def test_extract_master_maps_headers():
    csv_text = "Ad,Media Source,Campaign,Date,Impressions,Clicks,Installs,Cost,Revenue\n" \
               "260616_VID_X,Facebook Ads,camp1,2026-06-20,1000,50,10,20.5,30.0\n"
    rows = extract_master(csv_text)
    assert len(rows) == 1
    r = rows[0]
    assert r["creative"] == "260616_VID_X"
    assert r["media_source"] == "Facebook Ads"
    assert r["campaign"] == "camp1"
    assert r["date"] == "2026-06-20"
    assert r["impressions"] == "1000"
    assert r["cost"] == "20.5"


def test_parse_master_basic_with_fx():
    rows = [{"creative": "A", "media_source": "facebook ads", "campaign": "c",
             "date": "2026-06-20", "impressions": "1000", "clicks": "50",
             "installs": "10", "cost": "20", "revenue": "30"}]
    out = parse_master_rows(rows, exclude=set(), fx_rate=1500.0)
    assert len(out) == 1
    d = out[0]
    assert d.creative_name == "A" and d.channel == "facebook ads"
    assert d.campaign_name == "c" and d.date == "2026-06-20"
    assert d.impressions == 1000 and d.clicks == 50 and d.installs == 10
    assert d.cost == 30000 and d.revenue_d7 == 45000   # ×fx
    assert d.retained_d1 == 0                            # v1


def test_parse_master_excludes_google_and_organic_and_empty():
    rows = [
        {"creative": "A", "media_source": "googleadwords_int", "date": "2026-06-20"},
        {"creative": "B", "media_source": "organic", "date": "2026-06-20"},
        {"creative": "", "media_source": "facebook", "date": "2026-06-20"},
        {"creative": "C", "media_source": "Facebook", "date": "2026-06-20", "installs": "5"},
    ]
    out = parse_master_rows(rows, exclude=set(DEFAULT_EXCLUDE_MEDIA_SOURCES))
    assert [d.creative_name for d in out] == ["C"]


def test_parse_master_graceful_missing_cost():
    # 설치>0·비용/노출 결측 → cost=0·impr=0, 설치·매출 보존 (분모 가드가 '—' 처리)
    rows = [{"creative": "A", "media_source": "facebook", "date": "2026-06-20",
             "installs": "10", "revenue": "5"}]
    out = parse_master_rows(rows, exclude=set())
    assert out[0].installs == 10 and out[0].revenue_d7 == 5
    assert out[0].cost == 0 and out[0].impressions == 0


def test_fetch_chunks_over_90_days_and_dedup():
    s = AppsFlyerMmpSource(token="x", app_id="y")
    calls = []
    csv_row = "Ad,Media Source,Date,Installs\nA,facebook,2026-06-20,3\n"

    def fake(cs, ce):
        calls.append((cs, ce))
        return csv_row
    s._fetch_master_csv = fake
    out = s.fetch_mmp_window(date(2025, 11, 1), date(2026, 5, 19), exclude_channels=set())
    assert len(calls) == 3
    assert calls[0] == (date(2025, 11, 1), date(2026, 1, 29))
    assert calls[1] == (date(2026, 1, 30), date(2026, 4, 29))
    assert calls[2] == (date(2026, 4, 30), date(2026, 5, 19))
    # 세 청크 모두 동일 (A,facebook,2026-06-20) → dedup → 1건
    assert len(out) == 1
