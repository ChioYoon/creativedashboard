"""content_theme 축 매핑 — 훅→테마 결정적 룩업 (R팀 정의서 v2.0 / theme_map_v2.json).

CLOOP↔브랜드브리프 연동: content_theme(콘텐츠 테마 10축)은 core_usp(소구 유형 5)와 **병존**.
기존 훅은 theme_map 테이블을 그대로 따름(결정적·무비용·회귀0). 신규 훅=N/A:미상+검수.
⚠️ content_theme엔 Gemini 자동분류 경로가 없다 — 미매핑 훅은 항상 검수 큐(N/A:미상). 즉 R팀
   gate_binding.new_hook_policy=REVIEW_QUEUE(도원암귀)는 전 타이틀에 기본 적용된 상태다.

- 훅 추출: creative_concept `{stage}-{seg}-{Hook}[-variant]-{num}-{suffix}` 의 Hook 세그먼트.
- 정규화는 **맵별로 다름**(theme_map JSON이 규칙 소유):
  · zeus(theme_map_v2.json): 접미 LD/15s/30s + 2자리 숫자 제거.
  · 도원암귀(theme_map_tougenanki.json): 접미 없음, 1~2자리 숫자만 제거(Cutscene0 대응),
    보존 토큰(TVA/SSR/PV)은 말미 숫자가 아니라 영향 없음.
- 매핑 실패 = 신규 훅 → theme_primary 'N/A:미상' + 검수 플래그.
- 도원암귀 등 intent_axis 구조 맵: 소재명 2번째 세그먼트(제작 의도 축)를 별도 보존
  (content_theme 판정엔 미사용 — 정의서 §2-2 '보이는 것 기준'. 충돌 훅 측정용).
"""
from __future__ import annotations
import json
import re
from pathlib import Path

# 타이틀 → theme_map 파일. 미등록 타이틀은 기본(zeus) 맵.
_TITLE_MAP_FILE = {"tougenanki": "theme_map_tougenanki.json"}
_DEFAULT_MAP_FILE = "theme_map_v2.json"

_CFG_CACHE: dict[str, dict] = {}
_MAP_CACHE: dict | None = None
_ALIAS_CACHE: dict | None = None

_ZEUS_VARIATION = r"\d{2}$"


def _load_raw(fname: str, repo_root: str | Path | None = None) -> dict:
    p = (Path(repo_root) if repo_root else Path(__file__).parent) / fname
    return json.loads(p.read_text(encoding="utf-8"))


def _load_config(title: str | None, repo_root: str | Path | None = None) -> dict:
    """타이틀별 맵 설정 로드(캐시). 두 스키마(zeus `map`/`primary` · 도원암귀 `hooks`/`theme_primary`)를
    내부 단일 형태 {primary,secondary,core_usp,review,flags,partner}로 어댑트."""
    fname = _TITLE_MAP_FILE.get(title or "", _DEFAULT_MAP_FILE)
    ck = fname
    if repo_root is None and ck in _CFG_CACHE:
        return _CFG_CACHE[ck]
    raw = _load_raw(fname, repo_root)
    if "hooks" in raw:  # 도원암귀 스키마
        hooks = {
            k: {"primary": v["theme_primary"], "secondary": list(v.get("theme_secondary", [])),
                "core_usp": v.get("core_usp"), "review": v.get("review"),
                "flags": list(v.get("flags", [])), "partner": v.get("partner")}
            for k, v in raw["hooks"].items()
        }
        norm = raw.get("normalization", {}) or {}
        cfg = {
            "hooks": hooks,
            "alias": raw.get("alias", {}) or {},
            "variation": norm.get("variation_regex") or r"\d{1,2}$",
            "strip_suffix": bool(norm.get("removed_suffixes")),  # [] → False
            "intent": (raw.get("intent_axis") or {}).get("values"),
        }
    else:  # zeus 스키마 (map + primary/secondary)
        cfg = {
            "hooks": raw.get("map", {}),
            "alias": raw.get("alias", {}) or {},
            "variation": _ZEUS_VARIATION,
            "strip_suffix": True,
            "intent": None,
        }
    if repo_root is None:
        _CFG_CACHE[ck] = cfg
    return cfg


def load_map(repo_root: str | Path | None = None) -> dict:
    """(하위호환) zeus theme_map_v2.json 의 훅→테마 맵. axis_verdict/기존 테스트용."""
    global _MAP_CACHE
    if _MAP_CACHE is not None and repo_root is None:
        return _MAP_CACHE
    m = _load_raw(_DEFAULT_MAP_FILE, repo_root).get("map", {})
    if repo_root is None:
        _MAP_CACHE = m
    return m


def load_alias(repo_root: str | Path | None = None) -> dict:
    """(하위호환) zeus 오타→정규 훅 별칭."""
    global _ALIAS_CACHE
    if _ALIAS_CACHE is not None and repo_root is None:
        return _ALIAS_CACHE
    a = _load_raw(_DEFAULT_MAP_FILE, repo_root).get("alias", {})
    if repo_root is None:
        _ALIAS_CACHE = a
    return a


def _normalize(tok: str, *, variation: str = _ZEUS_VARIATION, strip_suffix: bool = True):
    """맵별 정규화. strip_suffix=True(zeus)면 LD/15s/30s도 제거, variation=말미 숫자 정규식.
    LD(Launch Date) 접미는 theme 통합하되 launch_date_variant 플래그 보존."""
    t = str(tok).strip()
    ld = False
    prev = None
    while t != prev:
        prev = t
        if strip_suffix:
            t2 = re.sub(r"LD$", "", t)
            if t2 != t:
                ld = True
            t = t2
            t = re.sub(r"(?:15s|30s)$", "", t)
        t = re.sub(variation, "", t)
        t = t.rstrip("-")
    return t, ld


def normalize_hook(tok: str, return_flags: bool = False):
    """(하위호환) zeus 규칙 정규화. 맵별 규칙은 _normalize 사용."""
    base, ld = _normalize(tok)
    return (base, ld) if return_flags else base


def _hook_candidates(concept: str) -> list[str]:
    """concept 에서 훅 후보 — 2세그 결합(zeus Dirguide-Artisan 류) 우선, 단일 세그 폴백.
    도원암귀는 결합(Hook-suffix)이 맵에 없어 자연히 단일 세그로 폴백된다."""
    segs = str(concept).split("-")
    cands: list[str] = []
    if len(segs) >= 4:
        cands.append(f"{segs[2]}-{segs[3]}")
    if len(segs) >= 3:
        cands.append(segs[2])
    return cands


def _intent_of(concept: str, intent_values) -> str | None:
    """도원암귀류: 소재명 2번째 세그먼트가 intent_axis 값이면 반환."""
    if not intent_values:
        return None
    segs = str(concept).split("-")
    return segs[1] if len(segs) >= 2 and segs[1] in intent_values else None


def assign_theme(concept: str, m: dict | None = None, *, title: str | None = None) -> dict:
    """concept → 테마 판정 dict.

    - title 지정: 해당 타이틀 맵(정규화·alias·intent 포함) 사용.
    - m 지정(하위호환): zeus hooks dict 를 맵으로, zeus 규칙 사용(axis_verdict 경로).
    - 둘 다 없음: 기본 zeus 맵.
    theme_reviewed 는 항상 False 로 시작(§6 검수 통과 전 판정 미투입).
    """
    if title is not None:
        cfg = _load_config(title)
    elif m is not None:
        cfg = {"hooks": m, "alias": load_alias(), "variation": _ZEUS_VARIATION,
               "strip_suffix": True, "intent": None}
    else:
        cfg = _load_config(None)

    hooks, alias = cfg["hooks"], cfg["alias"]
    intent = _intent_of(concept, cfg["intent"])
    for cand in _hook_candidates(concept):
        # 순서: ① alias(오타·대소문자) 최우선 → ② 정규화(+LD 플래그) → ③ alias 재적용 → 조회
        a = alias.get(cand, cand)
        base, ld = _normalize(a, variation=cfg["variation"], strip_suffix=cfg["strip_suffix"])
        key = base if base in hooks else alias.get(base)
        if key and key in hooks:
            e = hooks[key]
            return {
                "theme_primary": e["primary"],
                "theme_secondary": list(e.get("secondary", [])),
                "core_usp": e.get("core_usp"),
                "theme_reviewed": False,
                "matched_hook": key,
                "new_hook": False,
                "review_flag": "검수" if e.get("review") else "",
                "launch_date_variant": ld,
                "partner": e.get("partner"),
                "intent_axis": intent,
                "theme_flags": list(e.get("flags", [])),
            }
    return {
        "theme_primary": "N/A:미상",
        "theme_secondary": [],
        "core_usp": None,
        "theme_reviewed": False,
        "matched_hook": None,
        "new_hook": True,
        "review_flag": "검수",  # REVIEW_QUEUE: 자동분류 없이 검수 큐로
        "launch_date_variant": False,
        "partner": None,
        "intent_axis": intent,
        "theme_flags": [],
    }


if __name__ == "__main__":  # 커버리지 자체점검
    tests = {  # (concept, title): expected_primary
        ("L-Event-Market1st-02-DA", None): "N/A:고지",
        ("P-Slogan-CinematicPV30s-01-PV", None): "스토리·세계관",
        ("L-Genre-Dirguide-Artisan-UA", None): "수집·육성",
        ("P-Ingame-Region-Thebes-UA", None): "그래픽·비주얼",
        ("FGT-IP-MudanoSSR01-DA", "tougenanki"): "IP·캐릭터",
        ("P-Battle-Freindship02-DA", "tougenanki"): "스토리·세계관",  # 오타 alias
        ("P-Character-Cutscene0-DA", "tougenanki"): "스토리·세계관",   # 1자리 번호
        ("L-Story-Endcard-EC", "tougenanki"): "N/A:CTA",
    }
    ok = 0
    for (c, t), exp in tests.items():
        r = assign_theme(c, title=t) if t else assign_theme(c)
        good = r["theme_primary"] == exp
        ok += good
        assert good, f"{c}({t}): {r['theme_primary']} != {exp}"
    # intent_axis 보존 확인
    r = assign_theme("P-Reward-MudanoSSR01-DA", title="tougenanki")
    assert r["intent_axis"] == "Reward" and "ssr_grade" in r["theme_flags"], r
    print(f"self-check {ok}/{len(tests)} pass · intent_axis/flags OK")
