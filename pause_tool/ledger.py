"""
pause_tool 실행 원장 — apply/resume 결과를 append-only JSONL로 기록, "현재 중단됨" 상태 도출.

왜: apply 후 뭘 껐는지 어딘가 남아야 감사·일괄복원·대시보드 연동이 됨. 파일 닫아도 유지.
append-only 라 read-modify-write 경합 없음. 상태 = asset_id별 마지막 이벤트(remove=중단, resume=활성).

# ponytail: key 단위 기록 — min_keep로 일부 광고서 스킵된 asset도 '중단'으로 셈(상태 근사).
#           정밀 광고별 추적 필요해지면 이벤트에 ad_group_ad 추가.
"""
from __future__ import annotations

import json
from pathlib import Path

LEDGER = Path(__file__).resolve().parent / "pause_ledger.jsonl"


def append(event: dict, path: Path = LEDGER) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def read_events(path: Path = LEDGER) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def reduce_paused(events: list[dict], title: str | None = None) -> list[dict]:
    """이벤트(시간순) → 현재 중단 중인 소재 리스트. asset_id별 마지막 mode가 'remove'면 중단.

    반환: [{key, asset_ids[정렬], last_ts}] — key별 그룹, 중단 asset 하나라도 있으면 포함.
    """
    state: dict[str, dict] = {}  # asset_id -> {mode, key, ts}
    for e in events:
        if title and e.get("title") != title:
            continue
        for aid in e.get("asset_ids") or []:
            state[aid] = {"mode": e.get("mode"), "key": e.get("key"), "ts": e.get("ts")}
    grouped: dict[str, dict] = {}
    for aid, s in state.items():
        if s["mode"] != "remove":
            continue
        g = grouped.setdefault(s["key"], {"key": s["key"], "asset_ids": [], "last_ts": ""})
        g["asset_ids"].append(aid)
        if (s["ts"] or "") > g["last_ts"]:
            g["last_ts"] = s["ts"] or ""
    out = list(grouped.values())
    for g in out:
        g["asset_ids"].sort()
    out.sort(key=lambda g: g["last_ts"], reverse=True)
    return out
