"""등록부 xlsx → titles.json 생성 단위 테스트."""
import json
from pathlib import Path
import openpyxl
import pytest
from pipeline import registry

HEADERS = ["타이틀 ID","타이틀명","소재 폴더 링크","소재 유형","장르","광고 성과 연동",
           "비고/요청","로컬 스캔 경로","Google Ads ID","MMP 종류","MMP 앱 식별자","활성화"]

def _make_xlsx(path, rows):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(HEADERS)
    for r in rows:
        ws.append(r)
    wb.save(path)
    return path

# 행 헬퍼: 컬럼 12개 순서대로
def _row(tid="newgame-us", name="뉴게임", folder="https://drive/x", types="BNR,VID",
         genre="character_collection_rpg", kpi="N", note="", root="G:\\공유\\x",
         gads="", mmp="없음", mmp_app="", active="Y"):
    return [tid,name,folder,types,genre,kpi,note,root,gads,mmp,mmp_app,active]


def test_read_rows_parses_headers(tmp_path):
    p = _make_xlsx(tmp_path/"r.xlsx", [_row()])
    rows = registry._read_rows(p)
    assert len(rows) == 1
    assert rows[0]["타이틀 ID"] == "newgame-us"
    assert rows[0]["활성화"] == "Y"

def test_read_rows_missing_file_returns_none(tmp_path):
    assert registry._read_rows(tmp_path/"nope.xlsx") is None

def test_active(tmp_path):
    assert registry._active({"활성화":"Y"}) is True
    assert registry._active({"활성화":"y"}) is True
    assert registry._active({"활성화":"N"}) is False
    assert registry._active({}) is False

def test_row_error_required(tmp_path):
    assert registry._row_error({"타이틀 ID":"", "타이틀명":"a", "로컬 스캔 경로":"b"})
    assert registry._row_error({"타이틀 ID":"a", "타이틀명":"", "로컬 스캔 경로":"b"})
    assert registry._row_error({"타이틀 ID":"a", "타이틀명":"b", "로컬 스캔 경로":""})
    assert registry._row_error({"타이틀 ID":"a", "타이틀명":"b", "로컬 스캔 경로":"c"}) is None

def test_map_row_basic(tmp_path):
    row = dict(zip(HEADERS, _row(tid="ng-us", name="뉴게임", types="BNR,VID",
                                 genre="dark_fantasy_card_rpg", kpi="N", root="G:\\x")))
    t = registry._map_row(row, tmp_path)
    assert t["id"] == "ng-us"
    assert t["name"] == "뉴게임"
    assert t["json_url"] == "public/data/ng-us.json"
    assert t["_pipeline_enabled"] is True
    assert t["_pipeline_scan_mode"] == "by-filename"
    assert t["_pipeline_types"] == ["BNR","VID"]
    assert t["_pipeline_genre"] == "dark_fantasy_card_rpg"
    assert t["_pipeline_kpi_enabled"] is False
    assert t["_pipeline_creatives_root"] == "G:\\x"
    assert t["drive_folder_url"] == "https://drive/x"
    assert "_pipeline_google_ads_customer_id" not in t   # KPI=N

def test_map_row_kpi_airbridge(tmp_path):
    row = dict(zip(HEADERS, _row(tid="kp", kpi="Y", gads="123", mmp="Airbridge", mmp_app="myapp")))
    t = registry._map_row(row, tmp_path)
    assert t["_pipeline_kpi_enabled"] is True
    assert t["_pipeline_google_ads_customer_id"] == "123"
    assert t["_pipeline_airbridge_enabled"] is True
    assert t["_pipeline_airbridge_usd_to_krw"] == 1500

def test_map_row_game_context_when_file_exists(tmp_path):
    gc = tmp_path/"pipeline"/"game_context"; gc.mkdir(parents=True)
    (gc/"hasctx.md").write_text("ctx", encoding="utf-8")
    row = dict(zip(HEADERS, _row(tid="hasctx")))
    t = registry._map_row(row, tmp_path)
    assert t["_pipeline_game_context_file"] == "pipeline/game_context/hasctx.md"
    row2 = dict(zip(HEADERS, _row(tid="noctx")))
    assert "_pipeline_game_context_file" not in registry._map_row(row2, tmp_path)


def _read_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))

def test_build_only_active_rows(tmp_path):
    xlsx = _make_xlsx(tmp_path/"r.xlsx", [
        _row(tid="a", name="A", root="G:\\a", active="Y"),
        _row(tid="b", name="B", root="G:\\b", active="N"),      # 비활성
        _row(tid="",  name="C", root="G:\\c", active="Y"),       # ID 누락
    ])
    out = tmp_path/"titles.json"
    s = registry.build_titles_json(xlsx, out_path=out, overrides_path=tmp_path/"ov.json", repo_root=tmp_path)
    assert s["status"] == "ok"
    assert s["generated"] == 1
    assert s["skipped"] == 2
    data = _read_json(out)
    assert [t["id"] for t in data] == ["a"]

def test_build_overrides_merge(tmp_path):
    xlsx = _make_xlsx(tmp_path/"r.xlsx", [_row(tid="t", name="T", root="G:\\t", active="Y")])
    ov = tmp_path/"ov.json"
    ov.write_text(json.dumps({"t": {"_pipeline_prompt_version_pin": "v9", "_pipeline_google_ads_window_days": 159}}), encoding="utf-8")
    out = tmp_path/"titles.json"
    registry.build_titles_json(xlsx, out_path=out, overrides_path=ov, repo_root=tmp_path)
    t = _read_json(out)[0]
    assert t["_pipeline_prompt_version_pin"] == "v9"
    assert t["_pipeline_google_ads_window_days"] == 159

def test_build_preserves_sample(tmp_path):
    out = tmp_path/"titles.json"
    out.write_text(json.dumps([{"id":"sample","_pipeline_enabled":False}], ensure_ascii=False), encoding="utf-8")
    xlsx = _make_xlsx(tmp_path/"r.xlsx", [_row(tid="a", name="A", root="G:\\a", active="Y")])
    registry.build_titles_json(xlsx, out_path=out, overrides_path=tmp_path/"ov.json", repo_root=tmp_path)
    data = _read_json(out)
    assert {t["id"] for t in data} == {"a", "sample"}

def test_build_missing_registry_keeps_existing(tmp_path):
    out = tmp_path/"titles.json"
    out.write_text(json.dumps([{"id":"orig"}], ensure_ascii=False), encoding="utf-8")
    s = registry.build_titles_json(tmp_path/"nope.xlsx", out_path=out, overrides_path=tmp_path/"ov.json", repo_root=tmp_path)
    assert s["status"] == "skipped_no_registry"
    assert _read_json(out) == [{"id":"orig"}]   # 기존 보존

def test_build_empty_keeps_existing(tmp_path):
    out = tmp_path/"titles.json"
    out.write_text(json.dumps([{"id":"orig"}], ensure_ascii=False), encoding="utf-8")
    xlsx = _make_xlsx(tmp_path/"r.xlsx", [_row(tid="a", name="A", root="G:\\a", active="N")])  # 활성 0
    s = registry.build_titles_json(xlsx, out_path=out, overrides_path=tmp_path/"ov.json", repo_root=tmp_path)
    assert s["status"] == "empty_kept_existing"
    assert _read_json(out) == [{"id":"orig"}]

def test_map_row_appsflyer_provider(tmp_path):
    from pipeline.registry import _map_row
    row = {
        "타이틀 ID": "gd-global", "타이틀명": "갓앤데몬", "로컬 스캔 경로": "G:\\x",
        "광고 성과 연동": "Y", "MMP 종류": "appsflyer",
        "MMP 앱 식별자": "com.com2us.gd.android.google.global.normal",
    }
    t = _map_row(row, tmp_path)
    assert t["_pipeline_mmp_provider"] == "appsflyer"
    assert t["_pipeline_appsflyer_app_id"] == "com.com2us.gd.android.google.global.normal"
    assert t["_pipeline_airbridge_usd_to_krw"] == 1500


def test_map_row_airbridge_sets_provider(tmp_path):
    from pipeline.registry import _map_row
    row = {"타이틀 ID": "pepp-us", "타이틀명": "펩", "로컬 스캔 경로": "G:\\x",
           "광고 성과 연동": "Y", "MMP 종류": "airbridge"}
    t = _map_row(row, tmp_path)
    assert t["_pipeline_mmp_provider"] == "airbridge"
    assert t["_pipeline_airbridge_enabled"] is True
