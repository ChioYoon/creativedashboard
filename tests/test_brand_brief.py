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
