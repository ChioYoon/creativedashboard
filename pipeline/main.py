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
from .scanner import scan_creative_folders, summarize
from .schemas import CreativeDataset, CreativeRecord
from .tagger import GeminiTagger, prompt_version

# Asia/Seoul timezone
KST = timezone(timedelta(hours=9))

# titles.json 위치 (프로젝트 루트 기준)
TITLES_JSON_PATH = Path("js/titles.json")


# ─────────────────────────────────────────────────────────────
# Stage 5-D: 파일명 → 소재명(concept) 정규화
# ─────────────────────────────────────────────────────────────
# CSV 컨벤션:
#   파일명 (S열): 251104_BNR_A-Character-Adventure01A-DA_L_1200x628_EN[.jpg]
#   소재명 (T열): A-Character-Adventure01A-DA  ← 사이즈/언어/투입일 무관 콘셉트 코어
# 정규식 그룹 1 = concept (T열 값).
# 미스 시 None 반환 — main.py가 fallback (파일 stem 사용 또는 그대로).
_FILENAME_TO_CONCEPT_RE = re.compile(
    r"^\d{6}_(?:BNR|VID|HTML5|IMG|MP4)_(.+?)_[LSVF]_\d+x\d+_[A-Z]+(?:\.[A-Za-z0-9]+)?$",
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
        # Stage 5 KPI 매핑 (titles.json _pipeline_google_ads_*)
        google_ads_customer_id = title_override.get("_pipeline_google_ads_customer_id", "")
        google_ads_campaign_filter = title_override.get("_pipeline_google_ads_campaign_filter", [])
        kpi_enabled = bool(title_override.get("_pipeline_kpi_enabled", False))
        kpi_window_days = int(
            title_override.get("_pipeline_google_ads_window_days", default_kpi_window_days)
            or default_kpi_window_days
        )
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

    if not title:
        sys.exit("❌ --title, --all-titles, 또는 .env CLOOP_TITLE_ID 가 필요합니다.")
    if not root_str:
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
        "root": Path(root_str),
        "model": model,
        "api_key": api_key,
        "cache_dir": Path(cache_dir),
        "output_dir": Path(output_dir),
        "phases": phases,
        "types": types,
        "limit": args.limit,
        "no_cache": args.no_cache,
        "dry_run": args.dry_run,
        "no_fallback": args.no_fallback,
        # Stage 5: KPI 통합
        "no_kpi": args.no_kpi,
        "kpi_window_days": kpi_window_days,
        "google_ads_customer_id": google_ads_customer_id,
        "google_ads_campaign_filter": google_ads_campaign_filter,
        "kpi_enabled": kpi_enabled and not args.no_kpi,
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
    if cfg["limit"] > 0:
        candidates = candidates[: cfg["limit"]]
        print(f"   → --limit {cfg['limit']} 적용: {len(candidates)}개로 축소")
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
    pversion = prompt_version()
    fallback_model = "gemini-2.5-flash-lite"

    # ── 2-Stage5) KPI batch fetch (kpi_enabled=true 일 때만) ──
    kpi_index: dict[str, list] = {}  # creative_name → list[CreativeKpiDaily]
    kpi_window_start = None
    kpi_window_end = None
    kpi_status = "skipped"
    if cfg.get("kpi_enabled") and cfg.get("google_ads_customer_id"):
        try:
            from .sources.google_ads import GoogleAdsKpiSource, default_window
            from .cache import KpiCache

            source = GoogleAdsKpiSource.from_env()
            kpi_window_start, kpi_window_end = default_window(cfg["kpi_window_days"])
            candidate_concepts = {c.creative_name for c in candidates}  # 폴더명 = T열 concept
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

    # ── 3) 폴더별 태깅 루프 ──
    records: list[CreativeRecord] = []
    hits, misses, failures = 0, 0, 0
    started_at = time.time()
    daily_quota_exhausted = False  # 한 번 발생하면 같은 모델로 더 시도 불필요

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
            try:
                tag = tagger.tag_creative(rep)
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
                    tagger = GeminiTagger(api_key=cfg["api_key"], model=fallback_model)
                    metrics["fallback_used"] = True
                    daily_quota_exhausted = False
                    # 같은 소재 재시도
                    try:
                        tag = tagger.tag_creative(rep)
                        tag_dict = tag.model_dump()
                        cache.put(sha, pversion, tag_dict)
                        cache.save()
                        misses += 1
                    except Exception as e2:
                        tqdm.write(f"   [실패] {c.creative_name} (폴백 후): {e2}")
                        failures += 1
                        continue
                elif is_quota_exhausted and metrics["fallback_used"]:
                    # 폴백 모델도 한도 도달
                    tqdm.write(
                        f"   [실패] {c.creative_name}: 폴백 모델 quota도 한도 도달, 나머지 건너뜀"
                    )
                    failures += 1
                    daily_quota_exhausted = True
                    break  # 더 시도해도 같은 에러, 루프 종료
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
        one_line = tag_dict.get("one_line_insight")
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
            # Stage 5-E v2: 구조화 신호 (분석·집계용). schema 가 default_factory=list 보장.
            strengths=tag_dict.get("strengths", []),
            weaknesses=tag_dict.get("weaknesses", []),
            hypothesis=tag_dict.get("hypothesis", []),
            test_ideas=tag_dict.get("test_ideas", []),
            one_line_insight=one_line,
            # 후방 호환: 기존 대시보드가 marketer_insight 참조 시 깨지지 않도록 한 줄 가설 주입
            # (Stage 5-F: 대시보드 JS normalizeFromJson 에서 alias 처리 후 schema 측 필드는 제거 예정)
            marketer_insight=one_line,
            tagged_at=datetime.now(KST).isoformat(timespec="seconds"),
            gemini_model=cfg["model"],
            source_files=[str(p.relative_to(cfg["root"])) for p in c.all_files],
            **kpi_fields,
        )
        records.append(record)

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
        },
    )

    out_path = cfg["output_dir"] / f"{cfg['title']}.json"
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
    if metrics["fallback_used"]:
        print(f"   폴백 사용:     ✅ {fallback_model}")
    print(f"   산출 파일:     {out_path}")
    print(f"   대시보드 URL:  step1_integrated.html?title={cfg['title']}")

    metrics.update({
        "status": "success" if failures == 0 else "partial",
        "tagged_records": len(records),
        "cache_hits": hits,
        "cache_misses": misses,
        "failures": failures,
        "duration_sec": round(duration, 1),
        "output_path": str(out_path),
        "daily_quota_exhausted": daily_quota_exhausted,
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
