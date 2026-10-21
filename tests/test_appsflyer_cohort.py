"""AppsFlyer Cohort API(D7 매출) 연동 — 가짜 응답(네트워크·토큰 없음) 단위테스트.

⚠️ Cohort 응답 CSV 의 실제 열 이름은 공식 문서에 없음. 아래 가짜 응답은 예상 형태(와이드·롱)이며,
첫 라이브 호출로 실제 헤더를 확인하면 그 형태의 테스트를 추가할 것.
"""
from datetime import date

import pytest

from pipeline.base_errors import AuthError
from pipeline.sources.appsflyer import (
    AppsFlyerMmpSource, CohortFormatError, cohort_request_body, extract_cohort_revenue, mmp_key,
)

MASTER = ("Ad,Media Source,Campaign,Install Time,Impressions,Clicks,Installs,Cost,Revenue,Retention Day 1\n"
          "260901_VID_A,Facebook Ads,NU_AOS,2026-10-01,1000,50,10,20,99,4\n"     # Master revenue=LTV 99
          "260901_VID_A,Facebook Ads,NU_AOS,2026-10-15,800,40,8,16,30,3\n"
          "260901_BNR_B,TikTok,NU_AOS,2026-10-01,500,20,5,10,50,2\n")             # Cohort 에 없음 → 0

# 와이드형: Day 별 누적 매출 열(+count 열·Day 8 열은 무시돼야 함)
COHORT_WIDE = ("Ad,Media Source,Campaign,Date,Users,Cost,"
               "Revenue Count Day 0,Revenue Sum Day 0,Revenue Sum Day 3,Revenue Sum Day 7,Revenue Sum Day 8\n"
               "260901_VID_A,Facebook Ads,NU_AOS,2026-10-01,10,20,1,5,12,20,25\n"      # 완성 → D7=20
               "260901_VID_A,Facebook Ads,NU_AOS,2026-10-15,8,16,1,2,6,N/A,\n")        # 미완성 → D3=6


def _src(**kw):
    s = AppsFlyerMmpSource(token="x", app_id=kw.pop("app_id", "com.app"), usd_to_krw=1500, cohort_d7=True, **kw)
    s._fetch_master_csv = lambda cs, ce, app_id=None: MASTER
    return s


def test_request_body_matches_master_unit_and_d7_basis():
    b = cohort_request_body(date(2026, 10, 1), date(2026, 10, 31))
    assert b["groupings"] == ["af_ad", "pid", "c", "date"]            # Master 와 같은 단위
    assert b["kpis"] == ["revenue"] and b["aggregation_type"] == "cumulative"
    assert b["filters"]["period"] == [0, 1, 2, 3, 4, 5, 6, 7]          # Day 0~7
    assert b["filters"]["revenue_type"] == ["regular"]                  # 인앱 구매만
    assert b["partial_data"] is True and b["cohort_type"] == "user_acquisition"
    assert b["preferred_timezone"] is False and b["preferred_currency"] is False   # Master 와 동일 시간대·USD


def test_extract_wide_uses_last_available_day_up_to_7():
    rev = extract_cohort_revenue(COHORT_WIDE)
    assert rev[mmp_key("260901_VID_A", "facebook ads", "NU_AOS", "2026-10-01")] == 20.0   # D7 (Day 8 무시)
    assert rev[mmp_key("260901_VID_A", "facebook ads", "NU_AOS", "2026-10-15")] == 6.0    # 미완성 → D3 까지 누적


def test_extract_long_format_with_period_column():
    csv_text = ("af_ad,pid,c,date,period,revenue_sum\n"
                "A,facebook,c1,2026-10-01,0,1\nA,facebook,c1,2026-10-01,7,9\nA,facebook,c1,2026-10-01,9,99\n")
    rev = extract_cohort_revenue(csv_text)
    assert rev == {mmp_key("A", "facebook", "c1", "2026-10-01"): 9.0}


def test_extract_raises_when_no_revenue_columns():
    with pytest.raises(CohortFormatError):
        extract_cohort_revenue("Ad,Media Source,Campaign,Date,Users\nA,f,c,2026-10-01,3\n")


def test_fetch_replaces_master_ltv_with_cohort_d7():
    s = _src()
    s._fetch_cohort_csv = lambda cs, ce, app_id=None: COHORT_WIDE
    out = {(r.creative_name, r.date): r for r in s.fetch_mmp_window(date(2026, 10, 1), date(2026, 10, 18), exclude_channels=set())}
    assert out[("260901_VID_A", "2026-10-01")].revenue_d7 == 20 * 1500    # LTV 99 → D7 20 (×fx)
    assert out[("260901_VID_A", "2026-10-15")].revenue_d7 == 6 * 1500     # 미완성 D3
    assert out[("260901_BNR_B", "2026-10-01")].revenue_d7 == 0            # Cohort 에 없음 = 인앱 매출 0
    # 매출 외 지표는 Master 그대로
    assert out[("260901_VID_A", "2026-10-01")].installs == 10 and out[("260901_VID_A", "2026-10-01")].retained_d1 == 4
    assert s.revenue_source == "cohort" and s.revenue_cohort_matched == 2 and s.revenue_fallback_reason == ""


def test_cohort_failure_keeps_master_revenue():
    s = _src()

    def boom(cs, ce, app_id=None):
        raise AuthError("AppsFlyer 인증 실패: 401")
    s._fetch_cohort_csv = boom
    out = {(r.creative_name, r.date): r for r in s.fetch_mmp_window(date(2026, 10, 1), date(2026, 10, 18), exclude_channels=set())}
    assert out[("260901_VID_A", "2026-10-01")].revenue_d7 == 99 * 1500    # Master LTV 유지
    assert s.revenue_source == "master_fallback" and "401" in s.revenue_fallback_reason


def test_cohort_key_mismatch_falls_back():
    s = _src()
    s._fetch_cohort_csv = lambda cs, ce, app_id=None: ("Ad,Media Source,Campaign,Date,Revenue Sum Day 7\n"
                                                       "OTHER,x,y,2026-10-01,5\n")
    out = s.fetch_mmp_window(date(2026, 10, 1), date(2026, 10, 18), exclude_channels=set())
    assert s.revenue_source == "master_fallback" and "매칭" in s.revenue_fallback_reason
    assert sorted(r.revenue_d7 for r in out) == sorted(v * 1500 for v in (99, 30, 50))


def test_cohort_disabled_keeps_master():
    s = _src()
    s.cohort_d7 = False
    s._fetch_cohort_csv = lambda *a, **k: pytest.fail("Cohort 비활성인데 호출됨")
    s.fetch_mmp_window(date(2026, 10, 1), date(2026, 10, 18), exclude_channels=set())
    assert s.revenue_source == "master"


def test_multiple_apps_merge_by_key_and_sum():
    s = AppsFlyerMmpSource(token="x", app_id="com.aos\nid123", usd_to_krw=1.0, cohort_d7=True)
    assert s.app_ids == ["com.aos", "id123"]
    s._fetch_master_csv = lambda cs, ce, app_id=None: ("Ad,Media Source,Campaign,Install Time,Installs,Revenue\n"
                                                       f"A,facebook,c1,2026-10-01,{3 if app_id == 'com.aos' else 2},0\n")
    s._fetch_cohort_csv = lambda cs, ce, app_id=None: ("Ad,Media Source,Campaign,Date,Revenue Sum Day 7\n"
                                                       f"A,facebook,c1,2026-10-01,{10 if app_id == 'com.aos' else 4}\n")
    out = s.fetch_mmp_window(date(2026, 10, 1), date(2026, 10, 5), exclude_channels=set())
    assert len(out) == 1 and out[0].installs == 5 and out[0].revenue_d7 == 14   # Android+iOS 합산
    assert s.revenue_source == "cohort"


def test_one_app_cohort_failure_reverts_all_apps_to_master():
    """일부 앱만 D7 로 바뀌면 기준이 섞임 → 하나라도 실패하면 전 앱 Master 로 통일."""
    s = AppsFlyerMmpSource(token="x", app_id=["com.aos", "id123"], usd_to_krw=1.0, cohort_d7=True)
    s._fetch_master_csv = lambda cs, ce, app_id=None: ("Ad,Media Source,Campaign,Install Time,Installs,Revenue\n"
                                                       "A,facebook,c1,2026-10-01,1,50\n")

    def cohort(cs, ce, app_id=None):
        if app_id == "id123":
            raise RuntimeError("AppsFlyer HTTP 오류: 422")
        return "Ad,Media Source,Campaign,Date,Revenue Sum Day 7\nA,facebook,c1,2026-10-01,10\n"
    s._fetch_cohort_csv = cohort
    out = s.fetch_mmp_window(date(2026, 10, 1), date(2026, 10, 5), exclude_channels=set())
    assert out[0].revenue_d7 == 100                     # 50(Android Master) + 50(iOS Master)
    assert s.revenue_source == "master_fallback" and s.revenue_cohort_matched == 0


def test_from_env_enables_cohort_and_env_can_disable(monkeypatch):
    monkeypatch.setenv("APPSFLYER_API_TOKEN", "tok")
    monkeypatch.delenv("APPSFLYER_COHORT_D7", raising=False)
    assert AppsFlyerMmpSource.from_env(app_id="com.x").cohort_d7 is True
    monkeypatch.setenv("APPSFLYER_COHORT_D7", "0")
    assert AppsFlyerMmpSource.from_env(app_id="com.x").cohort_d7 is False
