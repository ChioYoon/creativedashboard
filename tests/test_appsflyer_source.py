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


def test_from_env_missing_token_raises(monkeypatch):
    import pytest
    monkeypatch.delenv("APPSFLYER_API_TOKEN", raising=False)
    with pytest.raises(FileNotFoundError):
        AppsFlyerMmpSource.from_env(app_id="com.x")


def test_from_env_missing_app_id_raises(monkeypatch):
    import pytest
    monkeypatch.setenv("APPSFLYER_API_TOKEN", "tok")
    with pytest.raises(FileNotFoundError):
        AppsFlyerMmpSource.from_env(app_id="")


# ── 라이브 검증 확정 계약 (2026-06-26 Starseed JP): 실제 Master API CSV 헤더 ──

def test_extract_master_real_headers_install_time_retention():
    """실제 헤더 — Install Time→date, Retention Day 1→retained_d1 매핑."""
    csv_text = ("Ad,Media Source,Campaign,Install Time,Impressions,Clicks,Installs,Cost,Revenue,Retention Day 1\n"
                "250911_VID_X,Facebook Ads,camp,2026-06-07,0,0,1,0,5.99,1\n")
    rows = extract_master(csv_text)
    assert len(rows) == 1
    r = rows[0]
    assert r["date"] == "2026-06-07"          # Install Time
    assert r["retained_d1"] == "1"            # Retention Day 1
    assert r["installs"] == "1" and r["revenue"] == "5.99"


def test_parse_master_populates_retained_d1():
    """retention_day_1 kpi → retained_d1(count) 채워짐 (v1 의 하드코딩 0 아님)."""
    rows = [{"creative": "A", "media_source": "facebook ads", "date": "2026-06-07",
             "installs": "10", "retained_d1": "4", "revenue": "5.99"}]
    out = parse_master_rows(rows, exclude=set())
    assert out[0].retained_d1 == 4
    assert out[0].installs == 10


def test_parse_master_skips_none_creative():
    """Ad='None'(오가닉/비소재 행)은 skip — 실제 응답에 'None' 문자열로 옴."""
    rows = [
        {"creative": "None", "media_source": "page", "date": "2026-06-07", "installs": "8"},
        {"creative": "C", "media_source": "facebook", "date": "2026-06-07", "installs": "1"},
    ]
    out = parse_master_rows(rows, exclude=set())
    assert [d.creative_name for d in out] == ["C"]
