"""
[Phase 0 PoC] Google Ads UAC 소재(asset) pause 실현가능성 검증.

스펙: docs 플랜 "Google Ads 저효율 소재 자동 제외(pause)" — P0-1(식별자) + P0-3(실제 pause) 검증용.
전 캠페인이 UAC(App Campaign)라 개별 '광고'가 아니라 asset 단위 링크(status)를 pause 해야 함.
이 스크립트는 (1) 대상 asset의 pause 가능한 링크 리소스를 '발견'하고, (2) 기본은 dry-run(출력만),
--apply 명시 시에만 실제 mutate 한다.

⚠️ --apply 는 라이브 광고 소재를 실제로 중단한다(비용·노출 영향). 반드시 담당자가 승인·실행할 것.
   기본(dry-run)은 아무것도 바꾸지 않는다.

사용법:
    cd C:\\claude\\cloop_dashboard
    # 1) 발견만 (안전, 아무것도 안 바꿈)
    .\\.venv\\Scripts\\python.exe scripts\\gads-pause-poc.py --title zeus \\
        --asset-name "260701_VID_..._KR" --start 2026-07-01 --end 2026-08-08

    # 2) 실제 pause (담당자 승인 후)
    .\\.venv\\Scripts\\python.exe scripts\\gads-pause-poc.py --title zeus \\
        --asset-name "..." --link campaign --apply

    # 3) 되돌리기(재개)
    .\\.venv\\Scripts\\python.exe scripts\\gads-pause-poc.py --title zeus \\
        --asset-name "..." --link campaign --apply --resume

옵션:
    --asset-name   대상 소재 asset 이름(필수). VIDEO는 youtube_video_title.
    --title        titles.json id (customer_id 조회). 기본 zeus.
    --customer-id  직접 지정 시.
    --start/--end  발견용 asset_view 조회 기간(YYYY-MM-DD). 기본 최근 30일.
    --link         pause 대상 링크 레벨: campaign | ad | both(기본, 발견만).
    --apply        실제 mutate 실행(미지정=dry-run).
    --resume       status를 ENABLED로(되돌리기). 미지정=PAUSED.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from google.ads.googleads.client import GoogleAdsClient


def _customer_id(title_id: str, override: str | None) -> str:
    if override:
        return override.replace("-", "").strip()
    titles = json.loads(Path("js/titles.json").read_text(encoding="utf-8"))
    m = next((t for t in titles if t.get("id") == title_id), None)
    if not m:
        sys.exit(f"titles.json 에 title='{title_id}' 없음")
    cid = (m.get("_pipeline_google_ads_customer_id") or "").replace("-", "").strip()
    if not cid:
        sys.exit(f"'{title_id}' 의 _pipeline_google_ads_customer_id 비어있음")
    return cid


def _esc(s: str) -> str:
    return s.replace("'", "\\'")


def discover_links(ga, customer_id: str, asset_name: str, start: str, end: str) -> dict:
    """대상 asset의 pause 가능한 링크(캠페인/광고 레벨) 발견. 리소스명·현재 status 반환."""
    name = _esc(asset_name)
    found = {"campaign_asset": [], "ad_group_ad_asset": [], "asset_ids": set()}

    # asset.id 먼저 확보 (이름 → id). VIDEO는 youtube_video_title로도 매칭.
    q_asset = (
        f"SELECT asset.id, asset.name, asset.type FROM asset "
        f"WHERE asset.name = '{name}' "
        f"OR asset.youtube_video_asset.youtube_video_title = '{name}'"
    )
    try:
        for b in ga.search_stream(customer_id=customer_id, query=q_asset):
            for r in b.results:
                found["asset_ids"].add(str(r.asset.id))
    except Exception as e:
        print(f"  [asset 조회 오류] {e}")

    # 1) CAMPAIGN 레벨 링크 (App 캠페인은 보통 여기) — 직접 mutate 가능(CampaignAssetService)
    q_ca = (
        "SELECT campaign_asset.resource_name, campaign_asset.status, "
        "campaign_asset.field_type, campaign.name, asset.name, asset.id "
        "FROM campaign_asset "
        f"WHERE asset.name = '{name}' "
        f"OR asset.youtube_video_asset.youtube_video_title = '{name}'"
    )
    try:
        for b in ga.search_stream(customer_id=customer_id, query=q_ca):
            for r in b.results:
                found["campaign_asset"].append({
                    "resource_name": r.campaign_asset.resource_name,
                    "status": r.campaign_asset.status.name,
                    "field_type": r.campaign_asset.field_type.name,
                    "campaign": r.campaign.name,
                    "asset": r.asset.name,
                })
    except Exception as e:
        print(f"  [campaign_asset 조회 오류/미지원] {e}")

    # 2) AD 레벨 링크 — ad_group_ad_asset_view 로 (ad_group_ad, asset, field_type) 확인 후
    #    AdGroupAdAsset 리소스명 구성: customers/{cid}/adGroupAdAssets/{adGroupAdId}~{assetId}~{fieldType}
    q_view = (
        "SELECT ad_group_ad.ad.id, ad_group_ad.resource_name, asset.id, asset.name, "
        "ad_group_ad_asset_view.field_type, ad_group_ad_asset_view.enabled "
        "FROM ad_group_ad_asset_view "
        f"WHERE segments.date BETWEEN '{start}' AND '{end}' "
        f"AND (asset.name = '{name}' OR asset.youtube_video_asset.youtube_video_title = '{name}')"
    )
    try:
        seen = set()
        for b in ga.search_stream(customer_id=customer_id, query=q_view):
            for r in b.results:
                ad_id = str(r.ad_group_ad.ad.id)
                # ad_group_ad.resource_name = customers/{cid}/adGroupAds/{adGroupId}~{adId}
                agad = r.ad_group_ad.resource_name
                ag_part = agad.split("/adGroupAds/")[-1] if "/adGroupAds/" in agad else ""
                ft = r.ad_group_ad_asset_view.field_type.name
                asset_id = str(r.asset.id)
                res = f"customers/{customer_id}/adGroupAdAssets/{ag_part}~{asset_id}~{ft}"
                key = res
                if key in seen:
                    continue
                seen.add(key)
                found["ad_group_ad_asset"].append({
                    "resource_name": res,
                    "field_type": ft,
                    "enabled": bool(r.ad_group_ad_asset_view.enabled),
                    "asset": r.asset.name,
                })
    except Exception as e:
        print(f"  [ad_group_ad_asset_view 조회 오류] {e}")

    return found


def do_mutate(client, ga_customer_id: str, level: str, resource_name: str, resume: bool) -> str:
    """링크 status를 PAUSED(또는 resume 시 ENABLED)로 mutate. 실제 API 변경 발생."""
    status_enum = client.enums.AssetLinkStatusEnum
    target = status_enum.ENABLED if resume else status_enum.PAUSED
    if level == "campaign":
        svc = client.get_service("CampaignAssetService")
        op = client.get_type("CampaignAssetOperation")
        op.update.resource_name = resource_name
        op.update.status = target
        op.update_mask.paths.append("status")
        resp = svc.mutate_campaign_assets(customer_id=ga_customer_id, operations=[op])
    elif level == "ad":
        svc = client.get_service("AdGroupAdAssetService")
        op = client.get_type("AdGroupAdAssetOperation")
        op.update.resource_name = resource_name
        op.update.status = target
        op.update_mask.paths.append("status")
        resp = svc.mutate_ad_group_ad_assets(customer_id=ga_customer_id, operations=[op])
    else:
        sys.exit(f"--link 는 campaign 또는 ad 여야 mutate 가능 (현재 {level})")
    return resp.results[0].resource_name


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--asset-name", required=True)
    p.add_argument("--title", default="zeus")
    p.add_argument("--customer-id", default=None)
    p.add_argument("--start", default=str(date.today() - timedelta(days=30)))
    p.add_argument("--end", default=str(date.today()))
    p.add_argument("--link", choices=["campaign", "ad", "both"], default="both")
    p.add_argument("--apply", action="store_true", help="실제 mutate 실행(미지정=dry-run)")
    p.add_argument("--resume", action="store_true", help="ENABLED로 되돌리기")
    args = p.parse_args()

    cid = _customer_id(args.title, args.customer_id)
    client = GoogleAdsClient.load_from_storage(".secrets/google_ads.yaml")
    ga = client.get_service("GoogleAdsService")

    print(f"\n[Phase 0 PoC] customer_id={cid} · asset={args.asset_name!r}")
    print(f"  기간(발견용)={args.start}~{args.end} · link={args.link} · "
          f"{'APPLY(실제 변경)' if args.apply else 'DRY-RUN(변경 없음)'}"
          f"{' · RESUME(ENABLED)' if args.resume else ''}")

    print("\n=== 링크 발견 ===")
    found = discover_links(ga, cid, args.asset_name, args.start, args.end)
    print(f"  asset id: {sorted(found['asset_ids']) or '(없음)'}")
    print(f"  캠페인 레벨 링크(campaign_asset): {len(found['campaign_asset'])}건")
    for c in found["campaign_asset"]:
        print(f"    - {c['resource_name']} [status={c['status']} field={c['field_type']} camp={c['campaign']}]")
    print(f"  광고 레벨 링크(ad_group_ad_asset): {len(found['ad_group_ad_asset'])}건")
    for c in found["ad_group_ad_asset"]:
        print(f"    - {c['resource_name']} [field={c['field_type']} enabled={c['enabled']}]")

    # 대상 링크 선정
    targets = []
    if args.link in ("campaign", "both"):
        targets += [("campaign", c["resource_name"]) for c in found["campaign_asset"]]
    if args.link in ("ad", "both"):
        targets += [("ad", c["resource_name"]) for c in found["ad_group_ad_asset"]]

    if not targets:
        print("\n❌ pause 대상 링크를 못 찾음. asset 이름/기간/링크 레벨 확인 필요.")
        sys.exit(1)

    action = "ENABLED(재개)" if args.resume else "PAUSED(중단)"
    print(f"\n=== {'실제 실행' if args.apply else 'DRY-RUN'} — {action} 대상 {len(targets)}건 ===")
    for level, res in targets:
        if not args.apply:
            print(f"  [dry-run] {level:8s} {res} → {action} (변경 안 함)")
            continue
        if args.link == "both":
            sys.exit("⚠️ --apply 시엔 --link campaign 또는 ad 로 명시하세요(both는 발견 전용).")
        try:
            done = do_mutate(client, cid, level, res, args.resume)
            print(f"  ✅ {level} {done} → {action}")
        except Exception as e:
            print(f"  ❌ {level} {res} 실패: {e}")

    if not args.apply:
        print("\n(변경 없음. 실제 적용은 --link campaign|ad + --apply. 되돌리기는 --resume 추가.)")


if __name__ == "__main__":
    main()
