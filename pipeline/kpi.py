"""
KPI 검증용 CLI (Stage 5).

사용법:
    # 인증 healthcheck (Stage 5-A 완료 검증용)
    python -m pipeline.kpi --healthcheck

    # 특정 타이틀의 최근 N일 KPI 조회 (dry-run, JSON 미저장)
    python -m pipeline.kpi --title pepp-us --days 3 --limit 5 --dry-run

    # 실 fetch + cache 갱신 (main.py에 통합 전 수동 검증)
    python -m pipeline.kpi --title pepp-us --days 28

목적:
- IT 승인 직후 인증이 동작하는지 1초 만에 확인 (`--healthcheck`)
- main.py 통합 전 GAQL 쿼리·매핑이 실제로 맞는지 사람이 확인
- 캐시 상태 점검 (`--cache-stats`)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m pipeline.kpi",
        description="Google Ads KPI 검증 CLI (Stage 5)",
    )
    p.add_argument(
        "--healthcheck",
        action="store_true",
        help="OAuth 인증 + login_customer_id 접근 가능 여부만 확인. 즉시 종료.",
    )
    p.add_argument("--title", default=None, help="js/titles.json 의 타이틀 ID")
    p.add_argument(
        "--customer-id",
        default=None,
        help="Google Ads customer ID (10자리, 하이픈 없이). 미지정 시 titles.json에서 조회.",
    )
    p.add_argument("--days", type=int, default=7, help="조회 기간 (기본 7일)")
    p.add_argument("--limit", type=int, default=0, help="처음 N개 소재만 (0=전체)")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="실 API 호출하지 않고 GAQL 쿼리만 출력",
    )
    p.add_argument(
        "--cache-stats",
        action="store_true",
        help="KPI 캐시 상태(엔트리 수, 디스크 크기) 출력 후 종료",
    )
    return p


def cmd_healthcheck() -> int:
    """OAuth + login_customer_id 검증."""
    print("🔍 Google Ads API healthcheck...")
    try:
        from .sources.google_ads import GoogleAdsKpiSource
        source = GoogleAdsKpiSource.from_env()
    except FileNotFoundError as e:
        print(f"❌ 설정 파일 누락: {e}")
        return 1
    except Exception as e:
        print(f"❌ 초기화 실패: {type(e).__name__}: {e}")
        return 1

    ok = source.auth_check()
    if ok:
        print(f"✅ Google Ads API 인증 OK (MCC={source.login_customer_id})")
        print("   → Stage 5-B 진입 조건 충족")
        return 0
    else:
        print("❌ 인증 실패. .secrets/google_ads.yaml 의 refresh_token 또는 client_secret 확인 필요.")
        print("   재발급: .\\scripts\\setup-google-ads.ps1")
        return 1


def _load_titles_manifest() -> list[dict]:
    path = Path("js/titles.json")
    if not path.exists():
        sys.exit(f"❌ {path} 가 없습니다.")
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_title_customer(title_id: str) -> tuple[str, str, list[str]]:
    """titles.json에서 customer_id, campaign_filter 조회.

    Returns:
        (customer_id, login_customer_id_optional, campaign_filter_list)
    """
    titles = _load_titles_manifest()
    matched = next((t for t in titles if t.get("id") == title_id), None)
    if not matched:
        sys.exit(f"❌ titles.json에 title='{title_id}' 가 없습니다.")
    customer_id = matched.get("_pipeline_google_ads_customer_id", "")
    if not customer_id:
        sys.exit(f"❌ '{title_id}'의 _pipeline_google_ads_customer_id 가 비어있습니다.")
    campaign_filter = matched.get("_pipeline_google_ads_campaign_filter", []) or []
    return customer_id, "", campaign_filter


def cmd_fetch(args) -> int:
    """KPI fetch — main.py 통합 전 수동 검증."""
    if args.dry_run:
        # GAQL 쿼리만 출력하고 종료
        from .sources.google_ads import GoogleAdsKpiSource

        end = date.today() - timedelta(days=1)
        start = end - timedelta(days=args.days - 1)
        # creative_names는 미지정 (모든 ENABLED ad)
        query = GoogleAdsKpiSource._build_gaql(
            start=start,
            end=end,
            creative_names_chunk=None,
            campaign_filter=None,
        )
        print(f"🔍 [DRY-RUN] GAQL preview ({start} ~ {end}):")
        print()
        print(query)
        print()
        print("✅ 실 호출 안 함. --dry-run 제거 후 재실행하면 실제 API 호출.")
        return 0

    if not args.title and not args.customer_id:
        sys.exit("❌ --title 또는 --customer-id 중 하나 필요")

    # customer_id 결정
    if args.customer_id:
        customer_id = args.customer_id.replace("-", "").strip()
        campaign_filter = []
    else:
        customer_id, _, campaign_filter = _resolve_title_customer(args.title)

    # Source 초기화
    print(f"🔍 Google Ads KPI fetch — customer={customer_id}, {args.days}일")
    try:
        from .sources.google_ads import GoogleAdsKpiSource
        source = GoogleAdsKpiSource.from_env()
    except Exception as e:
        print(f"❌ Source 초기화 실패: {e}")
        return 1

    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=args.days - 1)

    try:
        kpi_rows = list(
            source.fetch_window(
                customer_id=customer_id,
                start=start,
                end=end,
                creative_names=None,
                campaign_filter=campaign_filter or None,
            )
        )
    except Exception as e:
        print(f"❌ fetch 실패: {type(e).__name__}: {e}")
        return 1

    if not kpi_rows:
        print(f"⚠️  {start} ~ {end} 기간에 KPI 데이터 0행. customer/캠페인/필터 확인 필요.")
        return 0

    # 결과 표시 — 소재별 합계
    by_creative: dict[str, dict] = {}
    for row in kpi_rows:
        agg = by_creative.setdefault(
            row.creative_name,
            {"impressions": 0, "clicks": 0, "cost": 0.0, "conversions": 0.0, "days": 0},
        )
        agg["impressions"] += row.impressions
        agg["clicks"] += row.clicks
        agg["cost"] += row.cost
        agg["conversions"] += row.conversions
        agg["days"] += 1

    print(f"\n📊 결과 — {len(kpi_rows)}행 fetch, {len(by_creative)}개 소재 매칭")
    print()
    print(f"{'소재명':<50} | {'노출':>10} | {'클릭':>6} | {'비용':>10} | {'전환':>6} | 일수")
    print("-" * 110)
    items = sorted(by_creative.items(), key=lambda x: -x[1]["impressions"])
    if args.limit > 0:
        items = items[: args.limit]
    for name, agg in items:
        print(
            f"{name[:48]:<50} | "
            f"{agg['impressions']:>10,} | "
            f"{agg['clicks']:>6,} | "
            f"{int(round(agg['cost'])):>10,} | "
            f"{agg['conversions']:>6.0f} | "
            f"{agg['days']:>3}일"
        )

    print()
    print("✅ 검증 완료. main.py 자동화 통합 시 같은 데이터가 public/data/{title}.json 에 주입됩니다.")
    return 0


def cmd_cache_stats(args) -> int:
    if not args.title:
        sys.exit("❌ --cache-stats 는 --title 필요")
    from .cache import KpiCache

    cache_dir = Path("cache")
    cache = KpiCache(cache_dir, args.title)
    stats = cache.stats()
    path = Path(stats["path"])
    print(f"📁 캐시 파일: {stats['path']}")
    print(f"   엔트리 수: {stats['entries']:,}")
    if path.exists():
        print(f"   디스크 크기: {path.stat().st_size / 1024:.1f} KB")
    return 0


def main() -> None:
    load_dotenv()
    args = build_arg_parser().parse_args()

    if args.healthcheck:
        sys.exit(cmd_healthcheck())
    if args.cache_stats:
        sys.exit(cmd_cache_stats(args))
    sys.exit(cmd_fetch(args))


if __name__ == "__main__":
    main()
