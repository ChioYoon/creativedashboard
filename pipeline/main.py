"""
CLI 진입점 — Com2uS R팀 소재 자동 태깅 파이프라인.

사용법:
    # 가상환경 활성화 후 (Windows PowerShell)
    .\\.venv\\Scripts\\Activate.ps1

    # 단일 타이틀 (Stage 2 호환)
    python -m pipeline.main --title pepp-us

    # 다중 타이틀 배치 (Stage 4) — titles.json의 enabled 타이틀 전체
    python -m pipeline.main --all-titles

    # 옵션: 차수·유형·개수 한정 (단일 타이틀 모드만)
    python -m pipeline.main --title pepp-us --phase 선론칭 --type BNR --limit 5

    # 옵션: 캐시 무시하고 강제 재태깅
    python -m pipeline.main --title pepp-us --no-cache

    # 옵션: dry-run (스캔만, Gemini 호출 X)
    python -m pipeline.main --all-titles --dry-run

산출:
    public/data/{title}.json — 대시보드 ?title= 으로 자동 로드됨
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from tqdm import tqdm

from .cache import TagCache, file_sha256
from .campaign_canonical import build_campaign_canonical
from .mmp_metrics import aggregate_rows_total, compute_mmp_quality
from .scanner import scan_creative_folders, scan_by_filename, summarize
from .schemas import CreativeDataset, CreativeRecord
from .scoring import compute_creative_scores
from .tagger import GeminiTagger, prompt_version, DEFAULT_GENRE

# Asia/Seoul timezone
KST = timezone(timedelta(hours=9))

# titles.json 위치 (프로젝트 루트 기준)
TITLES_JSON_PATH = Path("js/titles.json")

# 프로젝트 루트 (pipeline/../ = cloop_dashboard/)
_REPO_ROOT = Path(__file__).resolve().parent.parent


def _collect_campaign_names(records) -> set:
    """records 의 kpi_daily + mmp_daily 행에서 비어있지 않은 campaign_name 수집."""
    names = set()
    for r in records:
        for k in (getattr(r, "kpi_daily", None) or []):
            cn = getattr(k, "campaign_name", "")
            if cn:
                names.add(cn)
        for m in (getattr(r, "mmp_daily", None) or []):
            cn = getattr(m, "campaign_name", "")
            if cn:
                names.add(cn)
    return names


def _load_game_context(rel_path: str, repo_root: Path) -> str:
    """게임 컨텍스트 MD 로드. 경로 없거나 파일 없으면 빈 문자열 (graceful)."""
    if not rel_path:
        return ""
    full = repo_root / rel_path
    if not full.exists():
        print(f"[WARNING] _pipeline_game_context_file 없음: {full}")
        return ""
    return full.read_text(encoding="utf-8")


def _rel_source_path(p: Path, root) -> str:
    """파일을 root(단일 Path 또는 리스트) 기준 상대경로 문자열로. 매칭 root 없으면 파일명.

    멀티 루트(배너/비디오 분리 폴더) 타이틀은 각 파일이 속한 root 기준으로 환산.
    """
    roots = root if isinstance(root, list) else [root]
    for r in roots:
        try:
            if p.is_relative_to(r):
                return str(p.relative_to(r))
        except (ValueError, AttributeError):
            continue
    return p.name


def make_mmp_source(cfg: dict):
    """cfg['mmp_provider'](또는 airbridge_enabled 폴백)로 메인 MMP 소스 선택.

    Returns: (source, provider). 미설정이면 (None, "").
    """
    provider = (cfg.get("mmp_provider") or "").strip().lower()
    if not provider:
        provider = "airbridge" if cfg.get("airbridge_enabled") else ""
    if provider == "appsflyer":
        from .sources.appsflyer import AppsFlyerMmpSource
        src = AppsFlyerMmpSource.from_env(
            app_id=cfg.get("appsflyer_app_id") or "",
            usd_to_krw=cfg.get("airbridge_usd_to_krw") or 1.0,
            exclude_media_sources=set(cfg["appsflyer_exclude_media_sources"])
            if cfg.get("appsflyer_exclude_media_sources") else None,
        )
        return src, provider
    if provider == "airbridge":
        from .sources.airbridge import AirbridgeMmpSource
        src = AirbridgeMmpSource.from_env()
        if cfg.get("airbridge_usd_to_krw"):
            src.usd_to_krw = cfg["airbridge_usd_to_krw"]
        return src, provider
    return None, ""


# ─────────────────────────────────────────────────────────────
# Stage 5-D: 파일명 → 소재명(concept) 정규화
# ─────────────────────────────────────────────────────────────
# CSV 컨벤션:
#   파일명 (S열): 251104_BNR_A-Character-Adventure01A-DA_L_1200x628_EN[.jpg]
#   소재명 (T열): A-Character-Adventure01A-DA  ← 사이즈/언어/투입일 무관 콘셉트 코어
# 정규식 그룹 1 = concept (T열 값).
# 미스 시 None 반환 — main.py가 fallback (파일 stem 사용 또는 그대로).
_FILENAME_TO_CONCEPT_RE = re.compile(
    # lang(_[A-Z]+) 뒤 후행 세그먼트(_KR_NONE 등)·중복접미( (1)) 허용 — scanner.py FILENAME_PATTERN 과 정합
    r"^\d{6}_(?:BNR|VID|HTML5|IMG|MP4)_(.+?)_[LSVF]_\d+x\d+_[A-Z]+(?:_[A-Za-z0-9\-]+)*(?:\s*\(\d+\))?(?:\.[A-Za-z0-9]+)?$",
    re.IGNORECASE,
)


def filename_to_concept(filename: str) -> Optional[str]:
    """파일명에서 콘셉트 코어(CSV T열) 추출.

    예시:
        251104_BNR_A-Character-Adventure01A-DA_L_1200x628_EN.jpg
        → A-Character-Adventure01A-DA
        251104_VID_A-Character-Combat01A-UA_L_1920x1080_EN
        → A-Character-Combat01A-UA

    Returns:
        concept 문자열 또는 None (패턴 미스 시).
    """
    if not filename:
        return None
    m = _FILENAME_TO_CONCEPT_RE.match(filename.strip())
    return m.group(1) if m else None


def mmp_concept(name: str) -> str:
    """Airbridge ad_creative(파일명) → concept. 표준 정규식 우선, 실패 시 관대한 추출.

    Airbridge 소재명은 Google Ads/폴더와 동일 컨벤션이나 사이즈/해상도 토큰이 다양:
      251104_BNR_A-Character-Keyart01A-DA_L_1200x628_EN  → 표준(filename_to_concept)
      251104_BNR_A-Character-Keyart01A-DA_ALL_Mixed_EN   → Facebook 통합(_ALL_Mixed_) → fallback
    fallback: {6자리}_{유형}_ 접두 제거 후 concept(언더스코어 없음)만 취함.
    """
    if not name:
        return ""
    c = filename_to_concept(name)
    if c:
        return c
    stem = name.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    parts = stem.split("_")
    if len(parts) >= 3 and re.fullmatch(r"\d{6}", parts[0]):
        return parts[2]  # [date, TYPE, CONCEPT, size, res, lang] — concept 는 하이픈만 사용
    return stem


def inject_mmp_into_records(records, mmp_daily, source_name="airbridge", currency=None, fx_rate=None):
    """CreativeMmpDaily 리스트를 소재명(concept)으로 join 하여 records 에 mmp_* 주입.

    소재명 매칭: Airbridge ad_creative == 파일명/소재명 컨벤션. concept(폴더명) 기준 join.
    currency/fx_rate: 비용·매출 통화 메타(파이프라인에서 이미 변환 적용됨 — 표시용 라벨).
    """
    if not mmp_daily:
        return
    by_concept: dict[str, list] = {}
    for d in mmp_daily:
        by_concept.setdefault(mmp_concept(d.creative_name), []).append(d)

    for r in records:
        rows = by_concept.get(r.creative_id) or by_concept.get(r.소재명)
        if not rows:
            continue
        # concept 의 모든 변형(L/S/V·채널)을 하나로 합산 — Google Ads aggregate_kpi 와 동일 의미론.
        # (creative_name 별로 쪼개면 첫 변형만 반영되는 데이터 손실 발생 — 멀티변형 소재가 핵심 대상)
        a = aggregate_rows_total(rows)
        q = compute_mmp_quality(a)
        r.mmp_source = source_name
        r.mmp_currency = currency
        r.mmp_fx_rate = fx_rate
        r.mmp_channels = sorted(a["channels"])
        r.mmp_d1_ipm = None if q["d1_ipm"] is None else round(q["d1_ipm"], 3)
        r.mmp_d1_cpi = None if q["d1_cpi"] is None else round(q["d1_cpi"], 1)
        r.mmp_d7_roas = None if q["d7_roas"] is None else round(q["d7_roas"], 4)
        r.mmp_d1_retention = None if q["d1_retention"] is None else round(q["d1_retention"], 2)
        r.mmp_installs = a["installs"]
        r.mmp_retained_d1 = a["retained_d1"]
        r.mmp_cost = a["cost"]
        r.mmp_revenue = a["revenue_d7"]
        r.mmp_daily = rows

    # phase-2: 4지표 보유 소재들로 품질 종합점수 산출 후 주입 (대시보드 동일: 전환·D1 CPI·D1 IPM·D7 ROAS)
    scored_metrics = {
        r.creative_id: {"installs": r.mmp_installs, "d1_cpi": r.mmp_d1_cpi,
                        "d1_ipm": r.mmp_d1_ipm, "d7_roas": r.mmp_d7_roas}
        for r in records if r.mmp_source
    }
    if scored_metrics:
        from .mmp_metrics import compute_mmp_quality_scores
        qscores = compute_mmp_quality_scores(scored_metrics)
        for r in records:
            if r.creative_id in qscores:
                r.mmp_quality_score = qscores[r.creative_id]


# ─────────────────────────────────────────────────────────────
# 1. CLI 파서
# ─────────────────────────────────────────────────────────────
def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m pipeline.main",
        description="Com2uS R팀 소재 자동 태깅 (Stage 2/4)",
    )
    p.add_argument("--title", default=None, help="타이틀 ID (단일 모드, 기본: .env CLOOP_TITLE_ID)")
    p.add_argument(
        "--all-titles",
        action="store_true",
        help="js/titles.json의 _pipeline_enabled=true 타이틀 전체를 순차 처리 (Stage 4)",
    )
    p.add_argument(
        "--root",
        default=None,
        help="로컬 소재 루트 (단일 모드, 기본: .env CLOOP_CREATIVES_ROOT 또는 titles.json _pipeline_creatives_root)",
    )
    p.add_argument(
        "--phase",
        action="append",
        default=None,
        help="분석 차수 (기본: 선론칭). 다중 지정 가능: --phase 선론칭 --phase 사전예약",
    )
    p.add_argument(
        "--type",
        action="append",
        default=None,
        help="소재 유형 (기본: BNR, VID). 다중 지정 가능: --type BNR --type VID",
    )
    p.add_argument("--limit", type=int, default=0, help="소재 폴더 N개로 제한 (0=전체)")
    p.add_argument(
        "--pilot",
        action="store_true",
        help="(토큰 절감) 파일럿 모드 — 캐시 버전에 '-pilot' 접미 + 출력은 {title}.pilot.json. "
        "production 캐시/JSON 미오염으로 프롬프트를 자유롭게 반복 튜닝 (보통 --limit 와 함께).",
    )
    p.add_argument("--no-cache", action="store_true", help="캐시 무시하고 강제 재태깅")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="스캔만 수행. Gemini 호출 없이 발견된 소재 목록만 출력.",
    )
    p.add_argument(
        "--no-fallback",
        action="store_true",
        help="quota 한도 도달 시 flash-lite 자동 폴백 비활성화 (즉시 실패)",
    )
    p.add_argument(
        "--no-kpi",
        action="store_true",
        help="(Stage 5) 매체 KPI fetch 비활성화. 태깅만 진행. 디버그/오프라인 모드용.",
    )
    p.add_argument(
        "--kpi-window-days",
        type=int,
        default=0,
        help=(
            "(Stage 5) KPI 조회 윈도우 일수 명시 오버라이드. "
            "0 또는 미지정 시: titles.json _pipeline_google_ads_window_days → .env GOOGLE_ADS_KPI_WINDOW_DAYS → 28."
        ),
    )
    return p


# ─────────────────────────────────────────────────────────────
# 2. titles.json 로더 (Stage 4 신규)
# ─────────────────────────────────────────────────────────────
def load_titles_manifest() -> list[dict]:
    """js/titles.json을 읽어 _pipeline_enabled=true 타이틀만 반환."""
    if not TITLES_JSON_PATH.exists():
        sys.exit(f"❌ {TITLES_JSON_PATH} 가 없습니다. Stage 1 셋업이 누락되었을 수 있습니다.")
    raw = json.loads(TITLES_JSON_PATH.read_text(encoding="utf-8"))
    enabled = [t for t in raw if t.get("_pipeline_enabled")]
    if not enabled:
        sys.exit(f"❌ {TITLES_JSON_PATH} 에 _pipeline_enabled=true 타이틀이 없습니다.")
    return enabled


# ─────────────────────────────────────────────────────────────
# 3. 환경 변수 + 인자 통합
# ─────────────────────────────────────────────────────────────
def resolve_config(args, *, title_override: dict | None = None) -> dict:
    """단일 타이틀 설정 빌더.

    title_override: titles.json 항목 1개 (--all-titles 모드에서 전달).
                    None이면 args + .env 기반으로 구성 (Stage 2 호환 단일 모드).
    """
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    api_key = os.environ.get("GEMINI_API_KEY", "")
    cache_dir = os.environ.get("CACHE_DIR", "cache")
    output_dir = os.environ.get("OUTPUT_DIR", "public/data")

    # Stage 5: KPI 관련 환경 변수 (env 기본값 — titles.json 의 per-title 오버라이드가 우선)
    default_kpi_window_days = int(os.environ.get("GOOGLE_ADS_KPI_WINDOW_DAYS", "28") or "28")

    if title_override:
        # --all-titles 모드: titles.json의 _pipeline_* 필드 사용
        title = title_override["id"]
        root_str = title_override.get("_pipeline_creatives_root", "")
        phases = title_override.get("_pipeline_phases", ["선론칭"])
        types = title_override.get("_pipeline_types", ["BNR", "VID"])
        scan_mode = title_override.get("_pipeline_scan_mode", "foldered")
        prompt_version_pin = title_override.get("_pipeline_prompt_version_pin", "")
        genre = title_override.get("_pipeline_genre", DEFAULT_GENRE)
        game_context_file = title_override.get("_pipeline_game_context_file", "")
        # Stage 5 KPI 매핑 (titles.json _pipeline_google_ads_*)
        google_ads_customer_id = title_override.get("_pipeline_google_ads_customer_id", "")
        google_ads_campaign_filter = title_override.get("_pipeline_google_ads_campaign_filter", [])
        kpi_enabled = bool(title_override.get("_pipeline_kpi_enabled", False))
        kpi_window_days = int(
            title_override.get("_pipeline_google_ads_window_days", default_kpi_window_days)
            or default_kpi_window_days
        )
        kpi_start_date = title_override.get("_pipeline_kpi_start_date", "")
        airbridge_enabled = bool(title_override.get("_pipeline_airbridge_enabled", False))
        airbridge_exclude_channels = title_override.get("_pipeline_airbridge_exclude_channels",
                                                        ["google.adwords"])
        airbridge_usd_to_krw = float(title_override.get("_pipeline_airbridge_usd_to_krw", 0) or 0)
        mmp_provider = title_override.get("_pipeline_mmp_provider", "")
        appsflyer_app_id = title_override.get("_pipeline_appsflyer_app_id", "")
        appsflyer_exclude = title_override.get("_pipeline_appsflyer_exclude_media_sources", [])
        conversion_actions = title_override.get("_pipeline_conversion_actions")
    else:
        # 단일 타이틀 모드: CLI 인자 + titles.json _pipeline_* (Stage 5-D) + .env fallback
        title = args.title or os.environ.get("CLOOP_TITLE_ID", "")

        # Stage 5-D: titles.json에서 해당 타이틀 매칭 항목 자동 조회 (SSOT 유지)
        # 단일 모드에서도 _pipeline_google_ads_* 필드를 .env 없이 활용 가능하게 함.
        title_meta: dict = {}
        if title and TITLES_JSON_PATH.exists():
            try:
                titles_list = json.loads(TITLES_JSON_PATH.read_text(encoding="utf-8"))
                title_meta = next((t for t in titles_list if t.get("id") == title), {}) or {}
            except Exception as e:
                print(f"   [경고] titles.json 파싱 실패 (단일 모드 fallback): {e}")

        root_str = args.root or title_meta.get("_pipeline_creatives_root", "") or os.environ.get("CLOOP_CREATIVES_ROOT", "")
        phases = args.phase or title_meta.get("_pipeline_phases", ["선론칭"])
        types = args.type or title_meta.get("_pipeline_types", ["BNR", "VID"])
        scan_mode = title_meta.get("_pipeline_scan_mode", "foldered")
        prompt_version_pin = title_meta.get("_pipeline_prompt_version_pin", "")
        genre = title_meta.get("_pipeline_genre", DEFAULT_GENRE)
        game_context_file = title_meta.get("_pipeline_game_context_file", "")

        # Stage 5 KPI: titles.json 우선, .env fallback
        google_ads_customer_id = (
            title_meta.get("_pipeline_google_ads_customer_id", "")
            or os.environ.get("GOOGLE_ADS_CUSTOMER_ID", "")
        )
        google_ads_campaign_filter = title_meta.get("_pipeline_google_ads_campaign_filter", []) or []
        if not google_ads_campaign_filter:
            gcf = os.environ.get("GOOGLE_ADS_CAMPAIGN_FILTER", "")
            google_ads_campaign_filter = (
                [c.strip() for c in gcf.split(",") if c.strip()] if gcf else []
            )
        kpi_enabled = bool(
            title_meta.get("_pipeline_kpi_enabled", False)
            or (google_ads_customer_id and not title_meta)
        ) and not args.no_kpi
        # window_days: CLI > titles.json > .env > default 28
        kpi_window_days = (
            args.kpi_window_days
            if args.kpi_window_days
            else int(
                title_meta.get("_pipeline_google_ads_window_days", default_kpi_window_days)
                or default_kpi_window_days
            )
        )
        kpi_start_date = title_meta.get("_pipeline_kpi_start_date", "")
        airbridge_enabled = bool(title_meta.get("_pipeline_airbridge_enabled", False))
        airbridge_exclude_channels = title_meta.get("_pipeline_airbridge_exclude_channels",
                                                    ["google.adwords"])
        airbridge_usd_to_krw = float(title_meta.get("_pipeline_airbridge_usd_to_krw", 0) or 0)
        mmp_provider = title_meta.get("_pipeline_mmp_provider", "")
        appsflyer_app_id = title_meta.get("_pipeline_appsflyer_app_id", "")
        appsflyer_exclude = title_meta.get("_pipeline_appsflyer_exclude_media_sources", [])
        conversion_actions = title_meta.get("_pipeline_conversion_actions")

    if not title:
        sys.exit("❌ --title, --all-titles, 또는 .env CLOOP_TITLE_ID 가 필요합니다.")
    # creatives_root: 단일 문자열 또는 리스트(여러 폴더 — 예: 갓앤데몬 배너/비디오) 허용
    if isinstance(root_str, list):
        roots = [Path(str(r).strip()) for r in root_str if str(r).strip()]
    elif root_str and str(root_str).strip():
        roots = [Path(str(root_str).strip())]
    else:
        roots = []
    if not roots:
        sys.exit(
            f"❌ 타이틀 '{title}'의 creatives_root 가 비어있습니다. "
            "titles.json의 _pipeline_creatives_root 또는 .env CLOOP_CREATIVES_ROOT 를 설정하세요."
        )
    if not api_key and not args.dry_run:
        sys.exit(
            "❌ .env 의 GEMINI_API_KEY 가 비어있습니다. "
            "Google AI Studio(https://aistudio.google.com/apikey)에서 발급한 키를 .env 에 입력하세요."
        )

    return {
        "title": title,
        "root": roots[0] if len(roots) == 1 else roots,
        "model": model,
        "api_key": api_key,
        "cache_dir": Path(cache_dir),
        "output_dir": Path(output_dir),
        "phases": phases,
        "types": types,
        "scan_mode": scan_mode,
        "prompt_version_pin": prompt_version_pin,
        "genre": genre,
        "game_context_file": game_context_file,
        "pilot": args.pilot,
        "limit": args.limit,
        "no_cache": args.no_cache,
        "dry_run": args.dry_run,
        "no_fallback": args.no_fallback,
        # Stage 5: KPI 통합
        "no_kpi": args.no_kpi,
        "kpi_window_days": kpi_window_days,
        "kpi_start_date": kpi_start_date,
        "google_ads_customer_id": google_ads_customer_id,
        "google_ads_campaign_filter": google_ads_campaign_filter,
        "kpi_enabled": kpi_enabled and not args.no_kpi,
        "airbridge_enabled": bool(airbridge_enabled),
        "airbridge_exclude_channels": airbridge_exclude_channels,
        "airbridge_usd_to_krw": airbridge_usd_to_krw,
        "mmp_provider": mmp_provider,
        "appsflyer_app_id": appsflyer_app_id,
        "appsflyer_exclude_media_sources": appsflyer_exclude,
        "conversion_actions": conversion_actions,
    }


# ─────────────────────────────────────────────────────────────
# 4. 단일 타이틀 실행 (Stage 2 코어, --all-titles에서도 재사용)
# ─────────────────────────────────────────────────────────────
def run(cfg: dict) -> dict:
    """단일 타이틀의 태깅 파이프라인을 실행.

    Returns:
        실행 메트릭 dict — Stage 4 nightly 알림에 활용.
    """
    print(f"🎯 타이틀:        {cfg['title']}")
    print(f"📂 소재 루트:     {cfg['root']}")
    print(f"🗂  차수 필터:     {' / '.join(cfg['phases'])}")
    print(f"🎨 유형 필터:     {' / '.join(cfg['types'])}")
    print(f"⚙️  모델:          {cfg['model']}")
    print(f"💾 캐시 디렉토리: {cfg['cache_dir']}")
    print(f"📤 산출 디렉토리: {cfg['output_dir']}")
    if cfg["dry_run"]:
        print("🔧 모드:          DRY-RUN (스캔만, Gemini 호출 없음)")
    print()

    metrics: dict = {
        "title": cfg["title"],
        "status": "pending",
        "scanned_folders": 0,
        "tagged_records": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "failures": 0,
        "duration_sec": 0.0,
        "fallback_used": False,
        "output_path": None,
        "errors": [],
    }

    # ── 1) 스캔 ──
    print("🔍 1) 로컬 폴더 스캔 중...")
    try:
        if cfg.get("scan_mode") == "by-filename":
            # 파일명 기반 스캔 (폴더 레이아웃이 펩과 다른 타이틀 — 예: 도원암귀)
            candidates = scan_by_filename(root=cfg["root"], types=cfg["types"])
        else:
            candidates = scan_creative_folders(
                root=cfg["root"], phases=cfg["phases"], types=cfg["types"]
            )
    except FileNotFoundError as e:
        msg = f"소재 루트 폴더 없음: {e}"
        print(f"   [실패] {msg}")
        metrics["status"] = "skipped"
        metrics["errors"].append(msg)
        return metrics

    print(f"   → {summarize(candidates)}")
    metrics["scanned_folders"] = len(candidates)
    # Stage 5-I: 풀 백분위·KPI 매칭은 전체 기준(--limit 무관). 파일럿(--limit N)도
    # production 과 동일한 풀에서 백분위를 산출해야 캐시된 kpi_reality_check 가 정확.
    full_candidates = candidates
    if cfg["limit"] > 0:
        candidates = candidates[: cfg["limit"]]
        print(f"   → --limit {cfg['limit']} 적용: 태깅 {len(candidates)}개로 축소 (백분위 풀은 전체 {len(full_candidates)}개 유지)")
    if not candidates:
        msg = "분석 대상 소재 폴더가 없습니다 (경로/차수/유형 필터 확인 필요)"
        print(f"   [경고] {msg}")
        metrics["status"] = "empty"
        metrics["errors"].append(msg)
        return metrics

    if cfg["dry_run"]:
        print("\n📋 [DRY-RUN] 발견된 소재 미리보기:")
        for i, c in enumerate(candidates, 1):
            print(
                f"   {i:>3}. {c.creative_type:>3} | {c.phase} | {c.creative_name} "
                f"({len(c.all_files)}개 파일, 대표={c.representative_file.name if c.representative_file else '-'})"
            )
        print("\n✅ DRY-RUN 완료. 실제 태깅을 진행하려면 --dry-run 제거 후 재실행하세요.")
        metrics["status"] = "dry_run"
        return metrics

    # ── 2) 캐시·태거 준비 ──
    cache = TagCache(cfg["cache_dir"], cfg["title"])
    tagger = GeminiTagger(api_key=cfg["api_key"], model=cfg["model"])
    genre = cfg.get("genre", DEFAULT_GENRE)
    game_ctx = _load_game_context(cfg.get("game_context_file", ""), _REPO_ROOT)
    # ① 파일럿: 캐시 버전에 '-pilot' 접미 (production 캐시 미오염)
    # ② 타이틀 핀: _pipeline_prompt_version_pin 이 있으면 글로벌 bump 무시 (재태깅 격리)
    if cfg.get("pilot"):
        pversion = prompt_version(genre) + "-pilot"
    else:
        pversion = cfg.get("prompt_version_pin") or prompt_version(genre)
    fallback_model = "gemini-2.5-flash-lite"

    # ── 2-Stage5) KPI batch fetch (kpi_enabled=true 일 때만) ──
    kpi_index: dict[str, list] = {}  # creative_name → list[CreativeKpiDaily]
    kpi_window_start = None
    kpi_window_end = None
    kpi_status = "skipped"
    if cfg.get("kpi_enabled") and cfg.get("google_ads_customer_id"):
        try:
            from .sources.google_ads import GoogleAdsKpiSource, resolve_window
            from .cache import KpiCache

            source = GoogleAdsKpiSource.from_env()
            kpi_window_start, kpi_window_end = resolve_window(
                cfg["kpi_window_days"], cfg.get("kpi_start_date") or None
            )
            candidate_concepts = {c.creative_name for c in full_candidates}  # 폴더명 = T열 concept (전체 기준 — 풀 백분위용)
            print(
                f"\n💰 2.5) KPI fetch (Google Ads) — "
                f"{kpi_window_start} ~ {kpi_window_end}, "
                f"customer={cfg['google_ads_customer_id']}, candidate concept {len(candidate_concepts)}개..."
            )
            # Stage 5-D: IN() 필터 제거. 폴더명(concept) vs asset.name(파일명) 매칭 불가
            # → 전 asset fetch 후 concept 단위 그룹핑으로 매칭. SearchStream 1 operation 비용 동일.
            kpi_rows = list(
                source.fetch_window(
                    customer_id=cfg["google_ads_customer_id"],
                    start=kpi_window_start,
                    end=kpi_window_end,
                    creative_names=None,
                    campaign_filter=cfg.get("google_ads_campaign_filter") or None,
                    conversion_actions=cfg.get("conversion_actions"),
                )
            )
            # 그룹핑: concept(폴더명) → list[CreativeKpiDaily]
            # asset.name(파일명) 에서 concept 추출 → 같은 concept의 L/S/V 변형 + 캠페인 분리 모두 보존
            unmatched_assets: set[str] = set()
            for row in kpi_rows:
                concept = filename_to_concept(row.creative_name)
                if concept is None:
                    # 정규식 미스 — 파일명 stem 그대로 사용 (fallback)
                    concept = row.creative_name.rsplit(".", 1)[0]
                if concept in candidate_concepts:
                    kpi_index.setdefault(concept, []).append(row)
                else:
                    unmatched_assets.add(concept)
            if unmatched_assets:
                # candidate에 없는 asset (GDrive에 폴더 없는 경우) — 로그만
                print(
                    f"   ℹ️  candidate 미매칭 asset {len(unmatched_assets)}개 "
                    f"(GDrive 폴더에 없는 광고 asset, 대시보드 미표시): "
                    f"{sorted(unmatched_assets)[:3]}{'...' if len(unmatched_assets)>3 else ''}"
                )

            # KPI 캐시 보존 (백업·오프라인 분석용)
            try:
                kpi_cache = KpiCache(cfg["cache_dir"], cfg["title"])
                purged = kpi_cache.purge_old()
                for row in kpi_rows:
                    kpi_cache.put(
                        row.model_dump(),
                        source="google_ads",
                        customer_id=cfg["google_ads_customer_id"],
                    )
                kpi_cache.save()
                print(
                    f"   → {len(kpi_rows)}행 fetch 완료 ({len(kpi_index)}개 소재 매칭). "
                    f"캐시 오래된 항목 {purged}개 정리."
                )
            except Exception as cache_err:
                print(f"   [경고] KPI 캐시 저장 실패 (무시): {cache_err}")

            kpi_status = "success"
            metrics["kpi_rows_fetched"] = len(kpi_rows)
            metrics["kpi_creatives_matched"] = len(kpi_index)
        except Exception as e:
            err_type = type(e).__name__
            err_msg = f"KPI fetch 실패 ({err_type}): {e}"
            print(f"\n⚠️  {err_msg}")
            print("   → 태깅은 계속 진행, KPI 필드는 0으로 채워짐.")
            metrics["errors"].append(err_msg)
            kpi_status = "failed"
            # AuthError 만 batch 전체 중단 (다른 타이틀도 같은 token 사용)
            if err_type == "AuthError":
                metrics["status"] = "kpi_auth_failed"
                kpi_status = "auth_failed"
                # NOTE: 여기선 일단 태깅까지 마치고 정상 반환 — 호출 측에서 metrics 보고 결정
    else:
        if cfg.get("no_kpi"):
            print("\n💰 KPI fetch: --no-kpi 옵션으로 비활성화됨")
        elif not cfg.get("google_ads_customer_id"):
            print("\n💰 KPI fetch: customer_id 미설정으로 건너뜀")
    metrics["kpi_status"] = kpi_status

    # ── 2.6) Stage 7: MMP 페치 (Airbridge | AppsFlyer — 메인 프로바이더) ──
    mmp_status = "skipped"
    mmp_src, mmp_provider = make_mmp_source(cfg)
    if mmp_src is not None:
        try:
            from .sources.google_ads import resolve_window as _resolve_window
            _start, _end = _resolve_window(
                cfg.get("kpi_window_days") or 159, cfg.get("kpi_start_date") or None
            )
            # airbridge 는 채널 제외셋을 명시 전달, appsflyer 는 소스 내부 기본 제외셋 사용
            _exclude = set(cfg.get("airbridge_exclude_channels", [])) if mmp_provider == "airbridge" else None
            mmp_daily = mmp_src.fetch_mmp_window(_start, _end, exclude_channels=_exclude)
            cfg["_mmp_daily"] = mmp_daily
            cfg["_mmp_currency"] = mmp_src.currency
            cfg["_mmp_fx_rate"] = mmp_src.usd_to_krw
            cfg["_mmp_provider"] = mmp_provider
            mmp_status = "success_truncated" if mmp_src.last_fetch_truncated else "success"
            metrics["mmp_rows_fetched"] = len(mmp_daily)
            metrics["mmp_truncated"] = mmp_src.last_fetch_truncated
            metrics["mmp_provider"] = mmp_provider
            if mmp_src.last_fetch_truncated:
                metrics["errors"].append("MMP fetch 상한 도달 — 일부 소재 누락됨.")
            print(f"   → {mmp_provider} {len(mmp_daily)}행 fetch (非Google 매체, "
                  f"통화={mmp_src.currency} fx={mmp_src.usd_to_krw})")
        except FileNotFoundError:
            print(f"   💠 MMP({mmp_provider}): 토큰/앱ID 미설정 → 건너뜀")
            mmp_status = "skipped"
        except Exception as e:
            err_type = type(e).__name__
            print(f"\n⚠️  MMP fetch 실패 ({err_type}): {e} → mmp_* 비움, 진행 계속")
            metrics["errors"].append(f"MMP fetch 실패: {e}")
            mmp_status = "auth_failed" if err_type == "AuthError" else "failed"
    metrics["mmp_status"] = mmp_status

    # ── 2.7) Stage 5-I: 풀 데이터 컨텍스트 + 소재별 백분위 산출 ──
    # KPI 가 태깅보다 먼저 fetch 되므로(위) 태깅 시점에 풀 분포·실제 KPI 를
    # 컨텍스트로 주입 가능. 백분위는 코드가 정확히 계산 (AI 는 해석만).
    from .schemas import aggregate_kpi, signal_distribution

    POOL_IMP_THRESHOLD = 100  # 노출 100 미만은 KPI 노이즈 — 백분위 풀에서 제외

    def _pct_better(value, pool, higher_better=True):
        """value 가 pool(정렬 전 리스트)에서 이긴 비율 0-100 (높을수록 우수)."""
        if not pool or len(pool) < 2:
            return None
        if higher_better:
            beat = sum(1 for p in pool if p < value)
        else:
            beat = sum(1 for p in pool if p > value)
        return round(beat / (len(pool) - 1) * 100)

    # 소재별 집계 KPI (전체 후보 기준 — 풀 백분위가 --limit 에 영향받지 않도록)
    per_creative_kpi = {}  # creative_name → {ctr, cvr, cpa, imp}
    for c in full_candidates:
        daily = kpi_index.get(c.creative_name, [])
        if not daily:
            continue
        t = aggregate_kpi(daily)
        if t.impressions <= 0:
            continue
        per_creative_kpi[c.creative_name] = {
            "ctr": t.clicks / t.impressions * 100,
            "cvr": t.conversions / t.impressions * 100,
            "cpa": (t.cost / t.conversions) if t.conversions else None,
            "imp": t.impressions,
        }

    # 백분위 풀 (노출 임계 이상)
    pool = [v for v in per_creative_kpi.values() if v["imp"] >= POOL_IMP_THRESHOLD]
    ctr_pool = sorted(v["ctr"] for v in pool)
    cvr_pool = sorted(v["cvr"] for v in pool)
    cpa_pool = sorted(v["cpa"] for v in pool if v["cpa"] is not None)

    def _q(sorted_list, frac):
        if not sorted_list:
            return None
        return sorted_list[min(len(sorted_list) - 1, int(len(sorted_list) * frac))]

    # 소재별 백분위 (record 저장 + 컨텍스트용)
    creative_percentiles = {}  # creative_name → {ctr, cvr, cpa} (0-100, 높을수록 우수)
    for name, v in per_creative_kpi.items():
        creative_percentiles[name] = {
            "ctr": _pct_better(v["ctr"], ctr_pool, True),
            "cvr": _pct_better(v["cvr"], cvr_pool, True),
            "cpa": _pct_better(v["cpa"], cpa_pool, False) if v["cpa"] is not None else None,
        }

    # pool_context (공유 텍스트) — 직전 JSON 신호분포 + 백분위 임계
    pool_context = ""
    if pool:
        dist_line = ""
        try:
            prev_path = cfg["output_dir"] / f"{cfg['title']}.json"
            if prev_path.exists():
                prev = json.loads(prev_path.read_text(encoding="utf-8"))
                prev_creatives = prev.get("creatives", [])
                if prev_creatives:
                    sd = signal_distribution(prev_creatives)
                    n_prev = len(prev_creatives)
                    tops = [
                        f"'{k}' {v*100//n_prev}%"
                        for k, v in sd["strengths"].most_common(3)
                        if v * 100 // n_prev >= 50
                    ]
                    if tops:
                        dist_line = f"\n- 강점 분포(다수 공유 = 차별점 아님): {', '.join(tops)}"
        except Exception:
            pass

        def _fmt(q):
            return f"{q:.1f}" if q is not None else "?"
        pool_context = (
            f"[풀 데이터 컨텍스트 — 같은 타이틀 광고 집행 {len(pool)}개 소재 기준]"
            f"{dist_line}\n"
            f"- 실제 CTR 분포: 하위25% {_fmt(_q(ctr_pool, 0.25))}% / 중앙 {_fmt(_q(ctr_pool, 0.5))}% / 상위25% {_fmt(_q(ctr_pool, 0.75))}%\n"
            f"- 실제 CVR 분포: 하위25% {_fmt(_q(cvr_pool, 0.25))}% / 중앙 {_fmt(_q(cvr_pool, 0.5))}% / 상위25% {_fmt(_q(cvr_pool, 0.75))}%"
        )
    if pool_context:
        print(f"   📊 2.7) 풀 컨텍스트 산출: 백분위 풀 {len(pool)}개 소재 (노출≥{POOL_IMP_THRESHOLD})")

    def build_extra_context(creative_name):
        """소재별 동적 컨텍스트 (게임 컨텍스트 + pool_context + 이 소재 실제 성과)."""
        v = per_creative_kpi.get(creative_name)
        if not v:
            kpi_ctx = (pool_context + "\n[이 소재의 실제 성과] 광고 집행 이력 없음 — 시각 분석만 수행").strip()
        else:
            p = creative_percentiles.get(creative_name, {})
            # pct = 풀에서 이긴 비율(높을수록 우수). 절반 기준 상위/하위로 명확히 표현.
            def _top(pct):
                if pct is None:
                    return "?"
                return f"상위 {max(1, 100 - pct)}%" if pct >= 50 else f"하위 {max(1, pct)}%"
            parts = [f"CTR {v['ctr']:.1f}% ({_top(p.get('ctr'))})", f"CVR {v['cvr']:.2f}% ({_top(p.get('cvr'))})"]
            if v["cpa"] is not None:
                parts.append(f"CPA {round(v['cpa']):,}원 ({_top(p.get('cpa'))})")
            kpi_ctx = (pool_context + "\n[이 소재의 실제 성과] " + ", ".join(parts)).strip()
        # 게임 컨텍스트 prepend
        if not game_ctx:
            return kpi_ctx
        if not kpi_ctx:
            return f"[게임 컨텍스트]\n{game_ctx}"
        return f"[게임 컨텍스트]\n{game_ctx}\n\n{kpi_ctx}"

    # ── 3) 폴더별 태깅 루프 ──
    records: list[CreativeRecord] = []
    hits, misses, failures = 0, 0, 0
    skipped_quota = 0  # quota 소진으로 이번 실행에서 건너뛴 캐시 미스 항목 (다음 실행 시 자동 재시도)
    carried_forward = 0  # quota 소진 시 이전 버전 태그를 유지(carry-forward)한 소재 수
    started_at = time.time()
    daily_quota_exhausted = False  # 한 번 발생하면 같은 모델로 더 시도 불필요

    def _carry_forward(_sha: str):
        """현재 버전 태깅 불가(quota/실패) 시 이전 버전 태그가 있으면 그 tag_dict 반환.
        없으면 None. → 이전 태그 있는 소재는 출력에서 드롭되지 않음(대시보드 보존)."""
        _fb = cache.get_any(_sha, exclude_version=pversion)
        return _fb[0] if _fb is not None else None

    print(f"\n🚀 2) Gemini 태깅 시작 (프롬프트: {pversion}, 모델: {cfg['model']}) ...")
    for c in tqdm(candidates, desc="태깅", unit="소재"):
        rep = c.representative_file
        if not rep:
            tqdm.write(f"   [건너뜀] {c.creative_name}: 대표 파일 없음")
            continue

        sha = file_sha256(rep)
        cached = None if cfg["no_cache"] else cache.get(sha, pversion)
        if cached:
            tag_dict = cached
            hits += 1
        else:
            # 2026-06-11 수정: quota 소진 시에도 루프를 끊지 않고 (이전엔 break)
            # 캐시 미스 항목만 건너뜀 — 순서상 뒤에 있는 캐시 히트 record 가
            # 산출 JSON 에서 통째로 누락되던 퇴보(31→20건) 방지.
            if daily_quota_exhausted:
                # carry-forward: 현재 버전 미태깅이라도 이전 버전 태그가 있으면 유지(드롭 방지)
                cf = _carry_forward(sha)
                if cf is not None:
                    tag_dict = cf
                    carried_forward += 1
                else:
                    skipped_quota += 1
                    continue
            else:
                try:
                    # Stage 5-I: 풀 분포 + 이 소재 실제 KPI 백분위를 동적 컨텍스트로 주입
                    tag = tagger.tag_creative(rep, extra_context=build_extra_context(c.creative_name), genre=genre)
                    tag_dict = tag.model_dump()
                    cache.put(sha, pversion, tag_dict)
                    cache.save()
                    misses += 1
                except Exception as e:
                    err_msg = str(e)
                    # ── quota 한도 도달 시 flash-lite 폴백 (Stage 4 신규) ──
                    is_quota_exhausted = (
                        "GenerateRequestsPerDayPer" in err_msg
                        or ("429" in err_msg and "quota" in err_msg.lower())
                    )
                    if (
                        is_quota_exhausted
                        and not cfg["no_fallback"]
                        and not metrics["fallback_used"]
                    ):
                        tqdm.write(
                            f"   [폴백] {cfg['model']} quota 한도 → "
                            f"{fallback_model} 으로 전환하여 재시도"
                        )
                        cfg["model"] = fallback_model
                        _carry_usage = dict(tagger.usage)  # 1차 태거 토큰 실측 이어받기
                        tagger = GeminiTagger(api_key=cfg["api_key"], model=fallback_model)
                        for _k, _v in _carry_usage.items():
                            tagger.usage[_k] += _v
                        metrics["fallback_used"] = True
                        daily_quota_exhausted = False
                        # 같은 소재 재시도 (Stage 5-I: 동일 컨텍스트 주입)
                        try:
                            tag = tagger.tag_creative(rep, extra_context=build_extra_context(c.creative_name), genre=genre)
                            tag_dict = tag.model_dump()
                            cache.put(sha, pversion, tag_dict)
                            cache.save()
                            misses += 1
                        except Exception as e2:
                            cf = _carry_forward(sha)
                            if cf is not None:
                                tqdm.write(f"   [carry-forward] {c.creative_name}: 폴백 후 실패 → 이전 태그 유지 ({e2})")
                                tag_dict = cf
                                carried_forward += 1
                            else:
                                tqdm.write(f"   [실패] {c.creative_name} (폴백 후): {e2}")
                                failures += 1
                                continue
                    elif is_quota_exhausted and metrics["fallback_used"]:
                        # 폴백 모델도 한도 도달 — 이후 Gemini 호출은 스킵하되
                        # 캐시 히트/이전 태그(carry-forward)는 계속 처리 (퇴보 방지)
                        tqdm.write(
                            f"   [quota] {c.creative_name}: 폴백 모델 quota도 한도 도달 — "
                            f"이후 신규 태깅은 건너뛰고 캐시/이전 태그만 처리"
                        )
                        daily_quota_exhausted = True
                        cf = _carry_forward(sha)
                        if cf is not None:
                            tag_dict = cf
                            carried_forward += 1
                        else:
                            skipped_quota += 1
                            continue
                    else:
                        cf = _carry_forward(sha)
                        if cf is not None:
                            tqdm.write(f"   [carry-forward] {c.creative_name}: 태깅 실패 → 이전 태그 유지 ({e})")
                            tag_dict = cf
                            carried_forward += 1
                        else:
                            tqdm.write(f"   [실패] {c.creative_name}: {e}")
                            failures += 1
                            continue

        meta = c.parsed_meta

        # Stage 5: KPI 주입
        daily = kpi_index.get(c.creative_name, [])
        kpi_fields = {}
        preview_url: Optional[str] = None
        if daily:
            from .schemas import aggregate_kpi
            totals = aggregate_kpi(daily)
            kpi_fields = {
                "전환": int(round(totals.conversions)),
                "비용": int(round(totals.cost)),
                "노출수": totals.impressions,
                "클릭수": totals.clicks,
                "Revenue": int(round(totals.conversions_value)),
                "kpi_source": "google_ads",
                "kpi_window_start": kpi_window_start.isoformat() if kpi_window_start else None,
                "kpi_window_end": kpi_window_end.isoformat() if kpi_window_end else None,
                "kpi_daily": daily,
            }
            # Stage 5-D: 미리보기 URL — 대표 파일과 매칭되는 asset_url 우선, 없으면 임의 1개.
            # rep.name = 파일명 (예: 251104_BNR_..._L_1200x628_EN.jpg)
            # daily[].creative_name = 동일 형식 → 정확히 일치하는 행의 asset_url 선호
            rep_stem = rep.stem if rep else ""
            rep_name = rep.name if rep else ""
            for d in daily:
                if not d.asset_url:
                    continue
                d_name = d.creative_name or ""
                if d_name == rep_name or d_name.rsplit(".", 1)[0] == rep_stem:
                    preview_url = d.asset_url
                    break
            if not preview_url:
                # fallback: 첫 번째 URL이 있는 row
                preview_url = next((d.asset_url for d in daily if d.asset_url), None)

        # Stage 5-E: v2 신호 구조 추출 (서술형 marketer_insight 대체)
        # Stage 5-H v3: tag_dict 의 strengths/weaknesses/test_ideas 가 object-list
        # ({signal, evidence} / {idea, action}) 로 들어옴 — parallel-list 로 평탄화.
        # 정렬은 Gemini 경계(CreativeTag object-list)에서 구조적으로 보장됨.
        # 구 캐시 형태(list[str]) 는 PROMPT_VERSION 키로 격리되어 유입 불가.
        one_line = tag_dict.get("one_line_insight")
        _strength_items = tag_dict.get("strengths", []) or []
        _weakness_items = tag_dict.get("weaknesses", []) or []
        _test_items = tag_dict.get("test_ideas", []) or []
        record = CreativeRecord(
            creative_id=c.creative_name,
            소재명=c.creative_name,
            파일명=rep.name,
            유형=c.creative_type,
            일=meta.get("iso_date"),
            사이즈=meta.get("resolution"),
            언어=meta.get("lang"),
            링크=preview_url,  # Stage 5-D: Google Ads image_asset.full_size.url / youtube URL 자동 주입
            creative_concept=filename_to_concept(rep.name) or c.creative_name,  # T열 정규화 (fallback=폴더명)
            hooking_strategy=tag_dict.get("hooking_strategy"),
            USP=tag_dict.get("core_usp"),
            art_style=tag_dict.get("visual_style"),
            # Stage 5-H v3: object-list → parallel-list 평탄화 (하위 소비자 호환)
            strengths=[i["signal"] for i in _strength_items],
            strength_evidence=[i.get("evidence", "") for i in _strength_items],
            weaknesses=[i["signal"] for i in _weakness_items],
            weakness_evidence=[i.get("evidence", "") for i in _weakness_items],
            hypothesis=tag_dict.get("hypothesis", []),
            test_ideas=[i["idea"] for i in _test_items],
            improvement_actions=[i.get("action", "") for i in _test_items],
            creator_intent=tag_dict.get("creator_intent"),
            one_line_insight=one_line,
            # Stage 5-I: 실제 KPI 정합성 해석(AI) + 백분위(코드 산출).
            # 하드 가드: KPI 없는 소재는 모델 출력과 무관하게 강제 None —
            # flash-lite 폴백이 타 소재 수치를 베껴 환각 reality_check 를 쓴 사례 차단.
            kpi_reality_check=(
                tag_dict.get("kpi_reality_check")
                if c.creative_name in per_creative_kpi
                else None
            ),
            kpi_percentiles=creative_percentiles.get(c.creative_name),
            # Stage 5-F-1: marketer_insight dual-write 제거 — alias는 js/data-source.js
            # normalizeFromJson() 에서 처리. Python schema 의 marketer_insight 필드는
            # 다음 회차에 제거 예정 (구 JSON 호환 위해 일단 default=None).
            # marketer_insight=one_line,  # ← 제거됨 (JS-side alias 로 대체)
            tagged_at=datetime.now(KST).isoformat(timespec="seconds"),
            gemini_model=cfg["model"],
            source_files=[_rel_source_path(p, cfg["root"]) for p in c.all_files],
            **kpi_fields,
        )
        records.append(record)

    # Stage 7: 페치해둔 MMP daily 를 records 에 주입 (소재명 join)
    if cfg.get("_mmp_daily"):
        inject_mmp_into_records(records, cfg["_mmp_daily"], source_name=cfg.get("_mmp_provider") or "airbridge",
                                currency=cfg.get("_mmp_currency"), fx_rate=cfg.get("_mmp_fx_rate"))

    # ── Stage 6: 점수 산출 (대시보드 calculateCreativeScores 와 동일 — pipeline/scoring.py) ──
    # 기본 가중치 25/25/25/25 + roas_mode=auto. compute_creative_scores 가 입력 dict 를
    # in-place 변형하므로 records 와 positional zip (소재명 중복 무관). KPI 없는 타이틀은
    # 전 소재 0 → 무해. 대시보드는 KPI 로 런타임 재계산하므로 이 스냅샷은 이메일·리포트용.
    score_summary = {"graded": 0, "grades": {}, "top": None}
    if records:
        score_inputs = [
            {"전환": r.전환, "비용": r.비용, "노출수": r.노출수, "클릭수": r.클릭수, "매출": r.Revenue}
            for r in records
        ]
        compute_creative_scores(score_inputs)  # in-place 변형
        for r, s in zip(records, score_inputs):
            r.scores = {
                "total": round(s["TotalScore"], 2),
                "grade": s["등급"],
                "rank": s["Rank"],
                "conv": round(s["전환수점수"], 2),
                "cpa": round(s["CPA점수"], 2),
                "ipm": round(s["IPM점수"], 2),
                "roas": None if s["ROAS점수"] is None else round(s["ROAS점수"], 2),
            }
        # 이메일/콘솔용 요약 — KPI 보유분(점수 변별 있는 소재)만 집계
        scored_records = [r for r in records if (r.전환 or r.노출수 or r.비용)]
        for r in scored_records:
            g = r.scores["grade"]
            score_summary["grades"][g] = score_summary["grades"].get(g, 0) + 1
        score_summary["graded"] = len(scored_records)
        if scored_records:
            best = min(scored_records, key=lambda r: r.scores["rank"])
            score_summary["top"] = {"name": best.소재명, "total": best.scores["total"], "grade": best.scores["grade"]}

    # ── 4) 산출물 저장 ──
    cache.save()
    duration = time.time() - started_at
    dataset = CreativeDataset(
        title_id=cfg["title"],
        generated_at=datetime.now(KST).isoformat(timespec="seconds"),
        gemini_model=cfg["model"],
        creatives=records,
        metrics={
            "scanned_folders": len(candidates),
            "tagged_records": len(records),
            "cache_hits": hits,
            "cache_misses": misses,
            "failures": failures,
            "duration_sec": round(duration, 1),
            "prompt_version": pversion,
            "fallback_used": metrics["fallback_used"],
            "carried_forward": carried_forward,
            "score_summary": score_summary,  # Stage 6: 기본 가중치 점수 요약
        },
        campaign_canonical=build_campaign_canonical(_collect_campaign_names(records)),
    )

    # ① 파일럿은 별도 파일로 출력 (production JSON 미오염 — 백업/복원 불필요)
    out_name = f"{cfg['title']}.pilot.json" if cfg.get("pilot") else f"{cfg['title']}.json"
    out_path = cfg["output_dir"] / out_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = dataset.model_dump(by_alias=True)
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print()
    print(f"✅ 완료 ({duration:.1f}초)")
    print(f"   캐시 히트:     {hits}")
    print(f"   Gemini 호출:   {misses}")
    print(f"   실패:          {failures}")
    if skipped_quota:
        print(f"   quota 보류:    {skipped_quota} (다음 실행/nightly 에서 자동 재시도)")
    if carried_forward:
        print(f"   carry-forward: {carried_forward}건 (이전 버전 태그 유지 — 재태깅 수렴 중)")
    if metrics["fallback_used"]:
        print(f"   폴백 사용:     ✅ {fallback_model}")
    u = tagger.usage
    if u["calls"] > 0:
        print(
            f"   토큰 실측:     입력 {u['prompt']:,} / 출력 {u['output']:,} / "
            f"thinking {u['thoughts']:,} / 합계 {u['total']:,} "
            f"({u['calls']}콜, 평균 {u['total'] // max(1, u['calls']):,}/콜)"
        )
    if score_summary["graded"] > 0:
        g = score_summary["grades"]
        grade_str = " · ".join(f"{k} {v}" for k, v in g.items())
        print(f"   점수 산출:     KPI 보유 {score_summary['graded']}건 ({grade_str})")
        if score_summary["top"]:
            t = score_summary["top"]
            print(f"   최고 점수:     {t['name']} — {t['total']}점 ({t['grade']})")
    print(f"   산출 파일:     {out_path}")
    print(f"   대시보드 URL:  step1_integrated.html?title={cfg['title']}")

    metrics.update({
        "status": "success" if (failures == 0 and skipped_quota == 0) else "partial",
        "tagged_records": len(records),
        "cache_hits": hits,
        "cache_misses": misses,
        "failures": failures,
        "token_usage": dict(tagger.usage),
        "skipped_quota": skipped_quota,
        "duration_sec": round(duration, 1),
        "output_path": str(out_path),
        "daily_quota_exhausted": daily_quota_exhausted,
        "score_summary": score_summary,  # Stage 6: 이메일 알림용 점수 요약
    })
    return metrics


# ─────────────────────────────────────────────────────────────
# 5. 다중 타이틀 배치 (Stage 4 신규)
# ─────────────────────────────────────────────────────────────
def run_all_titles(args) -> dict:
    """js/titles.json의 enabled 타이틀 전체를 순차 처리."""
    titles = load_titles_manifest()
    print(f"📚 다중 타이틀 배치 모드 — {len(titles)}개 타이틀")
    for i, t in enumerate(titles, 1):
        print(f"   {i}. {t['id']} ({t.get('name', '?')})")
    print()

    batch_started = time.time()
    results: list[dict] = []
    for i, title_entry in enumerate(titles, 1):
        print(f"\n{'═' * 70}")
        print(f"  [{i}/{len(titles)}] {title_entry['id']}")
        print(f"{'═' * 70}\n")
        try:
            cfg = resolve_config(args, title_override=title_entry)
            metric = run(cfg)
        except SystemExit as e:
            metric = {
                "title": title_entry["id"],
                "status": "config_error",
                "errors": [str(e.code) if e.code else "unknown config error"],
            }
        except Exception as e:
            metric = {
                "title": title_entry["id"],
                "status": "exception",
                "errors": [f"{type(e).__name__}: {e}"],
            }
        results.append(metric)

    batch_duration = time.time() - batch_started

    # ── 배치 요약 ──
    print(f"\n{'═' * 70}")
    print(f"  📊 배치 요약 (총 {batch_duration:.1f}초)")
    print(f"{'═' * 70}")
    for r in results:
        status_icon = {
            "success": "✅",
            "partial": "⚠️",
            "empty": "📭",
            "skipped": "⏭",
            "dry_run": "🔧",
            "config_error": "❌",
            "exception": "💥",
        }.get(r.get("status", "?"), "?")
        print(
            f"   {status_icon} {r['title']:25s} "
            f"status={r.get('status', '?'):12s} "
            f"records={r.get('tagged_records', 0):3d} "
            f"failures={r.get('failures', 0)}"
        )
    print()

    return {
        "batch_duration_sec": round(batch_duration, 1),
        "title_count": len(titles),
        "results": results,
    }


# ─────────────────────────────────────────────────────────────
# 6. 엔트리
# ─────────────────────────────────────────────────────────────
def main() -> None:
    load_dotenv()
    args = build_arg_parser().parse_args()

    # 등록부(xlsx) → titles.json 자동 생성 (CLOOP_REGISTRY_XLSX 설정 시 opt-in)
    _reg = os.environ.get("CLOOP_REGISTRY_XLSX", "").strip()
    if _reg:
        try:
            from .registry import build_titles_json
            _s = build_titles_json(_reg)
            print(f"📋 등록부 → titles.json: {_s['status']} · 생성 {_s['generated']}개 · 스킵 {_s['skipped']}개")
            for _w in _s.get("warnings", []):
                print(f"   ⚠️  {_w}")
        except Exception as _e:
            print(f"⚠️  등록부 생성 실패(기존 titles.json 유지하고 계속): {_e}")

    try:
        if args.all_titles:
            batch_result = run_all_titles(args)
            # Stage 4: 알림 모듈 호출 (선택적, 실패해도 무시)
            try:
                from .notify import send_batch_notification
                send_batch_notification(batch_result)
            except Exception as e:
                print(f"⚠️  알림 발송 실패 (무시하고 계속): {e}")
            # 종료 코드: 실패가 있으면 1, 전체 성공이면 0
            any_failure = any(
                r.get("status") in ("partial", "config_error", "exception")
                for r in batch_result["results"]
            )
            sys.exit(1 if any_failure else 0)
        else:
            # 단일 타이틀 모드 (Stage 2 호환)
            cfg = resolve_config(args)
            metric = run(cfg)
            sys.exit(0 if metric.get("failures", 0) == 0 else 1)
    except KeyboardInterrupt:
        print("\n⚠️  사용자가 중단했습니다. (캐시는 부분적으로 저장됨)")
        sys.exit(130)


if __name__ == "__main__":
    main()
