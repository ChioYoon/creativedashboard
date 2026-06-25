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
