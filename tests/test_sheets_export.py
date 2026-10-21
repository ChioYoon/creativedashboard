"""Google Sheets exporter 테스트 — 게이팅·값 변환·쓰기 요청 순서(fake session)."""
import json

import pytest

from pipeline.sheets_export import (
    COLUMNS, build_tables, load_sheets_config, main, parse_spreadsheet_id, split_by_output,
    to_values, write_tables,
)


def test_gating(tmp_path):
    key = tmp_path / "sa.json"
    key.write_text("{}", encoding="utf-8")
    ok = {"SHEETS_EXPORT_ENABLED": "1", "SHEETS_CREDENTIALS": str(key),
          "SHEETS_SPREADSHEET_ID": "https://docs.google.com/spreadsheets/d/AbC_1-x/edit#gid=0"}
    assert load_sheets_config(ok) == {"spreadsheet_id": "AbC_1-x", "credentials_path": str(key)}
    assert load_sheets_config({**ok, "SHEETS_EXPORT_ENABLED": "0"}) is None
    assert load_sheets_config({**ok, "SHEETS_SPREADSHEET_ID": ""}) is None
    assert load_sheets_config({**ok, "SHEETS_CREDENTIALS": str(tmp_path / "nope.json")}) is None
    # SHEETS_CREDENTIALS 없으면 GOOGLE_APPLICATION_CREDENTIALS 폴백
    fb = {k: v for k, v in ok.items() if k != "SHEETS_CREDENTIALS"}
    assert load_sheets_config({**fb, "GOOGLE_APPLICATION_CREDENTIALS": str(key)}) is not None
    assert parse_spreadsheet_id(" raw_id ") == "raw_id"


def test_to_values_header_and_cells():
    v = to_values("creatives", [{"creative_name": "=HYPERLINK()", "theme_secondary": ["a", "b"],
                                 "theme_reviewed": True, "core_usp": None}])
    assert v[0] == COLUMNS["creatives"]
    row = dict(zip(v[0], v[1]))
    assert row["creative_name"] == "=HYPERLINK()"   # RAW 로 쓰므로 그대로
    assert row["theme_secondary"] == "a, b"
    assert row["theme_reviewed"] is True
    assert row["core_usp"] == "" and row["title_id"] == ""


def _write_title(d, tid, n_kpi):
    ds = {"title_id": tid, "generated_at": "2026-10-13T00:00:00Z", "creatives": [
        {"소재명": f"{tid}_c", "kpi_daily": [{"date": f"2026-10-{i + 1:02d}", "impressions": 1}
                                            for i in range(n_kpi)]}]}
    (d / f"{tid}.json").write_text(json.dumps(ds), encoding="utf-8")


def test_build_tables_merges_titles_and_fails_whole(tmp_path):
    _write_title(tmp_path, "a", 2)
    _write_title(tmp_path, "b", 3)
    t = build_tables(str(tmp_path), ["a", "b"], "L")
    assert len(t["kpi_daily"]) == 5 and len(t["creatives"]) == 2 and t["axis"] == []
    assert {r["title_id"] for r in t["kpi_daily"]} == {"a", "b"}
    with pytest.raises(FileNotFoundError):   # 한 타이틀이라도 없으면 전체 중단
        build_tables(str(tmp_path), ["a", "missing"], "L")


def test_split_by_output(tmp_path):
    _write_title(tmp_path, "a", 1)
    assert split_by_output(str(tmp_path), ["a", "new"]) == (["a"], ["new"])


def test_main_skips_title_without_output(tmp_path, caplog):
    """산출 JSON 없는 타이틀(신규·소재 0개)은 제외하고 나머지는 진행 — 전체 중단하지 않는다."""
    _write_title(tmp_path, "a", 2)
    rc = main(["--data-dir", str(tmp_path), "--titles", "a,new", "--dry-run"])
    assert rc == 0
    assert "new" in caplog.text and "제외" in caplog.text


def test_main_aborts_when_no_title_has_output(tmp_path):
    """올릴 타이틀이 하나도 없으면 빈 시트로 덮어쓰지 않도록 중단."""
    assert main(["--data-dir", str(tmp_path), "--titles", "new", "--dry-run"]) == 1


def test_main_aborts_on_corrupt_json(tmp_path):
    """JSON 은 있는데 손상 → 기존대로 전체 중단(일부 타이틀만 올라가 BI 에서 사라지는 것 방지)."""
    _write_title(tmp_path, "a", 1)
    (tmp_path / "b.json").write_text("{broken", encoding="utf-8")
    assert main(["--data-dir", str(tmp_path), "--titles", "a,b", "--dry-run"]) == 1


class _Resp:
    def __init__(self, body, code=200):
        self.status_code, self._b, self.text = code, body, json.dumps(body)

    def json(self):
        return self._b


class FakeSession:
    def __init__(self, existing=("kpi_daily",), fail_on=None):
        self.calls, self.existing, self.fail_on = [], existing, fail_on

    def request(self, method, url, timeout=None, params=None, json=None):
        self.calls.append((method, url.rsplit("/", 1)[-1], json))
        if self.fail_on and self.fail_on in url:
            return _Resp({"error": "x"}, 403)
        if method == "GET":
            return _Resp({"sheets": [{"properties": {"title": t, "sheetId": i}}
                                     for i, t in enumerate(self.existing)]})
        if json and json.get("requests", [{}])[0].get("addSheet"):
            return _Resp({"replies": [{"addSheet": {"properties": {
                "title": r["addSheet"]["properties"]["title"], "sheetId": 100 + i}}}
                for i, r in enumerate(json["requests"])]})
        return _Resp({})


def test_write_tables_sequence_and_chunking(monkeypatch):
    import pipeline.sheets_export as se
    monkeypatch.setattr(se, "CHUNK_ROWS", 2)
    s = FakeSession()
    values = {"kpi_daily": [["h"], [1], [2], [3]], "axis": [["h"]]}
    write_tables(s, "SID", values)
    kinds = [c[1] for c in s.calls]
    assert kinds[:4] == ["SID", "SID:batchUpdate", "SID:batchUpdate", "values:batchClear"]
    assert s.calls[1][2]["requests"] == [{"addSheet": {"properties": {"title": "axis"}}}]
    resize = {r["updateSheetProperties"]["properties"]["sheetId"]:
              r["updateSheetProperties"]["properties"]["gridProperties"]["rowCount"]
              for r in s.calls[2][2]["requests"]}
    assert resize == {0: 4, 100: 2}      # 데이터 크기에 맞춤(최소 2행)
    writes = [c[2]["data"][0] for c in s.calls if c[1] == "values:batchUpdate"]
    assert [w["range"] for w in writes] == ["'kpi_daily'!A1", "'kpi_daily'!A3", "'axis'!A1"]
    assert writes[1]["values"] == [[2], [3]]
    assert all(c[2]["valueInputOption"] == "RAW" for c in s.calls if c[1] == "values:batchUpdate")


def test_write_tables_raises_on_api_error():
    with pytest.raises(RuntimeError, match="403"):
        write_tables(FakeSession(fail_on="batchClear"), "SID", {"kpi_daily": [["h"]]})
