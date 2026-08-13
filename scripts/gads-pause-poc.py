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
    """대상 asset의 asset.id 확보 후, 캠페인/광고그룹 레벨 pause 링크 발견.

    GAQL의 OR(특히 '= ... OR ...')은 이 컨텍스트서 거부됨 → 단일 필드 IN 쿼리로 분리.
    IMAGE는 asset.name, VIDEO는 youtube_video_title(확장자 없는 파일명)로 각각 조회.
    """
    result = {"asset_ids": set(), "campaign_asset": [], "ad_group_asset": [],
              "ad_group_ad_asset": [], "view_detail": []}
    # 파일명 확장자 제거본도 후보(VIDEO youtube_video_title = 확장자 없는 파일명)
    import re
    no_ext = re.sub(r"\.(mp4|jpg|jpeg|png|gif)$", "", asset_name, flags=re.I)
    cands = {asset_name, no_ext}
    date_where = f"segments.date BETWEEN '{start}' AND '{end}'"

    for cand in cands:
        c = cand.replace("'", "\\'")
        # IMAGE: asset.name 정확 매칭
        for field in ("asset.name", "asset.youtube_video_asset.youtube_video_title"):
            q = (f"SELECT asset.id, asset.name FROM ad_group_ad_asset_view "
                 f"WHERE {date_where} AND {field} IN ('{c}')")
            try:
                for r in _rows(ga, customer_id, q):
                    result["asset_ids"].add(str(r.asset.id))
            except Exception as e:
                print(f"  [asset_view {field} 조회 오류] {_short(e)}")

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

    # 4) 광고(App Ad) 레벨 링크 — UAC 소재는 여기 붙음(ad_group_ad_asset)
    q_agaa = (
        "SELECT ad_group_ad_asset.resource_name, ad_group_ad_asset.status, "
        "ad_group_ad_asset.field_type FROM ad_group_ad_asset "
        f"WHERE asset.id IN ({ids_csv})"
    )
    try:
        for r in _rows(ga, customer_id, q_agaa):
            result["ad_group_ad_asset"].append({
                "resource_name": r.ad_group_ad_asset.resource_name,
                "status": r.ad_group_ad_asset.status.name,
                "field_type": r.ad_group_ad_asset.field_type.name,
            })
    except Exception as e:
        print(f"  [ad_group_ad_asset 조회 오류/미지원] {_short(e)}")

    # 5) 뷰 상세(참고) — 링크가 mutate 안 되더라도 현재 서빙 링크 상태 확인용
    q_vd = (
        "SELECT ad_group_ad.resource_name, ad_group_ad_asset_view.field_type, "
        "ad_group_ad_asset_view.enabled FROM ad_group_ad_asset_view "
        f"WHERE {date_where} AND asset.id IN ({ids_csv})"
    )
    try:
        seen = set()
        for r in _rows(ga, customer_id, q_vd):
            k = (r.ad_group_ad.resource_name, r.ad_group_ad_asset_view.field_type.name)
            if k in seen:
                continue
            seen.add(k)
            result["view_detail"].append({
                "ad_group_ad": r.ad_group_ad.resource_name,
                "field_type": r.ad_group_ad_asset_view.field_type.name,
                "enabled": bool(r.ad_group_ad_asset_view.enabled),
            })
    except Exception as e:
        print(f"  [ad_group_ad_asset_view 상세 조회 오류] {_short(e)}")

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
    elif level == "adgroup":
        svc = client.get_service("AdGroupAssetService")
        op = client.get_type("AdGroupAssetOperation")
        op.update.resource_name = resource_name
        op.update.status = target
        op.update_mask.paths.append("status")
        resp = svc.mutate_ad_group_assets(customer_id=customer_id, operations=[op])
    else:  # adgroupad (App Ad 레벨)
        svc = client.get_service("AdGroupAdAssetService")
        op = client.get_type("AdGroupAdAssetOperation")
        op.update.resource_name = resource_name
        op.update.status = target
        op.update_mask.paths.append("status")
        resp = svc.mutate_ad_group_ad_assets(customer_id=customer_id, operations=[op])
    return resp.results[0].resource_name


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--asset-name", required=True)
    p.add_argument("--title", default="zeus")
    p.add_argument("--customer-id", default=None)
    p.add_argument("--start", default=str(date.today() - timedelta(days=30)))
    p.add_argument("--end", default=str(date.today()))
    p.add_argument("--link", choices=["campaign", "adgroup", "adgroupad", "both"], default="both")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--resume", action="store_true")
    args = p.parse_args()

    _an = args.asset_name.strip()
    if (not _an) or ("여기에" in _an) or ("실제" in _an) or ("zeus.json" in _an) or _an == "...":
        sys.exit("⚠️ --asset-name 에 실제 소재명을 넣으세요 (public/data/zeus.json 의 파일명/소재명, 예: "
                 "260701_VID_P-Slogan-PreregPV15s-01-PV_L_1920x1080_KR).")

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
    print(f"  광고 레벨(ad_group_ad_asset): {len(d['ad_group_ad_asset'])}건")
    for c in d["ad_group_ad_asset"]:
        print(f"    - {c['resource_name']} [status={c['status']} field={c['field_type']}]")
    print(f"  [참고] 뷰 상세(ad_group_ad_asset_view): {len(d['view_detail'])}건")
    for c in d["view_detail"]:
        print(f"    - {c['ad_group_ad']} field={c['field_type']} enabled={c['enabled']}")

    targets = []
    if args.link in ("campaign", "both"):
        targets += [("campaign", c["resource_name"]) for c in d["campaign_asset"]]
    if args.link in ("adgroup", "both"):
        targets += [("adgroup", c["resource_name"]) for c in d["ad_group_asset"]]
    if args.link in ("adgroupad", "both"):
        targets += [("adgroupad", c["resource_name"]) for c in d["ad_group_ad_asset"]]

    if not targets:
        print("\n❌ pause 대상 링크 못 찾음. 소재명 정확한지(zeus.json 값 그대로)·기간 확인.")
        sys.exit(1)

    action = "ENABLED(재개)" if args.resume else "PAUSED(중단)"
    print(f"\n=== {'실제 실행' if args.apply else 'DRY-RUN'} — {action} 대상 {len(targets)}건 ===")
    if args.apply and args.link == "both":
        sys.exit("⚠️ --apply 시엔 --link campaign|adgroup|adgroupad 로 명시(both는 발견 전용).")
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
        print("\n(변경 없음. 실제 적용은 --link campaign|adgroup|adgroupad + --apply. 되돌리기는 --resume 추가.)")


if __name__ == "__main__":
    main()
