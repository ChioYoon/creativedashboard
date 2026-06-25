"""등록부 xlsx → titles.json 자동 생성.

CLOOP_REGISTRY_XLSX 가 가리키는 로컬 .xlsx(공유 드라이브 마운트)를 읽어
js/titles.json 을 생성한다. 인증/네트워크 불필요.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import openpyxl

# 기본값 (등록부에 없는 필드)
_DEF_TYPES = ["BNR", "VID"]
_DEF_GENRE = "character_collection_rpg"
_DEF_AB_EXCLUDE = ["google.adwords", "unattributed", "appstore", "sns", "airbridge_sdk_test"]
_DEF_USD_KRW = 1500


def _read_rows(xlsx_path) -> list[dict] | None:
    """첫 시트를 헤더→값 dict 행 리스트로. 파일 없음/읽기 실패 시 None."""
    p = Path(xlsx_path)
    if not p.exists():
        return None
    try:
        wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
    except Exception as e:
        print(f"[등록부] 읽기 실패: {e}")
        return None
    ws = wb.worksheets[0]
    it = ws.iter_rows(values_only=True)
    try:
        headers = [str(h).strip() if h is not None else "" for h in next(it)]
    except StopIteration:
        wb.close()
        return []
    out: list[dict] = []
    for raw in it:
        row = {}
        for i, h in enumerate(headers):
            if not h:
                continue
            v = raw[i] if i < len(raw) else None
            row[h] = "" if v is None else str(v).strip()
        if any(row.values()):
            out.append(row)
    wb.close()
    return out


def _active(row: dict) -> bool:
    return (row.get("활성화", "") or "").strip().upper() == "Y"


def _row_error(row: dict) -> str | None:
    tid = (row.get("타이틀 ID", "") or "").strip()
    if not tid:
        return "타이틀 ID 누락 행 스킵"
    if not (row.get("타이틀명", "") or "").strip():
        return f"{tid}: 타이틀명 누락 — 스킵"
    if not (row.get("로컬 스캔 경로", "") or "").strip():
        return f"{tid}: 로컬 스캔 경로 누락 — 스킵"
    return None


def _map_row(row: dict, repo_root: Path) -> dict:
    tid = row["타이틀 ID"].strip()
    types = [x.strip() for x in (row.get("소재 유형") or "BNR,VID").split(",") if x.strip()]
    t = {
        "id": tid,
        "name": row["타이틀명"].strip(),
        "json_url": f"public/data/{tid}.json",
        "_pipeline_enabled": True,
        "_pipeline_scan_mode": "by-filename",
        "_pipeline_creatives_root": row["로컬 스캔 경로"].strip(),
        "_pipeline_types": types or list(_DEF_TYPES),
        "_pipeline_genre": (row.get("장르") or "").strip() or _DEF_GENRE,
        "_pipeline_kpi_enabled": (row.get("광고 성과 연동", "N") or "N").strip().upper() == "Y",
    }
    folder = (row.get("소재 폴더 링크") or "").strip()
    if folder:
        t["drive_folder_url"] = folder
    if (repo_root / "pipeline" / "game_context" / f"{tid}.md").exists():
        t["_pipeline_game_context_file"] = f"pipeline/game_context/{tid}.md"
    if t["_pipeline_kpi_enabled"]:
        cid = (row.get("Google Ads ID") or "").strip()
        if cid:
            t["_pipeline_google_ads_customer_id"] = cid
            t["_pipeline_google_ads_campaign_filter"] = []
        mmp = (row.get("MMP 종류") or "").strip().lower()
        if mmp == "airbridge":
            t["_pipeline_airbridge_enabled"] = True
            t["_pipeline_airbridge_exclude_channels"] = list(_DEF_AB_EXCLUDE)
            t["_pipeline_airbridge_usd_to_krw"] = _DEF_USD_KRW
        # AppsFlyer: 소스 미구현 — 종류 보존만(범위 밖)
    return t


def _load_overrides(p: Path) -> dict:
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception as e:
        print(f"[등록부] overrides 읽기 실패(무시): {e}")
        return {}


def _existing_sample(out: Path) -> dict | None:
    if not out.exists():
        return None
    try:
        data = json.loads(out.read_text(encoding="utf-8"))
        return next((t for t in data if t.get("id") == "sample"), None)
    except Exception:
        return None


def _atomic_write_json(out: Path, data: list) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, out)


def build_titles_json(registry_xlsx_path, out_path="js/titles.json",
                      overrides_path="js/titles_overrides.json", repo_root=None) -> dict:
    repo_root = Path(repo_root) if repo_root else Path.cwd()
    out = Path(out_path)
    rows = _read_rows(registry_xlsx_path)
    if rows is None:
        return {"status": "skipped_no_registry", "generated": 0, "skipped": 0, "warnings": []}
    titles: list[dict] = []
    skipped = 0
    warnings: list[str] = []
    for row in rows:
        if not _active(row):
            skipped += 1
            continue
        err = _row_error(row)
        if err:
            skipped += 1
            warnings.append(err)
            print(f"[등록부] {err}")
            continue
        titles.append(_map_row(row, repo_root))
    ov = _load_overrides(Path(overrides_path))
    for t in titles:
        if t["id"] in ov and isinstance(ov[t["id"]], dict):
            t.update(ov[t["id"]])
    if not titles:
        return {"status": "empty_kept_existing", "generated": 0, "skipped": skipped, "warnings": warnings}
    sample = _existing_sample(out)
    result = titles + ([sample] if sample else [])
    _atomic_write_json(out, result)
    return {"status": "ok", "generated": len(titles), "skipped": skipped, "warnings": warnings}
