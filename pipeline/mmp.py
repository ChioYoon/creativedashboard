# -*- coding: utf-8 -*-
"""MMP(Airbridge) 검증용 CLI — Stage 7.

  python -m pipeline.mmp --healthcheck                  # 토큰·앱 접근 검증
  python -m pipeline.mmp --metadata-check               # 7-A: ad_creative groupBy 지원 확인
  python -m pipeline.mmp --title pepp-us --days 30 --dry-run   # 호출 바디만 출력
  python -m pipeline.mmp --title pepp-us --days 30      # 실 페치 + 소재별 4지표 출력
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta

from dotenv import load_dotenv


def _exclude_channels() -> set:
    import os
    from .sources.airbridge import DEFAULT_EXCLUDE_CHANNELS
    raw = os.environ.get("AIRBRIDGE_EXCLUDE_CHANNELS", ",".join(DEFAULT_EXCLUDE_CHANNELS))
    return {c.strip() for c in raw.split(",") if c.strip()}


def cmd_healthcheck() -> int:
    print("🔍 Airbridge API healthcheck...")
    try:
        from .sources.airbridge import AirbridgeMmpSource
        src = AirbridgeMmpSource.from_env()
    except Exception as e:
        print(f"❌ 초기화 실패: {type(e).__name__}: {e}")
        return 1
    if src.auth_check():
        print(f"✅ Airbridge 인증 OK (app={src.app_name}) → Stage 7-B 진입 조건 충족")
        return 0
    print("❌ 인증 실패. .env 의 AIRBRIDGE_API_TOKEN / AIRBRIDGE_APP_NAME 확인.")
    return 1


def cmd_metadata_check() -> int:
    """7-A 검증: Actuals dataspec 에서 ad_creative 필드 + 매핑된 메트릭 존재 확인."""
    from .sources.airbridge import AirbridgeMmpSource
    try:
        src = AirbridgeMmpSource.from_env()
    except Exception as e:
        print(f"❌ 초기화 실패: {e}")
        return 1
    fields = set(src.fetch_dataspec("fields"))
    metrics = set(src.fetch_dataspec("metrics"))
    if not fields and not metrics:
        print("❌ dataspec 조회 실패 — 토큰/앱이름/네트워크 확인")
        return 1
    print("🔍 Actuals 소재 단위 지원 검증:")
    print(f"   ad_creative (groupBy): {'✅' if 'ad_creative' in fields else '❌ 미지원'}")
    print("   품질지표 메트릭 매핑:")
    ok_all = "ad_creative" in fields
    for quality, mkey in src.metrics_map.items():
        if not mkey:
            print(f"     {quality:12} (생략 설정)")
            continue
        present = mkey in metrics
        print(f"     {quality:12} → {mkey:34} {'✅' if present else '⚠️ 미존재(앱별 custom?) → 0 처리'}")
        if quality in ("cost", "installs", "retained_d1") and not present:
            ok_all = False  # 핵심 지표 부재면 경고
    print("\n" + ("✅ 소재 단위 4지표 산출 가능"
                  if ok_all else "⚠️ 일부 핵심 메트릭/필드 부재 — 가용 지표만으로 분석"))
    return 0


def cmd_fetch(args) -> int:
    from .sources.airbridge import AirbridgeMmpSource
    from .mmp_metrics import aggregate_creative_mmp, compute_mmp_quality

    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=args.days - 1)
    if args.dry_run:
        src = AirbridgeMmpSource(token="(dry)", app_name="(dry)", session=object())
        body = {"from": start.isoformat(), "to": end.isoformat(),
                "groupBys": ["ad_creative", "channel", "event_date"],
                "metrics": src._query_metrics(), "filters": [], "sorts": []}
        print(f"🔍 [DRY-RUN] Actuals 단일 쿼리 ({start} ~ {end}):")
        print(json.dumps(body, ensure_ascii=False, indent=2))
        print("제외 채널:", sorted(_exclude_channels()))
        print("\n✅ 실 호출 안 함.")
        return 0

    try:
        src = AirbridgeMmpSource.from_env()
    except Exception as e:
        print(f"❌ 초기화 실패: {e}")
        return 1
    print(f"🔍 Airbridge fetch — app={src.app_name}, {start} ~ {end} (비-Google 매체)")
    daily = src.fetch_mmp_window(start, end, exclude_channels=_exclude_channels())
    if not daily:
        print("⚠️ 0행. 토큰/앱/기간/채널필터 확인 (pepp 가 非Google 집행 없었을 수 있음).")
        return 0
    agg = aggregate_creative_mmp(daily)
    items = sorted(agg.items(), key=lambda x: -(x[1]["retained_d1"]))
    if args.limit > 0:
        items = items[: args.limit]
    print(f"\n📊 {len(daily)}행, {len(agg)}개 소재")
    print(f"{'소재명':<44}|{'D1잔존':>7}|{'D1IPM':>7}|{'D1CPI':>9}|{'D7ROAS':>7}|{'D1Ret%':>7}")
    print("-" * 90)
    for name, a in items:
        q = compute_mmp_quality(a)
        cpi = f"{q['d1_cpi']:.0f}" if q["d1_cpi"] is not None else "—"
        roas = f"{q['d7_roas']:.2f}" if q["d7_roas"] is not None else "—"
        print(f"{name[:42]:<44}|{a['retained_d1']:>7,}|{q['d1_ipm']:>7.2f}|{cpi:>9}|{roas:>7}|{q['d1_retention']:>7.1f}")
    print("\n✅ 검증 완료. main.py 통합 시 같은 값이 public/data/{title}.json 의 mmp_* 에 주입됩니다.")
    return 0


def main() -> None:
    load_dotenv()
    p = argparse.ArgumentParser(prog="python -m pipeline.mmp", description="Airbridge MMP 검증 CLI (Stage 7)")
    p.add_argument("--healthcheck", action="store_true")
    p.add_argument("--metadata-check", action="store_true")
    p.add_argument("--title", default=None)
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if args.healthcheck:
        sys.exit(cmd_healthcheck())
    if args.metadata_check:
        sys.exit(cmd_metadata_check())
    sys.exit(cmd_fetch(args))


if __name__ == "__main__":
    main()
