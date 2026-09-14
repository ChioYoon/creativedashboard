"""브랜드 브리프 frozen 게이트 (R팀 회신 v1.2 §5).

CLOOP은 `status: frozen` 브랜드 브리프만 소비해야 함(미승인 작업본이 태깅·IP세이프로 흘러가는 것 차단).
브리프 .txt 상단 YAML frontmatter를 읽어 frozen 여부·버전을 판별한다.

- 콘텐츠(slogan/tone/ip_safe) 자동 파싱은 prose라 취약 → **본 모듈은 게이트·버전만** 담당.
  실제 콘텐츠는 `js/brand_briefs.json`(구조화, freeze 시 수동 동기화)이 소스.
  R팀이 구조화 `브랜드브리프.json` export 제공 시 `load_structured()`로 자동 fetch 확장.
- 드리프트 감지: frozen 브리프 버전 ↔ brand_briefs.json `_source` 버전 불일치 시 경고.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

_FM_RE = re.compile(r"```yaml\s*\n(.*?)\n```", re.S)


def parse_frontmatter(text: str) -> dict:
    """브리프 상단 ```yaml 블록 → {key: value} (경량 파서, pyyaml 불요)."""
    m = _FM_RE.search(text or "")
    if not m:
        return {}
    fm: dict = {}
    for line in m.group(1).splitlines():
        line = line.split("#", 1)[0].rstrip()  # 인라인 주석 제거
        if ":" in line:
            k, v = line.split(":", 1)  # maxsplit=1 → 값 내 ':' 보존(제우스: 오만의 신)
            if k.strip():
                fm[k.strip()] = v.strip()
    return fm


def is_frozen(fm: dict) -> bool:
    return (fm.get("status") or "").lower() == "frozen"


def brief_status(path: str | Path) -> dict | None:
    """브리프 파일 → {title, version, status, frozen_at, frozen}. 없으면 None."""
    p = Path(path)
    if not p.exists():
        return None
    fm = parse_frontmatter(p.read_text(encoding="utf-8"))
    return {
        "title": fm.get("title"),
        "version": fm.get("version"),
        "status": fm.get("status"),
        "frozen_at": fm.get("frozen_at"),
        "frozen": is_frozen(fm),
    }


def should_fetch(path: str | Path) -> bool:
    """CLOOP fetch 게이트 — frozen 인 브리프만 True."""
    st = brief_status(path)
    return bool(st and st["frozen"])


def drift_warning(path: str | Path, brand_briefs_source: str | None) -> str | None:
    """frozen 브리프 버전이 brand_briefs.json `_source`에 안 담겼으면 경고 문자열, 아니면 None."""
    st = brief_status(path)
    if not st or not st["frozen"]:
        return None
    ver = st.get("version") or ""
    if ver and ver not in (brand_briefs_source or ""):
        return f"[brand_brief 드리프트] frozen {ver} — brand_briefs.json _source='{brand_briefs_source}' 미반영. 수동 동기화 필요"
    return None


def load_structured(json_path: str | Path) -> dict | None:
    """구조화 브랜드브리프 JSON(회신 v1.5 §3, brief_{title}.json) 로드 — frozen 만 반환.

    prose .txt frontmatter 게이트보다 우선(1순위). 파일/frozen 아니면 None → txt 폴백.
    """
    p = Path(json_path)
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return d if (d.get("status") or "").lower() == "frozen" else None


def get_cloop_gate(d: dict) -> dict | None:
    """구조화 브리프의 CLOOP 생성 게이트(modification_level·allowed/blocked_axes). 없으면 None.
    ⚠️ 소재 생성 자동화(Higgsfield)는 이 게이트를 반드시 준수 — blocked_axes(축4 에셋조합·축5 신규생성·
    TrackB 신규훅)는 원본유지only IP(도원암귀 등)에서 판권 사고·트레이싱 리스크."""
    return d.get("cloop_gate")


def generation_allowed(gate: dict | None, axis: str) -> bool:
    """gate.blocked_axes 에 걸리면 False. gate 없으면(제약 없는 IP) True."""
    if not gate:
        return True
    return axis not in (gate.get("blocked_axes") or [])


def to_brand_brief_entry(d: dict) -> dict:
    """구조화 브리프 → js/brand_briefs.json 엔트리. zeus/tougenanki 등 다른 스키마 형태에 견고."""
    tone = d.get("tone", {}) or {}
    pal = tone.get("palette", {}) or {}
    ch = d.get("characters", {}) or {}
    slog = d.get("slogan", {}) or {}
    ip = list(d.get("ip_safe", []) or [])
    for b in (d.get("content_boundary", {}) or {}).get("blocked", []) or []:
        ip.append("미출시 콘텐츠 소구 금지: %s(%s)" % (b.get("name"), b.get("opens_at", "")))
    for w in (d.get("forbidden_words") or []):
        pass  # 금지어는 별도 필드로 보존(아래), ip_safe 비대화 방지
    gate = get_cloop_gate(d)
    if gate:
        ip.insert(0, "🔴 CLOOP 생성 게이트: modification_level=%s · 차단축 %s (소재 생성 자동화 시 준수)"
                  % (gate.get("modification_level"), ",".join(gate.get("blocked_axes") or [])))
    # 캐릭터: classes(제우스) 또는 priority(도원암귀)
    if ch.get("classes"):
        chars = " / ".join(ch["classes"])
        if ch.get("key_npc"):
            chars += " · NPC " + "·".join(ch["key_npc"])
        if ch.get("player_role"):
            chars += " · 역할 " + ch["player_role"]
    else:
        chars = " / ".join(ch.get("priority", [])[:8])
    palette = "/".join(v for v in (pal.get("background"), pal.get("main"), pal.get("point")) if v)
    tone_s = " · ".join(tone.get("art", []))
    if palette:
        tone_s += " · 컬러 " + palette
    cta = " · ".join(tone.get("keywords", []))
    if tone.get("avoid_format"):
        cta += " · 지양: " + tone["avoid_format"]
    entry = {
        "_source": "%s (frozen %s, structured brief)" % (d.get("version"), d.get("frozen_at")),
        "characters": chars,
        "tone": tone_s,
        "slogan": " = ".join(slog.get("current", [])) if slog else "",
        "cta_tone": cta,
        "ip_safe": ip,
    }
    if d.get("forbidden_words"):
        entry["forbidden_words"] = list(d["forbidden_words"])
    if gate:
        entry["cloop_gate"] = gate
    return entry


def get_brief_entry(title, json_path=None, txt_path=None):
    """구조화 JSON 1순위 → txt frontmatter 폴백(게이트만). 둘 다 없으면 None."""
    d = load_structured(json_path) if json_path else None
    if d:
        return to_brand_brief_entry(d)
    if txt_path and should_fetch(txt_path):
        return None  # frozen 확인되나 콘텐츠 파싱 미지원 → 기존 brand_briefs.json 유지 신호
    return None


if __name__ == "__main__":
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else ""
    print(brief_status(p))
