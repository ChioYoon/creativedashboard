#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
캐시버스터 자동 갱신 (bump_cache_busters.py)
Com2uS R팀 소재 분석 대시보드

목적
----
공용 정적 자산(js/*.js, css/*.css, assets/**/*.css)을 수정하면, 이를 로드하는
모든 HTML의 `?v=...` 쿼리를 **파일 내용 해시**로 자동 맞춰준다.
→ 수동으로 버전을 올리는 것을 잊어 구버전이 캐시되는 사고를 원천 차단한다.

동작
----
- 저장소 루트의 모든 *.html 을 스캔한다(.git/.venv/node_modules 제외).
- `src="<로컬경로>.js"` / `href="<로컬경로>.css"` 참조를 찾는다(`?v=` 유무 무관).
- 참조 파일이 실제로 존재하면 sha1(파일내용)[:8] 을 계산해 `?v=<해시>` 를 부여한다.
  · 이미 `?v=` 가 있으면 해시로 교체, 없으면 새로 추가.
  · 같은 파일은 어느 HTML에서 참조하든 동일 해시 → 자동으로 일관 유지.
- 외부 URL(http(s)://, //) 과 `?v=` 이외의 쿼리스트링은 건드리지 않는다.
- 파일이 없으면 건드리지 않고 경고만 출력한다.

사용법
------
  python tools/bump_cache_busters.py          # 실제 갱신 (변경분 기록)
  python tools/bump_cache_busters.py --check   # 갱신 필요 여부만 검사 (변경 시 exit 1)

pre-commit 훅(.githooks/pre-commit)이 커밋 시 자동 실행하므로 평소 직접 실행할
필요는 없다. 훅 활성화는 저장소당 1회:  git config core.hooksPath .githooks
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

# 저장소 루트 = 이 스크립트의 상위 디렉터리(tools/의 부모)
ROOT = Path(__file__).resolve().parent.parent

# src="js/foo.js" / href="assets/x.css"  (로컬 상대경로만; http(s):// 제외)
# ?v=... 는 있으면 캡처, 없으면 새로 부여. 다른 쿼리스트링(?foo=)은 매칭 안 됨(경로가 ? 에서 끊김).
_REF = re.compile(
    r'(?P<attr>\b(?:src|href))="'
    r'(?P<path>(?!https?://|//)[^"?]+\.(?:js|css))'
    r'(?:\?v=(?P<ver>[^"]*))?"'
)

_EXCLUDE_DIRS = {".git", ".venv", "node_modules", "__pycache__", "archive"}


def _short_hash(file_path: Path) -> str:
    # 줄끝(CRLF/CR)을 LF로 정규화한 뒤 해시한다.
    # → core.autocrlf 설정·OS·체크아웃 상태와 무관하게 항상 같은 해시(결정성 보장).
    raw = file_path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha1(raw).hexdigest()[:8]


def _iter_html_files():
    for p in ROOT.rglob("*.html"):
        if any(part in _EXCLUDE_DIRS for part in p.relative_to(ROOT).parts):
            continue
        yield p


def process(check_only: bool = False):
    hash_cache: dict[str, str] = {}
    missing: set[str] = set()
    changed_files: list[tuple[str, int]] = []

    for html in _iter_html_files():
        text = html.read_text(encoding="utf-8")
        n_local = 0

        def repl(m: re.Match) -> str:
            nonlocal n_local
            rel = m.group("path")
            target = (ROOT / rel).resolve()
            # 저장소 밖 경로 방지
            try:
                target.relative_to(ROOT)
            except ValueError:
                return m.group(0)
            if not target.is_file():
                missing.add(rel)
                return m.group(0)
            if rel not in hash_cache:
                hash_cache[rel] = _short_hash(target)
            new_ver = hash_cache[rel]
            if new_ver == m.group("ver"):
                return m.group(0)
            n_local += 1
            return f'{m.group("attr")}="{rel}?v={new_ver}"'

        new_text = _REF.sub(repl, text)
        if n_local:
            changed_files.append((str(html.relative_to(ROOT)).replace("\\", "/"), n_local))
            if not check_only:
                html.write_text(new_text, encoding="utf-8", newline="\n")

    for rel in sorted(missing):
        print(f"  [warn] 참조 파일 없음 — 건너뜀: {rel}")

    if changed_files:
        verb = "갱신 필요" if check_only else "갱신됨"
        total = sum(n for _, n in changed_files)
        print(f"캐시버스터 {verb}: {len(changed_files)}개 HTML, {total}개 참조")
        for name, n in changed_files:
            print(f"  {name}  ({n})")
    else:
        print("캐시버스터 최신 상태 — 변경 없음")

    return changed_files


def main(argv):
    args = argv[1:]
    check_only = "--check" in args
    print_changed = "--print-changed" in args

    if print_changed:
        # 실제 갱신하되, 표준출력에는 변경된 HTML 경로만(LF 구분) 낸다.
        # pre-commit 훅이 이 목록만 정확히 스테이징하는 용도.
        # Windows에서도 CRLF 가 섞이지 않도록 buffer 로 LF 만 직접 쓴다.
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            changed = process(check_only=False)
        out = "".join(name + "\n" for name, _ in changed)
        sys.stdout.buffer.write(out.encode("utf-8"))
        sys.stdout.buffer.flush()
        return 0

    changed = process(check_only=check_only)
    if check_only and changed:
        # pre-commit 등에서 '갱신 필요'를 실패로 신호
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
