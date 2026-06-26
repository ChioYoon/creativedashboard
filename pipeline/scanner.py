"""
로컬 GDrive sync 폴더 스캐너.

- Pepp Heroes 구조: {루트}/01. BNR/선론칭/{소재명}/[파일들]
                   {루트}/02. VID/선론칭/{소재명}/[하위 폴더]/[파일들]
- 파일명 규칙: [YYMMDD]_[BNR|VID]_[소재명]_[L|S|V]_[해상도]_[언어].[확장자]
  예) 260123_BNR_A-AI-Cinematic01A-DA_L_1200x628_EN.jpg

핵심 책임:
1. 차수(사전예약/상시/선론칭) + 유형(BNR/VID) 기준으로 소재 폴더 발견
2. 각 폴더 내 미디어 파일 모두 수집
3. 폴더당 1개의 "대표 파일" 선정 (Gemini 호출 비용 절감)
4. 파일명 정규식으로 메타 추출 → CSV 컬럼과 동일한 구조로 반환
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

# 분석 대상 미디어 확장자
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".webm", ".m4v"}
MEDIA_EXTS = IMAGE_EXTS | VIDEO_EXTS

# 파일명 정규식 — 펩 히어로즈 컨벤션
# 예: 260123_BNR_A-AI-Cinematic01A-DA_L_1200x628_EN.jpg
#     260612_VID_L-Mob-Adventure01A-UA_V_1080x1920_EN.mp4
FILENAME_PATTERN = re.compile(
    r"^(?P<date>\d{6})"
    r"_(?P<type>BNR|VID|TXT)"
    r"_(?P<creative_name>.+?)"                   # 소재명 (언더스코어 포함 가능 — 우측 앵커로 구분)
    r"_(?P<size_code>[LSV])"
    r"_(?P<resolution>\d+x\d+)"
    r"_(?P<lang>[A-Z]{2,4})"                      # 2~4자 언어/지역 코드 (KR/EN/CNT 등)
    r"(?:_[A-Za-z0-9\-]+)*"                       # 선택적 추가 세그먼트 (예: 갓앤데몬 _NONE)
    r"(?:\s*\(\d+\))?"                            # 중복 다운로드 접미 ' (1)'
    r"\.(?P<ext>[a-z0-9]+)$",
    re.IGNORECASE,
)

# 사이즈 코드 → 사람이 읽기 좋은 이름
SIZE_CODE_LABEL = {
    "L": "가로형(Landscape)",
    "S": "정방형(Square)",
    "V": "세로형(Vertical)",
}


@dataclass
class CreativeCandidate:
    """1개 소재 폴더 = 1개 분석 대상."""

    creative_name: str  # 폴더명 (= CSV의 소재명)
    creative_type: str  # BNR | VID
    phase: str  # 사전예약 | 상시 | 선론칭
    folder_path: Path
    all_files: list[Path] = field(default_factory=list)
    representative_file: Optional[Path] = None  # Gemini에 보낼 대표 파일
    parsed_meta: dict = field(default_factory=dict)  # 파일명 정규식 파싱 결과


def parse_filename(filename: str) -> Optional[dict]:
    """파일명을 정규식으로 파싱. 매칭 실패 시 None.

    >>> parse_filename("260123_BNR_A-AI-Cinematic01A-DA_L_1200x628_EN.jpg")
    {'date': '260123', 'type': 'BNR', 'creative_name': 'A-AI-Cinematic01A-DA', ...}
    """
    m = FILENAME_PATTERN.match(filename)
    if not m:
        return None
    d = m.groupdict()
    # YYMMDD → YYYY-MM-DD (20YY 가정)
    raw_date = d["date"]
    iso_date = f"20{raw_date[:2]}-{raw_date[2:4]}-{raw_date[4:6]}"
    d["iso_date"] = iso_date
    return d


def _pick_representative(files: list[Path]) -> Optional[Path]:
    """폴더 내 여러 사이즈 variant 중 1개를 대표로 선정.

    우선순위:
      1) Landscape(L) 사이즈 (가장 정보량 많음 — 게임플레이/캐릭터 전체 노출)
      2) Square(S)
      3) Vertical(V)
      4) 정규식 매칭 안 되면 첫 번째 파일
    """
    if not files:
        return None

    # 정규식 파싱 가능한 파일만
    parsed = [(f, parse_filename(f.name)) for f in files]
    parsed = [(f, m) for f, m in parsed if m is not None]

    if not parsed:
        return files[0]  # fallback

    # L → S → V 순서로 우선
    for target_code in ("L", "S", "V"):
        for f, meta in parsed:
            if meta["size_code"].upper() == target_code:
                return f

    return parsed[0][0]


def _collect_media_files(folder: Path) -> list[Path]:
    """폴더와 하위 폴더 전부 재귀 스캔해서 미디어 파일만 모음."""
    return sorted(
        p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in MEDIA_EXTS
    )


def scan_creative_folders(
    root: Path,
    phases: Iterable[str] = ("선론칭",),
    types: Iterable[str] = ("BNR", "VID"),
) -> list[CreativeCandidate]:
    """루트 폴더 스캔 → 분석 대상 소재 폴더 리스트 반환.

    예) scan_creative_folders(
            Path("G:/공유 드라이브/[펩 히어로즈] R마케팅실/01. UA/01. UA 소재"),
            phases=["선론칭"],
            types=["BNR", "VID"],
        )
    """
    if not root.exists():
        raise FileNotFoundError(f"소재 루트 폴더가 없습니다: {root}")

    # 타입 → 디렉토리명 매핑 (펩 히어로즈 컨벤션)
    type_dirs = {
        "BNR": "01. BNR",
        "VID": "02. VID",
        "AI_CREATIVE": "03. AI 활용 소재",
    }

    candidates: list[CreativeCandidate] = []
    for ctype in types:
        type_dir = root / type_dirs.get(ctype.upper(), ctype)
        if not type_dir.exists():
            print(f"  [스캔 경고] {type_dir} 가 없어 건너뜁니다.")
            continue

        for phase in phases:
            phase_dir = type_dir / phase
            if not phase_dir.exists():
                print(f"  [스캔 경고] {phase_dir} 가 없어 건너뜁니다.")
                continue

            # 차수 폴더 직속 자식 = 소재 폴더 (또는 단일 파일)
            for entry in sorted(phase_dir.iterdir()):
                if not entry.is_dir():
                    continue
                files = _collect_media_files(entry)
                if not files:
                    print(f"  [스캔 알림] {entry.name}: 미디어 파일이 없어 건너뜁니다.")
                    continue
                rep = _pick_representative(files)
                meta = parse_filename(rep.name) if rep else {}
                candidates.append(
                    CreativeCandidate(
                        creative_name=entry.name,
                        creative_type=ctype.upper(),
                        phase=phase,
                        folder_path=entry,
                        all_files=files,
                        representative_file=rep,
                        parsed_meta=meta or {},
                    )
                )

    return candidates


def scan_by_filename(
    root,
    types: Iterable[str] = ("BNR", "VID"),
    exclude_dir_keywords: Iterable[str] = ("미사용",),
) -> list[CreativeCandidate]:
    """파일명 규칙 기반 스캔 — 폴더 중첩 구조에 무관 (펩과 다른 레이아웃 지원).

    루트 하위를 재귀 스캔하여 FILENAME_PATTERN 매칭 파일만 수집하고, 파싱된
    creative_name 으로 그룹핑한다. 차수/유형 폴더 순서가 다르거나 언어 하위폴더가
    끼어 있어도(예: 도원암귀 `차수/유형/소재명/언어/파일`) 동작한다.

    root 는 단일 경로(str|Path) 또는 경로 리스트 — 여러 폴더(예: 갓앤데몬 배너/비디오
    분리 폴더)를 하나로 합쳐 스캔한다. 같은 creative_name 이 여러 root 에 흩어져 있어도
    그룹핑 단계에서 파일이 병합된다(유실 없음).
    - type 은 파일명에서 추출 (폴더명 무관).
    - phase(차수)는 루트 직속 폴더명에서 추론 (메타 용도).
    - 파일명 규칙 미매칭 파일(템플릿·작업본 등)은 자동 제외.
    - exclude_dir_keywords: 경로(폴더명)에 이 키워드가 포함되면 스킵
      (예: "카툰 소재(미사용)" → '미사용' 매칭으로 제외).
    """
    roots = [Path(root)] if isinstance(root, (str, Path)) else [Path(r) for r in root]
    for r in roots:
        if not r.exists():
            raise FileNotFoundError(f"소재 루트 폴더가 없습니다: {r}")

    types_up = {t.upper() for t in types}
    exclude_kw = tuple(exclude_dir_keywords or ())
    groups: dict[str, list[Path]] = {}
    meta_by_name: dict[str, dict] = {}
    for r in roots:
        for p in sorted(r.rglob("*")):
            if not (p.is_file() and p.suffix.lower() in MEDIA_EXTS):
                continue
            if any(kw in part for part in p.parts for kw in exclude_kw):
                continue  # '미사용' 등 제외 키워드 포함 폴더 스킵
            meta = parse_filename(p.name)
            if not meta or meta["type"].upper() not in types_up:
                continue
            cname = meta["creative_name"]
            groups.setdefault(cname, []).append(p)
            meta_by_name.setdefault(cname, meta)

    candidates: list[CreativeCandidate] = []
    for cname in sorted(groups):
        files = sorted(groups[cname])
        ctype = meta_by_name[cname]["type"].upper()
        rep = _pick_representative(files)
        # folder_path = 소재명과 동일한 조상 폴더 (없으면 대표 파일의 부모)
        folder_path = rep.parent
        for anc in rep.parents:
            if anc.name == cname:
                folder_path = anc
                break
        # 차수 = rep 가 속한 root 기준 첫 경로 세그먼트 (메타 용도)
        base = next((r for r in roots if rep.is_relative_to(r)), roots[0])
        try:
            phase = rep.relative_to(base).parts[0]
        except (ValueError, IndexError):
            phase = ""
        candidates.append(
            CreativeCandidate(
                creative_name=cname,
                creative_type=ctype,
                phase=phase,
                folder_path=folder_path,
                all_files=files,
                representative_file=rep,
                parsed_meta=parse_filename(rep.name) or {},
            )
        )
    return candidates


def summarize(candidates: list[CreativeCandidate]) -> str:
    """스캔 결과 요약 문자열."""
    if not candidates:
        return "(스캔 결과 0건)"
    by_type: dict[str, int] = {}
    total_files = 0
    for c in candidates:
        by_type[c.creative_type] = by_type.get(c.creative_type, 0) + 1
        total_files += len(c.all_files)
    parts = [f"{t}={n}개" for t, n in sorted(by_type.items())]
    return (
        f"소재 폴더 {len(candidates)}개 ({', '.join(parts)}) · "
        f"총 미디어 파일 {total_files}개"
    )
