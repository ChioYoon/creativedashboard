"""
Asset Performance UI ↔ CLI 노출수 불일치 1:1 진단 (Stage 5-B 보강).

사용법:
    cd C:\\claude\\cloop_dashboard
    .\\.venv\\Scripts\\python.exe scripts\\diagnose-asset-mismatch.py \\
        --asset-name "251104_BNR_A-Character-Adventure01A-DA_L_1200x628_EN.jpg" \\
        --start 2026-04-01 --end 2026-04-30

옵션:
    --asset-name      UI에서 확인한 정확한 asset 이름 (필수)
    --start --end     UI 보고서와 동일한 날짜 범위 (YYYY-MM-DD)
    --campaign-name   특정 캠페인만 (UI를 캠페인 단위로 보셨다면 입력)
    --customer-id     기본은 titles.json pepp-us, 변경 시 명시

출력:
    Layer 1: 같은 asset name 으로 검색된 모든 (campaign, ad_group, asset_id) 행
    Layer 2: 합계 (CLI 가 반환하는 값)
    Layer 3: 같은 asset 의 ad_group_ad metric (단일 캠페인 한정 시)
    Layer 4: 진단 결론
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from google.ads.googleads.client import GoogleAdsClient


def load_customer_id_from_titles(title_id: str = "pepp-us") -> str:
    titles = json.loads(Path("js/titles.json").read_text(encoding="utf-8"))
    matched = next((t for t in titles if t.get("id") == title_id), None)
    if not matched:
        sys.exit(f"titles.json 에 title='{title_id}' 없음")
    cid = matched.get("_pipeline_google_ads_customer_id", "")
    if not cid:
        sys.exit(f"'{title_id}' 의 _pipeline_google_ads_customer_id 가 비어있음")
    return cid


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--asset-name", required=True, help="UI에서 본 정확한 asset 이름")
    p.add_argument("--start", required=True, help="YYYY-MM-DD")
    p.add_argument("--end", required=True, help="YYYY-MM-DD")
    p.add_argument("--campaign-name", default=None, help="단일 캠페인 한정 시")
    p.add_argument("--customer-id", default=None)
    args = p.parse_args()

    customer_id = args.customer_id or load_customer_id_from_titles()
    customer_id = customer_id.replace("-", "").strip()

    client = GoogleAdsClient.load_from_storage(".secrets/google_ads.yaml")
    ga = client.get_service("GoogleAdsService")

    # 작은따옴표 이스케이프
    asset_name_esc = args.asset_name.replace("'", "\\'")
    base_where = (
        f"segments.date BETWEEN '{args.start}' AND '{args.end}' "
        f"AND ad_group_ad.status != 'REMOVED' "
        f"AND asset.name = '{asset_name_esc}'"
    )
    if args.campaign_name:
        camp_esc = args.campaign_name.replace("'", "\\'")
        base_where += f" AND campaign.name = '{camp_esc}'"

    print(f"\n진단 대상")
    print(f"  customer_id : {customer_id}")
    print(f"  asset_name  : {args.asset_name!r}")
    print(f"  기간       : {args.start} ~ {args.end}")
    print(f"  캠페인 필터 : {args.campaign_name or '(전체)'}")

    # ── Layer 1: asset_view 모든 행 (campaign × ad_group × ad_id × date) ──
    print(f"\n=== Layer 1: ad_group_ad_asset_view 행 (CLI가 보는 모든 행) ===")
    q1 = f"""
        SELECT segments.date, campaign.name, ad_group.id, ad_group.name,
               ad_group_ad.ad.id, asset.id, asset.type,
               metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions
        FROM ad_group_ad_asset_view
        WHERE {base_where}
        ORDER BY segments.date DESC, campaign.name
    """
    rows = []
    for batch in ga.search_stream(customer_id=customer_id, query=q1):
        rows.extend(batch.results)

    print(f"  총 행: {len(rows)}")
    by_campaign = defaultdict(lambda: [0, 0, 0, 0.0])  # imp, clk, cost, conv
    by_ad_group = defaultdict(lambda: [0, 0, 0, 0.0])
    asset_ids = set()
    for r in rows:
        c = r.campaign.name
        g = (c, r.ad_group.name)
        by_campaign[c][0] += r.metrics.impressions
        by_campaign[c][1] += r.metrics.clicks
        by_campaign[c][2] += r.metrics.cost_micros
        by_campaign[c][3] += r.metrics.conversions
        by_ad_group[g][0] += r.metrics.impressions
        by_ad_group[g][1] += r.metrics.clicks
        by_ad_group[g][2] += r.metrics.cost_micros
        by_ad_group[g][3] += r.metrics.conversions
        asset_ids.add(r.asset.id)

    print(f"\n  같은 asset.name 으로 잡힌 asset.id 개수: {len(asset_ids)}")
    if len(asset_ids) > 1:
        print(f"  >>> 주의: 같은 이름의 asset이 여러 ID로 등록되어 있습니다 ({list(asset_ids)[:5]}{'...' if len(asset_ids)>5 else ''})")
        print(f"           → UI는 asset.id 단위로 분리 표시, CLI는 이름 단위로 합산 — 차이의 가능성")

    # ── Layer 2: 캠페인별 합 ──
    print(f"\n=== Layer 2: 캠페인별 합 ({len(by_campaign)}개 캠페인에 등장) ===")
    print(f"  {'캠페인':<55} | {'노출':>10} | {'클릭':>6} | {'비용(KRW)':>12} | {'전환':>6}")
    print("  " + "-" * 100)
    for c, (i, k, co, cv) in sorted(by_campaign.items(), key=lambda x: -x[1][0]):
        print(f"  {c[:53]:<55} | {i:>10,} | {k:>6,} | {co/1_000_000:>12,.0f} | {cv:>6.1f}")
    total_imp = sum(v[0] for v in by_campaign.values())
    total_clk = sum(v[1] for v in by_campaign.values())
    total_cost = sum(v[2] for v in by_campaign.values()) / 1_000_000
    total_conv = sum(v[3] for v in by_campaign.values())
    print("  " + "-" * 100)
    print(f"  {'CLI 가 반환하는 합 (across all campaigns)':<55} | {total_imp:>10,} | {total_clk:>6,} | {total_cost:>12,.0f} | {total_conv:>6.1f}")

    # ── Layer 3: ad_group 별 ──
    if len(by_campaign) <= 3:
        print(f"\n=== Layer 3: ad_group 별 (UI Asset Performance 가 ad_group 단위면 비교 가능) ===")
        for (c, g), (i, k, co, cv) in sorted(by_ad_group.items(), key=lambda x: -x[1][0]):
            print(f"  [{c[:30]:<30}] {g[:30]:<30} | imp={i:>8,}  clk={k:>5,}  cost={co/1_000_000:>10,.0f}  conv={cv:>5.1f}")

    # ── Layer 4: 진단 결론 ──
    print(f"\n=== Layer 4: 진단 결론 ===")
    print(f"  UI에서 보신 노출수를 어디서 보셨는지에 따라 해석이 달라집니다:\n")

    if len(asset_ids) > 1:
        print(f"  [가설 A] 같은 이름의 asset이 {len(asset_ids)}개 다른 ID로 등록되어 있음.")
        print(f"           UI Asset Performance가 asset.id 단위 표시라면, UI는 1개 ID 값만 보이고")
        print(f"           CLI는 모든 ID 합산. → 정상 동작, 데이터 의미 명확화 필요.")
        print()

    if len(by_campaign) > 1:
        print(f"  [가설 B] 이 asset은 {len(by_campaign)}개 캠페인에서 사용 중.")
        print(f"           UI에서 특정 캠페인 1개만 보셨다면, CLI 전체 합과 다른 게 정상.")
        print(f"           → --campaign-name 옵션으로 좁혀서 재실행 → UI 값과 비교")
        print()

    if not args.campaign_name and len(by_campaign) == 1:
        only_camp = list(by_campaign.keys())[0]
        print(f"  [가설 C] 이 asset은 캠페인 1개 ({only_camp[:50]!r}) 에서만 사용 중.")
        print(f"           CLI vs UI 차이가 있다면 기간/필터 조건이 다를 가능성. UI 보고서의 ")
        print(f"           시작일/종료일/필터 적용 여부 재확인 필요.")

    print()


if __name__ == "__main__":
    main()
