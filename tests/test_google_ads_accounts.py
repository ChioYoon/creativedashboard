"""타이틀 하나에 Google Ads 계정 여러 개(SB: 나라별 계정) — 설정 파싱·계정별 조회 합산·단일계정 전용 명령 가드."""
import json

import pytest

from pipeline.sources.google_ads import customer_ids_of


def test_customer_ids_of_accepts_string_list_and_separators():
    assert customer_ids_of("3250895166") == ["3250895166"]            # 기존 타이틀(문자열 1개) 그대로
    assert customer_ids_of("325-089-5166") == ["3250895166"]          # 하이픈 제거
    assert customer_ids_of("111, 222\n333") == ["111", "222", "333"]  # 쉼표·줄바꿈 구분
    assert customer_ids_of(["111", "222-0", "111", ""]) == ["111", "2220"]   # 목록·중복·빈값
    assert customer_ids_of("") == [] and customer_ids_of(None) == []


class _FakeSource:
    def __init__(self, fail_on=None):
        self.calls, self.fail_on = [], fail_on

    def fetch_window(self, customer_id, **kw):
        self.calls.append((customer_id, kw))
        if customer_id == self.fail_on:
            raise RuntimeError("boom")
        return [f"{customer_id}-r1", f"{customer_id}-r2"]


def test_fetch_kpi_accounts_merges_each_account(monkeypatch):
    from pipeline import main
    monkeypatch.setattr(main.time, "sleep", lambda s: None)
    src = _FakeSource()
    rows = main._fetch_kpi_accounts(src, ["111", "222"], start="S", end="E")
    assert rows == ["111-r1", "111-r2", "222-r1", "222-r2"]
    assert [c[0] for c in src.calls] == ["111", "222"]
    assert all(c[1] == {"start": "S", "end": "E"} for c in src.calls)   # 같은 조건으로 계정마다 호출


def test_fetch_kpi_accounts_fails_whole_when_one_account_fails(monkeypatch):
    """한 계정이라도 끝내 실패하면 전체 실패 — 일부 계정만 반영된 성과로 산출되지 않게."""
    from pipeline import main
    monkeypatch.setattr(main.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError):
        main._fetch_kpi_accounts(_FakeSource(fail_on="222"), ["111", "222"])


def test_pause_refuses_multi_account_title(tmp_path):
    """라이브 광고를 바꾸는 pause 는 계정이 여러 개면 임의 계정을 고르지 않고 거부."""
    from pipeline.pause import customer_id_for_title
    p = tmp_path / "titles.json"
    p.write_text(json.dumps([
        {"id": "one", "_pipeline_google_ads_customer_id": "325-089-5166"},
        {"id": "multi", "_pipeline_google_ads_customer_id": ["111", "222"]},
    ]), encoding="utf-8")
    assert customer_id_for_title("one", str(p)) == "3250895166"
    with pytest.raises(ValueError, match="여러 개"):
        customer_id_for_title("multi", str(p))
