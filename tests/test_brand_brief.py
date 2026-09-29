"""브랜드 브리프 frozen 게이트 — frontmatter 파싱·frozen 판별·드리프트."""
from pipeline.brand_brief import parse_frontmatter, is_frozen, brief_status, should_fetch, drift_warning

FROZEN = """# [제우스] 브랜드 브리프 v1.1

```yaml
title:       제우스: 오만의 신
version:     v1.1
status:      frozen          # CLOOP fetch 게이트
frozen_at:   2026-09-12
```

## 본문
슬로건 등...
"""

DRAFT = FROZEN.replace("status:      frozen          # CLOOP fetch 게이트", "status:      draft")


def test_frontmatter_preserves_colon_value():
    fm = parse_frontmatter(FROZEN)
    assert fm["title"] == "제우스: 오만의 신"   # 값 내 ':' 보존
    assert fm["version"] == "v1.1"
    assert fm["status"] == "frozen"             # 인라인 주석 제거


def test_frozen_gate(tmp_path):
    fp = tmp_path / "brief.txt"; fp.write_text(FROZEN, encoding="utf-8")
    st = brief_status(fp)
    assert st["frozen"] is True and st["version"] == "v1.1"
    assert should_fetch(fp) is True


def test_draft_not_fetched(tmp_path):
    fp = tmp_path / "brief.txt"; fp.write_text(DRAFT, encoding="utf-8")
    assert is_frozen(parse_frontmatter(DRAFT)) is False
    assert should_fetch(fp) is False


def test_drift_warning(tmp_path):
    fp = tmp_path / "brief.txt"; fp.write_text(FROZEN, encoding="utf-8")
    # 동기화됨(_source에 v1.1 포함) → 경고 없음
    assert drift_warning(fp, "브리프 v1.1 (frozen)") is None
    # 미반영 → 경고
    assert drift_warning(fp, "브리프 v1.0") is not None


def test_missing_file():
    assert brief_status("no/such/brief.txt") is None
    assert should_fetch("no/such/brief.txt") is False


_STRUCT = {
    "status": "frozen", "version": "v1.1", "frozen_at": "2026-09-12",
    "slogan": {"current": ["A", "B"], "deprecated": ["old"]},
    "tone": {"keywords": ["웅장"], "art": ["UE5", "포토리얼"],
             "palette": {"background": "백색", "main": "황금색", "point": "청록색"},
             "avoid_format": "린나류"},
    "characters": {"classes": ["나이트", "아티산"], "key_npc": ["판도라"], "player_role": "아르콘"},
    "ip_safe": ["연령 19세"],
    "content_boundary": {"blocked": [{"name": "아카디아 제전", "opens_at": "2026-10-28"}]},
}


def test_load_structured_frozen_gate(tmp_path):
    import json
    fp = tmp_path / "brief.json"; fp.write_text(json.dumps(_STRUCT, ensure_ascii=False), encoding="utf-8")
    from pipeline.brand_brief import load_structured
    assert load_structured(fp)["version"] == "v1.1"
    # draft → None
    draft = dict(_STRUCT, status="draft")
    fp.write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
    assert load_structured(fp) is None


def test_to_brand_brief_entry():
    from pipeline.brand_brief import to_brand_brief_entry
    e = to_brand_brief_entry(_STRUCT)
    assert e["slogan"] == "A = B"
    assert "나이트" in e["characters"] and "판도라" in e["characters"]
    assert "백색/황금색/청록색" in e["tone"]
    assert "린나류" in e["cta_tone"]
    # content_boundary.blocked → ip_safe 가드로 편입
    assert any("아카디아 제전" in s for s in e["ip_safe"])


_STRUCT_GATED = {  # 도원암귀 형태(원본유지only IP)
    "status": "frozen", "version": "v1.1", "frozen_at": "2026-09-11",
    "tone": {"keywords": ["다크"], "art": ["애니풍 3D"], "avoid_format": "명령형"},
    "characters": {"priority": ["시키", "나이토", "진"]},
    "ip_safe": ["카피라이트 표기"],
    "forbidden_words": ["原作", "推し"],
    "cloop_gate": {"modification_level": "원본유지only",
                   "allowed_axes": ["축1_카피"], "blocked_axes": ["축4_에셋조합", "축5_신규생성", "TrackB_신규훅"]},
}


def test_cloop_gate_and_generation_allowed():
    from pipeline.brand_brief import get_cloop_gate, generation_allowed
    g = get_cloop_gate(_STRUCT_GATED)
    assert g["modification_level"] == "원본유지only"
    assert generation_allowed(g, "축5_신규생성") is False   # 차단
    assert generation_allowed(g, "축1_카피") is True         # 허용
    # fail-closed — 게이트 부재·축 목록 미선언은 '제약 없음'이 아니라 '미선언' → 차단
    assert generation_allowed(None, "축5_신규생성") is False
    assert generation_allowed({}, "축1_카피") is False
    assert generation_allowed({"modification_level": "제약없음"}, "축1_카피") is False  # blocked_axes 미선언
    # 전 축 허용은 blocked_axes: [] 로 명시 선언해야 한다(제우스)
    assert generation_allowed({"modification_level": "제약없음", "blocked_axes": []}, "축5_신규생성") is True


def test_entry_gated_title():
    from pipeline.brand_brief import to_brand_brief_entry
    e = to_brand_brief_entry(_STRUCT_GATED)
    assert "시키" in e["characters"]              # priority 형태 캐릭터
    assert e["slogan"] == ""                       # 슬로건 없는 브리프
    assert e["forbidden_words"] == ["原作", "推し"]
    assert e["cloop_gate"]["blocked_axes"]         # 게이트 보존
    assert any("생성 게이트" in s for s in e["ip_safe"])  # ip_safe 최상단 가드


# ── ②-4 미러 자동 동기화 ──────────────────────────────────────────────

def _brief(tid, **over):
    d = {"schema_version": "1.1", "title_id": tid, "version": "2.0", "status": "frozen",
         "frozen_at": "2026-09-01", "updated_at": "2026-09-30",
         "tone": {"art": ["A"], "keywords": ["K"], "avoid_format": "X"},
         "slogan": {"current": ["S"]},
         "characters": {"priority": ["가", "나"]},
         "characters_display": {"priority_line": "배치 — 가 > 나", "note_lines": ["주의"]},
         "ip_safe": ["금기1"],
         "cloop_gate": {"modification_level": "원본유지only", "allowed_axes": ["축1_카피"],
                        "blocked_axes": ["축5_신규생성"], "rationale": "R"}}
    d.update(over)
    return d


def _setup(tmp_path, *briefs, registry=True):
    import json
    src = tmp_path / "briefs"; src.mkdir(parents=True, exist_ok=True)
    for b in briefs:
        (src / f"brief_{b['title_id']}.json").write_text(json.dumps(b, ensure_ascii=False), encoding="utf-8")
    if registry:
        (src / "gate_registry.json").write_text('{"legacy":[]}', encoding="utf-8")
    return src


def test_sync_mirror_writes_entry_and_registry(tmp_path):
    import json
    from pipeline.brand_brief import sync_mirror
    src = _setup(tmp_path, _brief("alpha"))
    mp = tmp_path / "brand_briefs.json"
    r = sync_mirror(src, mp)
    assert r == {"updated": ["alpha"], "skipped": [], "registry": True}
    e = json.loads(mp.read_text(encoding="utf-8"))["alpha"]
    # characters_display 는 브리프가 준 렌더 문자열을 그대로(Z-4 render_contract)
    assert e["characters_display"]["priority_line"] == "배치 — 가 > 나"
    assert e["cloop_gate"]["blocked_axes"] == ["축5_신규생성"]
    assert "2.0" in e["_source"] and "자동 동기화" in e["_source"]
    assert (tmp_path / "gate_registry.json").exists()      # R팀 소유 파일은 복사만


def test_sync_mirror_preserves_legacy_and_carry(tmp_path):
    """정본에 없는 레거시 엔트리는 보존하고, 미러에만 있는 게임성격 맥락 키는 이어받는다."""
    import json
    from pipeline.brand_brief import sync_mirror
    src = _setup(tmp_path, _brief("alpha"))
    mp = tmp_path / "brand_briefs.json"
    mp.write_text(json.dumps({"legacy_title": {"ip_safe": ["보존"]},
                              "alpha": {"genre": "RPG", "core_loop": "L"}}, ensure_ascii=False), encoding="utf-8")
    sync_mirror(src, mp)
    m = json.loads(mp.read_text(encoding="utf-8"))
    assert m["legacy_title"] == {"ip_safe": ["보존"]}
    assert m["alpha"]["genre"] == "RPG" and m["alpha"]["core_loop"] == "L"


def test_sync_mirror_fails_closed(tmp_path, monkeypatch):
    """🔴 경로 부재·정본 결손은 경고가 아니라 실패(회신 Q7)."""
    import pytest
    from pipeline.brand_brief import sync_mirror, BriefSyncError
    monkeypatch.delenv("CLOOP_BRIEFS_DIR", raising=False)
    with pytest.raises(BriefSyncError):           # 미설정
        sync_mirror(None, tmp_path / "m.json")
    with pytest.raises(BriefSyncError):           # 접근 불가
        sync_mirror(tmp_path / "없는경로", tmp_path / "m.json")
    with pytest.raises(BriefSyncError):           # frozen 브리프 0건
        sync_mirror(_setup(tmp_path, _brief("d", status="draft")), tmp_path / "m.json")
    # fail-hard 필수키 결손
    src2 = _setup(tmp_path / "x", _brief("alpha", ip_safe=[]))
    with pytest.raises(BriefSyncError):
        sync_mirror(src2, tmp_path / "m2.json")


def test_sync_mirror_draft_skipped_not_written(tmp_path):
    """draft 는 스킵하되 frozen 이 하나라도 있으면 성공."""
    import json
    from pipeline.brand_brief import sync_mirror
    src = _setup(tmp_path, _brief("alpha"), _brief("beta", status="draft"))
    mp = tmp_path / "brand_briefs.json"
    r = sync_mirror(src, mp)
    assert r["updated"] == ["alpha"] and r["skipped"] == ["beta"]
    assert "beta" not in json.loads(mp.read_text(encoding="utf-8"))
