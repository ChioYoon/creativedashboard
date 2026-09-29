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
    """축 생성 허용 여부 — **fail-closed** (schema_contract 1.1 · R팀 회신 v1.3 §2).

    게이트 부재는 '제약 없음'이 아니라 '미선언'이다. 미선언 타이틀에 생성 자동화를 돌리면
    판권 사고가 나므로 차단으로 처리한다. 허용하려면 정본 brief_<title_id>.json 에
    cloop_gate 를 명시 선언할 것(제우스는 blocked_axes: [] 로 전 축 허용).
    step1 의 brandGateAllowsGeneration() 과 같은 방향이다.
    """
    if not gate:
        return False
    blocked = gate.get("blocked_axes")
    if blocked is None:      # 게이트는 있으나 축 목록 미선언 → 판단 불가 → 차단
        return False
    return axis not in blocked


def _ip_safe_lines(d: dict) -> list[str]:
    """정본의 흩어진 금기 항목을 미러 ip_safe 한 배열로 모은다(모달·AI 프롬프트가 이 배열만 읽음)."""
    ip = list(d.get("ip_safe") or [])
    cb = d.get("content_boundary") or {}
    ip += ["미출시 콘텐츠 소구 금지: %s(%s)" % (b.get("name"), b.get("opens_at", ""))
           for b in (cb.get("blocked") or [])]
    if cb.get("name_check_required"):
        ip.append("명칭 확인 필요 — " + " · ".join(cb["name_check_required"]))
    cr = d.get("copyright_required") or {}
    if cr.get("jp") or cr.get("en"):
        ip.append("카피라이트 표기 원문 — JP: %s / EN: %s" % (cr.get("jp", ""), cr.get("en", "")))
    for r in (d.get("naming_rules") or []):
        ip.append("명칭 — '%s' 사용 / '%s' 금지%s" % (
            r.get("correct", ""), "·".join(r.get("wrong") or []),
            " (%s)" % r["note"] if r.get("note") else ""))
    # forbidden_words_note 가 있으면 '단어'가 아니라 '표현 유형' 금지이며 그 내용이 이미 ip_safe 에 있다
    # (제우스). 없으면 단어 목록이므로 금칙어 줄을 따로 만든다(도원암귀).
    if d.get("forbidden_words") and not d.get("forbidden_words_note"):
        ip.append("금칙어 절대 사용 금지 — " + " · ".join(d["forbidden_words"]))
    # 차단축이 있는데 ip_safe 가 게이트를 서술하지 않은 브리프에만 가드 줄을 세운다.
    # (도원암귀는 ip_safe 1·2항이 이미 서술 → 중복 방지 / 제우스는 차단축 0 → 불요)
    gate = d.get("cloop_gate") or {}
    if gate.get("blocked_axes") and not any("modification_level" in s for s in ip):
        ip.insert(0, "🔴 CLOOP 생성 게이트: modification_level=%s · 차단축 %s (소재 생성 자동화 시 준수)"
                  % (gate.get("modification_level"), ",".join(gate["blocked_axes"])))
    return ip


def _characters_line(ch: dict) -> str:
    """슬롯[4] '등장 캐릭터' 폴백 한 줄. 배치 규칙은 characters_display 가 따로 담당한다."""
    if ch.get("classes"):
        s = " / ".join(ch["classes"])
        if ch.get("key_npc"):
            s += " · NPC " + "·".join(ch["key_npc"])
        if ch.get("player_role"):
            s += " · 역할 " + ch["player_role"]
        return s
    if ch.get("priority"):
        s = "우선순위(집단 훅 배치 순서) " + " > ".join(ch["priority"])
        if ch.get("faction_oni") or ch.get("faction_momotaro"):
            s += " (=라세츠학원 %d명)" % len(ch["priority"])
        if ch.get("faction_oni"):
            s += " · 오니 진영 " + "·".join(ch["faction_oni"])
        if ch.get("faction_momotaro"):
            s += " · 모모타로 진영 " + "·".join(ch["faction_momotaro"])
        return s
    return ""


def to_brand_brief_entry(d: dict, carry: dict | None = None, source_note: str = "자동 동기화") -> dict:
    """구조화 브리프 → js/brand_briefs.json 엔트리.

    characters_display 는 브리프가 준 렌더 문자열을 **그대로** 싣는다(Z-4 render_contract).
    로더가 타이틀별 characters 구조를 해석하지 않는다 — 해석은 폴백 한 줄(_characters_line)에만 남는다.
    carry: 정본에 없고 미러에만 있는 키(genre·core_loop·core_appeals 등 게임성격 맥락)를 이어받는다.
    """
    tone = d.get("tone") or {}
    pal = tone.get("palette") or {}
    slog = d.get("slogan") or {}
    ci = d.get("creative_inventory") or {}
    gate = get_cloop_gate(d)

    tone_s = " · ".join(tone.get("art") or [])
    palette = "/".join(v for v in (pal.get("background"), pal.get("main"), pal.get("point")) if v)
    if palette:
        tone_s += " · 컬러 " + palette
    cta = " · ".join(tone.get("keywords") or [])
    if tone.get("avoid_format"):
        cta += " · 지양: " + tone["avoid_format"]

    entry: dict = {"_source": "v%s (frozen %s, updated %s, structured brief) — brief_%s.json %s" % (
        d.get("version"), d.get("frozen_at"), d.get("updated_at"), d.get("title_id"), source_note)}
    for k in ("genre", "core_loop", "core_appeals"):
        if (carry or {}).get(k):
            entry[k] = carry[k]
    entry["characters"] = _characters_line(d.get("characters") or {})
    if d.get("characters_display"):
        cd = d["characters_display"]
        entry["characters_display"] = {"priority_line": cd.get("priority_line"),
                                       "note_lines": list(cd.get("note_lines") or [])}
    st = d.get("stage") or {}
    if st:   # 축 판정이 읽는다(launch_date 하드코딩 제거). 어휘: pre_campaign|prerelease|launched
        entry["stage"] = {k: st.get(k) for k in ("current", "launch_date", "axis_judgement")}
    entry["tone"] = tone_s
    entry["slogan"] = " = ".join(slog.get("current") or [])
    entry["cta_tone"] = cta
    if d.get("forbidden_words"):
        entry["forbidden_words"] = list(d["forbidden_words"])
    for k in ("gaps_scope", "execution_scope"):   # 운영 규칙 — 데이터만 적재, 렌더는 추후(회신 Q3 ⓒ)
        if ci.get(k):
            entry[k] = ci[k]
    if gate:
        entry["cloop_gate"] = {k: gate[k] for k in
                               ("modification_level", "allowed_axes", "blocked_axes", "rationale") if k in gate}
    entry["ip_safe"] = _ip_safe_lines(d)
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


# ── 미러 자동 동기화 (②-4) ──────────────────────────────────────────────
# 정본(G드라이브) brief_<title_id>.json → js/brand_briefs.json.
# 브라우저는 G: 를 못 읽으므로 이 미러가 대시보드의 유일한 실배선이다.
# 경로는 .env CLOOP_BRIEFS_DIR 로 받는다(하드코딩 금지 — 이관·경로 변경 시 코드 수정 불요).
# 🔴 경로 부재·로드 실패는 **경고가 아니라 실패**로 올린다(R팀 회신 Q7).
#    조용히 멈추면 미러가 며칠 낡은 채로 돌고, 그게 이 프로젝트가 실제로 겪은 사고다.

MIRROR_PATH = "js/brand_briefs.json"
GATE_REGISTRY = "gate_registry.json"   # R팀 소유. 복사만 하고 내용은 생성하지 않는다


class BriefSyncError(RuntimeError):
    """미러 동기화 실패 — 호출부는 이를 삼키지 말고 종료 코드에 반영할 것."""


def sync_mirror(briefs_dir: str | Path | None = None, mirror_path: str | Path = MIRROR_PATH) -> dict:
    """정본 디렉터리의 frozen 브리프로 미러를 갱신. {updated, skipped, registry} 반환.

    · 정본에 없는 타이틀 엔트리(gd·pepp-us 등 레거시)는 건드리지 않는다.
    · 미러에만 있는 키(genre·core_loop·core_appeals)는 carry 로 보존한다.
    · gate_registry.json 은 R팀 소유라 **복사만** 한다(brand_briefs 생성 로직과 분리).
    """
    import os
    d = str(briefs_dir or os.environ.get("CLOOP_BRIEFS_DIR", "")).strip()
    if not d:
        raise BriefSyncError("CLOOP_BRIEFS_DIR 미설정 — .env 에 브랜드 브리프 정본 경로를 지정할 것")
    src = Path(d)
    if not src.is_dir():
        raise BriefSyncError(f"브리프 정본 경로에 접근 불가: {src} (드라이브 미마운트·경로 변경 확인)")

    mp = Path(mirror_path)
    mirror = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}

    updated, skipped = [], []
    for f in sorted(src.glob("brief_*.json")):
        tid = f.stem[len("brief_"):]
        b = load_structured(f)                 # status != frozen 이면 None
        if not b:
            skipped.append(tid)
            continue
        if not b.get("ip_safe") or not b.get("cloop_gate"):   # schema_contract 1.1 fail-hard
            raise BriefSyncError(f"{f.name}: ip_safe·cloop_gate 는 필수이며 비어 있을 수 없음")
        mirror[tid] = to_brand_brief_entry(b, carry=mirror.get(tid))
        updated.append(tid)

    if not updated:
        raise BriefSyncError(f"{src} 에서 frozen 브리프를 하나도 읽지 못함")

    mp.write_text(json.dumps(mirror, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    reg_src = src / GATE_REGISTRY
    reg = False
    if reg_src.exists():
        (mp.parent / GATE_REGISTRY).write_text(reg_src.read_text(encoding="utf-8"), encoding="utf-8")
        reg = True
    return {"updated": updated, "skipped": skipped, "registry": reg}


def stage_of(title: str, mirror_path: str | Path = MIRROR_PATH,
             briefs_dir: str | Path | None = None) -> dict:
    """타이틀 → {current, launch_date, axis_judgement}. 없으면 빈 dict.

    미러(js/brand_briefs.json)를 1순위로 읽는다 — 미러는 nightly 가 정본에서 생성하므로
    내용이 같고, 드라이브가 안 잡히는 환경에서도 축 판정이 돈다.
    미러에 stage 가 없으면(구버전 미러) 정본을 직접 본다.
    """
    import os
    mp = Path(mirror_path)
    if mp.exists():
        try:
            st = (json.loads(mp.read_text(encoding="utf-8")).get(title) or {}).get("stage")
            if st:
                return st
        except Exception:
            pass
    d = str(briefs_dir or os.environ.get("CLOOP_BRIEFS_DIR", "")).strip()
    if d:
        b = load_structured(Path(d) / f"brief_{title}.json")
        if b and b.get("stage"):
            return {k: b["stage"].get(k) for k in ("current", "launch_date", "axis_judgement")}
    return {}
