"""
[Phase 0 PoC] Google Ads UAC 소재(asset) pause 실현가능성 검증.

스펙: 플랜 "Google Ads 저효율 소재 자동 제외(pause)" — P0-1(식별자) + P0-3(실제 pause) 검증용.
전 캠페인이 UAC(App Campaign)라 개별 '광고'가 아니라 asset 링크(status)를 pause 해야 함.
링크는 캠페인 레벨(campaign_asset) 또는 광고그룹 레벨(ad_group_asset)에 존재 — 어느 레벨인지
'발견'으로 확인하고, 기본은 dry-run(출력만), --apply 명시 시에만 실제 mutate 한다.

⚠️ --apply 는 라이브 광고 소재를 실제 중단(비용·노출 영향). 반드시 담당자가 승인·실행. 기본(dry-run)은 무변경.

사용법:
    cd C:\\claude\\cloop_dashboard
    # 0) 소재명 확인: public/data/zeus.json 의 creative "소재명" 또는 "파일명" 값을 그대로 사용
    # 1) 발견만 (안전, 무변경)
    .\\.venv\\Scripts\\python.exe scripts\\gads-pause-poc.py --title zeus ^
        --asset-name "260701_VID_실제파일명_KR" --start 2026-07-01 --end 2026-08-08
    # 2) 실제 pause (담당자 승인 후) — 발견에서 나온 레벨로
    .\\.venv\\Scripts\\python.exe scripts\\gads-pause-poc.py --title zeus --asset-name "..." --link campaign --apply
    # 3) 되돌리기(재개)
    .\\.venv\\Scripts\\python.exe scripts\\gads-pause-poc.py --title zeus --asset-name "..." --link campaign --apply --resume

옵션:
    --asset-name   대상 소재 asset 이름(필수, 실제값). VIDEO는 youtube_video_title 형식.
    --title        titles.json id (customer_id 조회). 기본 zeus.
    --customer-id  직접 지정 시.
    --start/--end  발견용 asset_view 조회 기간(YYYY-MM-DD). 기본 최근 30일.
    --link         pause 대상 링크 레벨: campaign | adgroup | both(기본, 발견 전용).
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


def _rows(ga, customer_id: str, query: str):
    out = []
    for b in ga.search_stream(customer_id=customer_id, query=query):
        out.extend(b.results)
    return out


def discover(ga, customer_id: str, asset_name: str, start: str, end: str) -> dict:
    """대상 asset의 asset.id 확보 후, 캠페인/광고그룹 레벨 pause 링크 발견."""
    name = asset_name.replace("'", "\\'")
    result = {"asset_ids": set(), "campaign_asset": [], "ad_group_asset": []}

    # 1) asset.id — 커넥터가 검증한 IN(...)+괄호 패턴(= ... OR 은 GAQL 미지원). VIDEO는 title로도 매칭.
    q_view = (
        "SELECT asset.id, asset.name, ad_group_ad_asset_view.enabled, campaign.name "
        "FROM ad_group_ad_asset_view "
        f"WHERE segments.date BETWEEN '{start}' AND '{end}' "
        f"AND (asset.name IN ('{name}') OR asset.youtube_video_asset.youtube_video_title IN ('{name}'))"
    )
    try:
        for r in _rows(ga, customer_id, q_view):
            result["asset_ids"].add(str(r.asset.id))
    except Exception as e:
        print(f"  [asset_view 조회 오류] {_short(e)}")

    if not result["asset_ids"]:
        return result
    ids_csv = ", ".join(sorted(result["asset_ids"]))

    # 2) 캠페인 레벨 링크 — asset.id(숫자) 필터라 OR 불필요. status/field_type/resource_name.
    q_ca = (
        "SELECT campaign_asset.resource_name, campaign_asset.status, "
        "campaign_asset.field_type, campaign.name FROM campaign_asset "
        f"WHERE asset.id IN ({ids_csv})"
    )
    try:
        for r in _rows(ga, customer_id, q_ca):
            result["campaign_asset"].append({
                "resource_name": r.campaign_asset.resource_name,
                "status": r.campaign_asset.status.name,
                "field_type": r.campaign_asset.field_type.name,
                "campaign": r.campaign.name,
            })
    except Exception as e:
        print(f"  [campaign_asset 조회 오류] {_short(e)}")

    # 3) 광고그룹 레벨 링크
    q_aga = (
        "SELECT ad_group_asset.resource_name, ad_group_asset.status, "
        "ad_group_asset.field_type, ad_group.name FROM ad_group_asset "
        f"WHERE asset.id IN ({ids_csv})"
    )
    try:
        for r in _rows(ga, customer_id, q_aga):
            result["ad_group_asset"].append({
                "resource_name": r.ad_group_asset.resource_name,
                "status": r.ad_group_asset.status.name,
                "field_type": r.ad_group_asset.field_type.name,
                "ad_group": r.ad_group.name,
            })
    except Exception as e:
        print(f"  [ad_group_asset 조회 오류] {_short(e)}")

    return result


def _short(e) -> str:
    s = str(e)
    return s[:300] + (" ...(생략)" if len(s) > 300 else "")


def do_mutate(client, customer_id: str, level: str, resource_name: str, resume: bool) -> str:
    status_enum = client.enums.AssetLinkStatusEnum
    target = status_enum.ENABLED if resume else status_enum.PAUSED
    if level == "campaign":
        svc = client.get_service("CampaignAssetService")
        op = client.get_type("CampaignAssetOperation")
        op.update.resource_name = resource_name
        op.update.status = target
        op.update_mask.paths.append("status")
        resp = svc.mutate_campaign_assets(customer_id=customer_id, operations=[op])
    else:  # adgroup
        svc = client.get_service("AdGroupAssetService")
        op = client.get_type("AdGroupAssetOperation")
        op.update.resource_name = resource_name
        op.update.status = target
        op.update_mask.paths.append("status")
        resp = svc.mutate_ad_group_assets(customer_id=customer_id, operations=[op])
    return resp.results[0].resource_name


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--asset-name", required=True)
    p.add_argument("--title", default="zeus")
    p.add_argument("--customer-id", default=None)
    p.add_argument("--start", default=str(date.today() - timedelta(days=30)))
    p.add_argument("--end", default=str(date.today()))
    p.add_argument("--link", choices=["campaign", "adgroup", "both"], default="both")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--resume", action="store_true")
    args = p.parse_args()

    if args.asset_name.strip() in ("", "실제_소재이름", "실제파일명", "..."):
        sys.exit("⚠️ --asset-name 에 실제 소재명을 넣으세요 (public/data/zeus.json 의 소재명/파일명).")

    cid = _customer_id(args.title, args.customer_id)
    client = GoogleAdsClient.load_from_storage(".secrets/google_ads.yaml")
    ga = client.get_service("GoogleAdsService")

    print(f"\n[Phase 0 PoC] customer_id={cid} · asset={args.asset_name!r}")
    print(f"  기간(발견용)={args.start}~{args.end} · link={args.link} · "
          f"{'APPLY(실제 변경)' if args.apply else 'DRY-RUN(변경 없음)'}"
          f"{' · RESUME(ENABLED)' if args.resume else ''}")

    print("\n=== 링크 발견 ===")
    d = discover(ga, cid, args.asset_name, args.start, args.end)
    print(f"  asset id: {sorted(d['asset_ids']) or '(없음 — 소재명/기간 확인)'}")
    print(f"  캠페인 레벨(campaign_asset): {len(d['campaign_asset'])}건")
    for c in d["campaign_asset"]:
        print(f"    - {c['resource_name']} [status={c['status']} field={c['field_type']} camp={c['campaign']}]")
    print(f"  광고그룹 레벨(ad_group_asset): {len(d['ad_group_asset'])}건")
    for c in d["ad_group_asset"]:
        print(f"    - {c['resource_name']} [status={c['status']} field={c['field_type']} ag={c['ad_group']}]")

    targets = []
    if args.link in ("campaign", "both"):
        targets += [("campaign", c["resource_name"]) for c in d["campaign_asset"]]
    if args.link in ("adgroup", "both"):
        targets += [("adgroup", c["resource_name"]) for c in d["ad_group_asset"]]

    if not targets:
        print("\n❌ pause 대상 링크 못 찾음. 소재명 정확한지(zeus.json 값 그대로)·기간 확인.")
        sys.exit(1)

    action = "ENABLED(재개)" if args.resume else "PAUSED(중단)"
    print(f"\n=== {'실제 실행' if args.apply else 'DRY-RUN'} — {action} 대상 {len(targets)}건 ===")
    if args.apply and args.link == "both":
        sys.exit("⚠️ --apply 시엔 --link campaign 또는 adgroup 로 명시(both는 발견 전용).")
    for level, res in targets:
        if not args.apply:
            print(f"  [dry-run] {level:8s} {res} → {action} (변경 안 함)")
            continue
        try:
            done = do_mutate(client, cid, level, res, args.resume)
            print(f"  ✅ {level} {done} → {action}")
        except Exception as e:
            print(f"  ❌ {level} {res} 실패: {_short(e)}")

    if not args.apply:
        print("\n(변경 없음. 실제 적용은 --link campaign|adgroup + --apply. 되돌리기는 --resume 추가.)")


if __name__ == "__main__":
    main()
