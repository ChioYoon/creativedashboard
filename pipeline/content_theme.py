"""content_theme 축 매핑 — 훅→테마 결정적 룩업 (R팀 정의서 v2.0 / theme_map_v2.json).

CLOOP↔브랜드브리프 연동: content_theme(콘텐츠 테마 10축)은 core_usp(소구 유형 5)와 **병존**.
기존 훅은 theme_map_v2.json 테이블을 그대로 따름(결정적·무비용·회귀0). 신규 훅만 Gemini 분류 대상.

- 훅 추출: creative_concept `{P|L}-{Category}-{Hook}[-variant]-{num}-{suffix}` 의 Hook 세그먼트.
- 정규화(정의서 §2-4): 접미 `LD` / 2자리 숫자 / `15s`·`30s` 제거 후 매핑.
- 매핑 실패 = 신규 훅 → theme_primary 'N/A:미상' + 검수 플래그(Gemini/사람 분류 대상).
"""
from __future__ import annotations
import json
import re
from pathlib import Path

_MAP_CACHE: dict | None = None
_ALIAS_CACHE: dict | None = None


def _load_raw(repo_root: str | Path | None = None) -> dict:
    p = (Path(repo_root) if repo_root else Path(__file__).parent) / "theme_map_v2.json"
    return json.loads(p.read_text(encoding="utf-8"))


def load_map(repo_root: str | Path | None = None) -> dict:
    """theme_map_v2.json 의 훅→테마 맵 로드(캐시)."""
    global _MAP_CACHE
    if _MAP_CACHE is not None and repo_root is None:
        return _MAP_CACHE
    m = _load_raw(repo_root).get("map", {})
    if repo_root is None:
        _MAP_CACHE = m
    return m


def load_alias(repo_root: str | Path | None = None) -> dict:
    """오타→정규 훅 별칭(theme_map v2.1 §alias). 정규화 직후·맵조회 직전 적용."""
    global _ALIAS_CACHE
    if _ALIAS_CACHE is not None and repo_root is None:
        return _ALIAS_CACHE
    a = _load_raw(repo_root).get("alias", {})
    if repo_root is None:
        _ALIAS_CACHE = a
    return a


def normalize_hook(tok: str, return_flags: bool = False):
    """정규화(v2.1 순서): LD(Launch Date)·길이(15s/30s)·2자리번호 접미 제거. 반복 적용.
    LD 접미는 '기존 소재 + 론칭일 부가' → theme 통합하되 launch_date_variant 플래그 보존(패치 correction)."""
    t = str(tok).strip()
    ld = False
    prev = None
    while t != prev:
        prev = t
        t2 = re.sub(r"LD$", "", t)
        if t2 != t:
            ld = True
        t = t2
        t = re.sub(r"(?:15s|30s)$", "", t)
        t = re.sub(r"\d{2}$", "", t)
        t = t.rstrip("-")
    return (t, ld) if return_flags else t


def _hook_candidates(concept: str) -> list[str]:
    """concept 에서 훅 후보 추출 — 2세그 결합(Dirguide-Artisan 류) 우선, 단일 세그 폴백."""
    segs = str(concept).split("-")
    cands: list[str] = []
    if len(segs) >= 4:
        cands.append(f"{segs[2]}-{segs[3]}")  # 복합 훅
    if len(segs) >= 3:
        cands.append(segs[2])                 # 단일 훅
    return cands


def assign_theme(concept: str, m: dict | None = None) -> dict:
    """concept → {theme_primary, theme_secondary[], core_usp, theme_reviewed, matched_hook, new_hook, review_flag}.

    매핑되면 테이블 값(결정적). 미매핑이면 신규 훅으로 N/A:미상 + 검수.
    theme_reviewed 는 항상 False 로 시작(§6 검수 절차 통과 전 판정 미투입).
    """
    m = m if m is not None else load_map()
    alias = load_alias()
    for cand in _hook_candidates(concept):
        # v2.1 순서: ① alias(오타→정규) 최우선 → ② LD/길이/번호 접미 제거(+LD 플래그) → ③ 조회
        a = alias.get(cand, cand)
        base, ld = normalize_hook(a, return_flags=True)
        key = base if base in m else alias.get(base)
        if key and key in m:
            e = m[key]
            return {
                "theme_primary": e["primary"],
                "theme_secondary": list(e.get("secondary", [])),
                "core_usp": e.get("core_usp"),
                "theme_reviewed": False,
                "matched_hook": key,
                "new_hook": False,
                "review_flag": e.get("review", ""),
                "launch_date_variant": ld,
                "partner": e.get("partner"),
            }
    return {
        "theme_primary": "N/A:미상",
        "theme_secondary": [],
        "core_usp": None,
        "theme_reviewed": False,
        "matched_hook": None,
        "new_hook": True,
        "review_flag": "검수",
        "launch_date_variant": False,
        "partner": None,
    }


if __name__ == "__main__":  # 커버리지 자체점검
    m = load_map()
    tests = {
        "L-Event-Market1st-02-DA": "N/A:고지",
        "P-Slogan-CinematicPV30s-01-PV": "스토리·세계관",
        "L-Genre-Dirguide-Artisan-UA": "수집·육성",
        "P-Ingame-Region-Thebes-UA": "그래픽·비주얼",
        "L-Ingame-ClassArtisan-01-SS": "수집·육성",
        "P-Event-CharacterName01-DA": "N/A:CTA",
        "P-Genre-AImodePV-UA": "편의성(자동·방치)",
    }
    ok = 0
    for c, exp in tests.items():
        r = assign_theme(c, m)
        good = r["theme_primary"] == exp
        ok += good
        assert good, f"{c}: {r['theme_primary']} != {exp}"
    print(f"self-check {ok}/{len(tests)} pass")
