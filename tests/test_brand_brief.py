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
