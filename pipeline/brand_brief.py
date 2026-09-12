"""브랜드 브리프 frozen 게이트 (R팀 회신 v1.2 §5).

CLOOP은 `status: frozen` 브랜드 브리프만 소비해야 함(미승인 작업본이 태깅·IP세이프로 흘러가는 것 차단).
브리프 .txt 상단 YAML frontmatter를 읽어 frozen 여부·버전을 판별한다.

- 콘텐츠(slogan/tone/ip_safe) 자동 파싱은 prose라 취약 → **본 모듈은 게이트·버전만** 담당.
  실제 콘텐츠는 `js/brand_briefs.json`(구조화, freeze 시 수동 동기화)이 소스.
  R팀이 구조화 `브랜드브리프.json` export 제공 시 `load_structured()`로 자동 fetch 확장.
- 드리프트 감지: frozen 브리프 버전 ↔ brand_briefs.json `_source` 버전 불일치 시 경고.
"""
from __future__ import annotations
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


if __name__ == "__main__":
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else ""
    print(brief_status(p))
