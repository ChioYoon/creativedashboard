"""CLOOP JSON → Google Sheets 내보내기 (BI 포털 연동용).

public/data/{title}.json(+_axis.json)을 bq_export 의 행 변환 함수로 평탄화해
지정 스프레드시트의 4탭(kpi_daily·mmp_daily·creatives·axis)을 매일 전체 교체.
타이틀은 title_id 컬럼으로 구분(합본). nightly git push 뒤 격리 실행 — 게이팅·graceful.
셋업: docs/sheets-export-setup.md
"""
from __future__ import annotations

import argparse
import json as _json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from pipeline.bq_export import TABLE_SPECS, _TABLE_ROWS

log = logging.getLogger("sheets_export")

API = "https://sheets.googleapis.com/v4/spreadsheets"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CHUNK_ROWS = 5000            # values.batchUpdate 요청당 행 수(페이로드 수 MB 이하 유지)
MAX_CELLS = 9_000_000        # 스프레드시트 한도 1,000만 셀 — 여유 두고 차단

# 탭별 컬럼 순서 = BQ 스키마 순서(헤더 행)
COLUMNS = {t: [f.name for f in spec["schema"]] for t, spec in TABLE_SPECS.items()}


def parse_spreadsheet_id(v: str) -> str:
    """시트 URL 또는 ID → ID."""
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", v or "")
    return m.group(1) if m else (v or "").strip()


def load_sheets_config(env: dict | None = None) -> dict | None:
    """env → 설정 dict. 비활성/키부재/시트 미지정이면 None(스킵).

    SHEETS_EXPORT_ENABLED=1, SHEETS_SPREADSHEET_ID(URL 가능),
    SHEETS_CREDENTIALS(없으면 GOOGLE_APPLICATION_CREDENTIALS) 서비스 계정 키 경로.
    """
    e = env if env is not None else os.environ
    if (e.get("SHEETS_EXPORT_ENABLED") or "") != "1":
        return None
    creds = e.get("SHEETS_CREDENTIALS") or e.get("GOOGLE_APPLICATION_CREDENTIALS") or ""
    if not creds or not Path(creds).exists():
        return None
    sid = parse_spreadsheet_id(e.get("SHEETS_SPREADSHEET_ID") or "")
    if not sid:
        return None
    return {"spreadsheet_id": sid, "credentials_path": creds}


def enabled_titles(titles_json: str = "js/titles.json") -> list[str]:
    """nightly 처리 대상(_pipeline_enabled=true) 타이틀 id — 레거시 JSON(gd·pepp-us) 제외."""
    raw = _json.loads(Path(titles_json).read_text(encoding="utf-8"))
    return [t["id"] for t in raw if t.get("_pipeline_enabled")]


def _cell(v):
    """행 값 → 시트 셀 값. None→빈칸, 리스트→', ' 결합, 숫자·bool 유지."""
    if v is None:
        return ""
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    return v


def to_values(table: str, rows: list[dict]) -> list[list]:
    """헤더 + 데이터 행(2차원 배열)."""
    cols = COLUMNS[table]
    return [cols] + [[_cell(r.get(c)) for c in cols] for r in rows]


def split_by_output(data_dir: str, titles: list[str]) -> tuple[list[str], list[str]]:
    """(산출 JSON 있는 타이틀, 없는 타이틀). 없는 타이틀 = 아직 한 번도 산출되지 않은 타이틀
    (소재 0개면 파이프라인이 JSON 을 쓰지 않음 — 예: 파일명 규칙 미적용 신규 타이틀).
    fetch 실패일은 이전 JSON 을 유지하므로 여기서 '없음'으로 잡히지 않는다."""
    p = Path(data_dir)
    present = [t for t in titles if (p / f"{t}.json").exists()]
    return present, [t for t in titles if t not in present]


def build_tables(data_dir: str, titles: list[str], loaded_at: str) -> dict[str, list[dict]]:
    """전 타이틀 행을 탭별로 합침. 한 타이틀이라도 로드 실패면 예외 —
    합본 전체 교체라 일부 타이틀만 올리면 BI 에서 그 타이틀 행이 사라지므로 업로드 자체를 중단."""
    out = {t: [] for t in _TABLE_ROWS}
    p = Path(data_dir)
    for tid in titles:
        ds = _json.loads((p / f"{tid}.json").read_text(encoding="utf-8"))
        ax_path = p / f"{tid}_axis.json"
        ax = _json.loads(ax_path.read_text(encoding="utf-8")) if ax_path.exists() else None
        for table, rowfn in _TABLE_ROWS.items():
            out[table].extend(rowfn(ds, ax, tid, loaded_at))
    return out


def write_tables(session, spreadsheet_id: str, values: dict[str, list[list]]) -> None:
    """탭 생성·그리드 크기 맞춤 → clear → RAW 청크 쓰기. session 은 AuthorizedSession(테스트 fake 가능).
    RAW: '=' 로 시작하는 소재명도 수식으로 해석되지 않음."""
    def call(method, url, **kw):
        r = session.request(method, url, timeout=120, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"Sheets API {r.status_code}: {r.text[:300]}")
        return r.json()

    base = f"{API}/{spreadsheet_id}"
    meta = call("GET", base, params={"fields": "sheets.properties(sheetId,title)"})
    existing = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta.get("sheets", [])}

    adds = [{"addSheet": {"properties": {"title": t}}} for t in values if t not in existing]
    if adds:
        res = call("POST", f"{base}:batchUpdate", json={"requests": adds})
        for rep in res.get("replies", []):
            p = rep["addSheet"]["properties"]
            existing[p["title"]] = p["sheetId"]

    # 그리드를 데이터 크기에 정확히 맞춤 — 늘릴 땐 쓰기 가능, 줄일 땐 이전 잔여 행 제거(셀 수 절약)
    resize = [{"updateSheetProperties": {
        "properties": {"sheetId": existing[t], "gridProperties": {
            "rowCount": max(len(v), 2), "columnCount": len(v[0]), "frozenRowCount": 1}},
        "fields": "gridProperties(rowCount,columnCount,frozenRowCount)"}} for t, v in values.items()]
    call("POST", f"{base}:batchUpdate", json={"requests": resize})
    call("POST", f"{base}/values:batchClear", json={"ranges": [f"'{t}'" for t in values]})

    for t, v in values.items():
        for i in range(0, len(v), CHUNK_ROWS):
            call("POST", f"{base}/values:batchUpdate", json={
                "valueInputOption": "RAW",
                "data": [{"range": f"'{t}'!A{i + 1}", "values": v[i:i + CHUNK_ROWS]}]})


def main(argv=None) -> int:
    """CLOOP JSON → Google Sheets CLI. 비활성이면 graceful 스킵(0). 실패는 1(nightly 는 WARN 만)."""
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser(description="CLOOP JSON → Google Sheets 내보내기")
    ap.add_argument("--data-dir", default="public/data")
    ap.add_argument("--titles", default="", help="쉼표 구분. 비우면 titles.json _pipeline_enabled 타이틀")
    ap.add_argument("--dry-run", action="store_true", help="행·셀 수만 출력(인증·네트워크 없음)")
    args = ap.parse_args(argv)

    from dotenv import load_dotenv
    load_dotenv()
    cfg = load_sheets_config()
    if cfg is None and not args.dry_run:
        log.info("sheets_export: 비활성(SHEETS_EXPORT_ENABLED≠1·키·시트ID 부재) — 스킵")
        return 0

    titles = [t for t in args.titles.split(",") if t] or enabled_titles()
    # 산출 JSON 이 아직 없는 타이틀은 건너뛰고 나머지만 올린다(한 타이틀 때문에 전체 갱신이 멈추지 않게).
    # JSON 이 있는데 읽기 실패(손상)한 경우는 아래 build_tables 에서 기존대로 전체 중단.
    titles, missing = split_by_output(args.data_dir, titles)
    if missing:
        log.warning("sheets_export: 산출 JSON 없는 타이틀 제외(아직 산출 전) — %s", missing)
    if not titles:
        log.error("sheets_export: 올릴 타이틀 없음 — 업로드 중단(이전 시트 유지)")
        return 1
    loaded_at = datetime.now(timezone.utc).isoformat()
    try:
        tables = build_tables(args.data_dir, titles, loaded_at)
    except Exception as e:
        log.error("sheets_export: JSON 로드 실패 — 업로드 중단(이전 시트 유지): %s", e)
        return 1
    values = {t: to_values(t, rows) for t, rows in tables.items()}
    cells = sum(len(v) * len(v[0]) for v in values.values())
    log.info("sheets_export: 타이틀=%s 행=%s 셀=%d",
             titles, {t: len(v) - 1 for t, v in values.items()}, cells)
    if cells > MAX_CELLS:
        log.error("sheets_export: 셀 %d > 한도 %d — 업로드 중단", cells, MAX_CELLS)
        return 1
    if args.dry_run:
        return 0

    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account
    creds = service_account.Credentials.from_service_account_file(
        cfg["credentials_path"], scopes=SCOPES)
    try:
        write_tables(AuthorizedSession(creds), cfg["spreadsheet_id"], values)
    except Exception as e:
        log.error("sheets_export: 업로드 실패: %s", e)
        return 1
    log.info("sheets_export: 업로드 완료 — https://docs.google.com/spreadsheets/d/%s",
             cfg["spreadsheet_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
