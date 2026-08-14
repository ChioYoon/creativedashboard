"""
pause_tool 매핑(순수 로직) — 제외추천 CSV + public/data JSON → 제거 대상 asset 후보.

대시보드 key(소재명=creative_id)는 정규화값이라 Google Ads asset에 직접 안 붙음.
실제 asset은 creative의 kpi_daily[]에 (creative_name=raw 이름, asset_id=Phase 1b) 로 있음.
1소재 = N asset(L/S/V 영상 + 병합된 BNR) → 전부 펼침. 제거는 VIDEO만(영상 리스트 기반), IMAGE는 별도 고지.

API·파일 I/O 없음(테스트 용이). 서버는 이 함수들에 데이터만 넣어 씀.
"""
from __future__ import annotations

import csv
import io


def parse_reco_csv(text: str) -> list[str]:
    """제외추천 CSV → 추천 소재 key(소재명) 리스트. 첫 컬럼='소재명'. BOM·헤더 처리."""
    text = text.lstrip("﻿")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return []
    header = [h.strip() for h in rows[0]]
    idx = header.index("소재명") if "소재명" in header else 0
    keys, seen = [], set()
    for r in rows[1:]:
        if idx >= len(r):
            continue
        k = r[idx].strip()
        if k and k not in seen:
            seen.add(k)
            keys.append(k)
    return keys


def expand_assets(creative: dict) -> dict:
    """creative → {'videos':[...], 'images':[...]}. kpi_daily에서 이름 dedup, 타입 분리.

    각 원소: {'name': raw creative_name, 'asset_id': str|None}.
    """
    videos, images, seen = {}, {}, set()
    for r in creative.get("kpi_daily") or []:
        name = r.get("creative_name")
        if not name or name in seen:
            continue
        seen.add(name)
        item = {"name": name, "asset_id": r.get("asset_id")}
        if str(r.get("asset_type") or "").upper() == "YOUTUBE_VIDEO":
            videos[name] = item
        else:
            images[name] = item
    return {"videos": list(videos.values()), "images": list(images.values())}


def _key_of(c: dict) -> str:
    return c.get("creative_id") or c.get("소재명") or ""


def build_candidates(keys: list[str], title_json: dict) -> list[dict]:
    """추천 key 리스트 + 타이틀 JSON → 후보 dict 리스트(제거 대상 asset 펼침 포함).

    found=False: JSON에 해당 소재 없음(오래된 CSV 등). video_asset_ids: asset_id 확보분만.
    """
    by_key = {_key_of(c): c for c in title_json.get("creatives") or []}
    out = []
    for k in keys:
        c = by_key.get(k)
        if not c:
            out.append({"key": k, "found": False, "유형": None,
                        "videos": [], "images": [], "video_count": 0, "image_count": 0,
                        "video_asset_ids": [], "video_names": [], "missing_asset_id": 0})
            continue
        ex = expand_assets(c)
        vids = ex["videos"]
        asset_ids = [v["asset_id"] for v in vids if v.get("asset_id")]
        names = [v["name"] for v in vids if not v.get("asset_id")]  # asset_id 없으면 이름으로 resolve
        out.append({
            "key": k, "found": True, "유형": c.get("유형"),
            "videos": vids, "images": ex["images"],
            "video_count": len(vids), "image_count": len(ex["images"]),
            "video_asset_ids": asset_ids, "video_names": names,
            "missing_asset_id": len(names),
        })
    return out
