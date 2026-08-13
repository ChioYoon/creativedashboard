"""
[Phase 0-A PoC] Google Ads App(UAC) 캠페인 소재 '제거' 실현가능성 검증.

배경: App 캠페인은 소재를 개별 pause 할 링크가 없고(campaign/ad_group/ad_group_ad_asset 전무),
소재가 App Ad(ad_group_ad.ad.app_ad) 안에 임베드됨. 서빙을 멈추려면 그 소재를 App Ad의
asset 리스트(youtube_videos 등)에서 '제거'해야 함. 이 스크립트는 1개 광고를 대상으로
제거(및 복원)가 API로 실제 되는지 검증한다.

⚠️⚠️ --apply 는 라이브 App Ad에서 소재를 실제 제거(서빙 중단, 되돌리려면 재추가).
      App 캠페인 최소 소재 개수 미달이면 API가 거부할 수 있음(그 자체가 P0 답).
      반드시 담당자 승인 후, 먼저 1개 광고로만 테스트. 기본(dry-run)은 무변경.

사용법:
    cd C:\\claude\\cloop_dashboard
    # 1) 발견 — 대상 소재가 붙은 광고 + 각 광고의 현재 영상 asset 목록 (안전, 무변경)
    .\\.venv\\Scripts\\python.exe scripts\\gads-remove-asset-poc.py --title zeus ^
        --asset-name "260701_VID_P-Slogan-PreregPV15s-01-PV_L_1920x1080_KR" --start 2026-07-01 --end 2026-08-08
    # 2) 1개 광고에서 실제 제거 (담당자 승인 후) — --ad 로 대상 광고 지정
    .\\.venv\\Scripts\\python.exe scripts\\gads-remove-asset-poc.py --title zeus --asset-name "..." ^
        --ad "customers/3250895166/adGroupAds/194909611141~814717408024" --apply
    # 3) 복원(재추가)
    .\\.venv\\Scripts\\python.exe scripts\\gads-remove-asset-poc.py --title zeus --asset-name "..." ^
        --ad "customers/.../adGroupAds/..." --apply --resume

옵션:
    --asset-name  대상(제거할) 소재 이름(필수).
    --ad          작업 대상 ad_group_ad resource_name(제거/복원 시 필수, 1개). 미지정=발견만.
    --field-type  asset field type. 기본 YOUTUBE_VIDEO.
    --apply       실제 mutate(미지정=dry-run).
    --resume      제거가 아니라 재추가(복원).
    --title/--customer-id/--start/--end  발견 파라미터.
"""
from __future__ import annotations

import argparse
import json
import re
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


def _rows(ga, cid, q):
    out = []
    for b in ga.search_stream(customer_id=cid, query=q):
        out.extend(b.results)
    return out


def _short(e):
    s = str(e)
    return s[:400] + (" ...(생략)" if len(s) > 400 else "")


def find_asset_ids(ga, cid, asset_name, start, end):
    ids = set()
    no_ext = re.sub(r"\.(mp4|jpg|jpeg|png|gif)$", "", asset_name, flags=re.I)
    for cand in {asset_name, no_ext}:
        c = cand.replace("'", "\\'")
        for field in ("asset.name", "asset.youtube_video_asset.youtube_video_title"):
            q = (f"SELECT asset.id FROM ad_group_ad_asset_view "
                 f"WHERE segments.date BETWEEN '{start}' AND '{end}' AND {field} IN ('{c}')")
            try:
                for r in _rows(ga, cid, q):
                    ids.add(str(r.asset.id))
            except Exception as e:
                print(f"  [asset_id {field} 오류] {_short(e)}")
    return ids


def ad_videos(ga, cid, ad_resource, field_type, start, end):
    """해당 광고의 현재 field_type asset id 목록 (제거 후 재구성용)."""
    ft = field_type.replace("'", "\\'")
    ar = ad_resource.replace("'", "\\'")
    q = (f"SELECT asset.id FROM ad_group_ad_asset_view "
         f"WHERE segments.date BETWEEN '{start}' AND '{end}' "
         f"AND ad_group_ad.resource_name = '{ar}' "
         f"AND ad_group_ad_asset_view.field_type = '{ft}'")
    ids = []
    for r in _rows(ga, cid, q):
        ids.append(str(r.asset.id))
    return ids


def ad_id_from_agad(ad_group_ad_resource: str) -> str:
    # customers/{cid}/adGroupAds/{adGroupId}~{adId} → {adId}
    tail = ad_group_ad_resource.split("/adGroupAds/")[-1]
    return tail.split("~")[-1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--asset-name", required=True)
    p.add_argument("--ad", default=None, help="대상 ad_group_ad resource_name(제거/복원 시 필수)")
    p.add_argument("--field-type", default="YOUTUBE_VIDEO")
    p.add_argument("--title", default="zeus")
    p.add_argument("--customer-id", default=None)
    p.add_argument("--start", default=str(date.today() - timedelta(days=30)))
    p.add_argument("--end", default=str(date.today()))
    p.add_argument("--apply", action="store_true")
    p.add_argument("--resume", action="store_true")
    args = p.parse_args()

    an = args.asset_name.strip()
    if (not an) or ("여기에" in an) or ("실제" in an) or ("zeus.json" in an) or an == "...":
        sys.exit("⚠️ --asset-name 에 실제 소재명을 넣으세요.")

    cid = _customer_id(args.title, args.customer_id)
    client = GoogleAdsClient.load_from_storage(".secrets/google_ads.yaml")
    ga = client.get_service("GoogleAdsService")

    print(f"\n[Phase 0-A PoC] customer_id={cid} · asset={an!r} · field={args.field_type}")
    print(f"  {'APPLY(실제 변경)' if args.apply else 'DRY-RUN(변경 없음)'}"
          f"{' · RESUME(재추가)' if args.resume else ' · REMOVE(제거)'}")

    target_ids = find_asset_ids(ga, cid, an, args.start, args.end)
    if not target_ids:
        sys.exit("❌ 대상 asset id 못 찾음. 소재명/기간 확인.")
    target_ids = set(target_ids)
    print(f"  대상 asset id: {sorted(target_ids)}")

    # 발견: 이 소재가 붙은 광고들
    ids_csv = ", ".join(sorted(target_ids))
    q_ads = (f"SELECT ad_group_ad.resource_name FROM ad_group_ad_asset_view "
             f"WHERE segments.date BETWEEN '{args.start}' AND '{args.end}' "
             f"AND asset.id IN ({ids_csv}) "
             f"AND ad_group_ad_asset_view.field_type = '{args.field_type}'")
    ads = sorted({r.ad_group_ad.resource_name for r in _rows(ga, cid, q_ads)})
    print(f"\n  이 소재가 붙은 광고(ad_group_ad): {len(ads)}건")
    for a in ads:
        print(f"    - {a}")

    if not args.ad:
        print("\n(발견만 완료. 실제 제거는 --ad <광고 하나> + --apply. 위 목록에서 1개 골라 테스트.)")
        print("  주의: 한 소재가 여러 광고에 붙음 → 완전 중단하려면 각 광고에서 제거해야 함.")
        return

    if args.ad not in ads:
        print(f"\n⚠️ --ad 가 발견 목록에 없음: {args.ad}")

    # 대상 광고의 현재 영상 목록 → 대상 제거(또는 복원) 후 새 목록 구성
    current = ad_videos(ga, cid, args.ad, args.field_type, args.start, args.end)
    print(f"\n  대상 광고 현재 {args.field_type} asset: {current}")
    ad_res = f"customers/{cid}/ads/{ad_id_from_agad(args.ad)}"

    if args.resume:
        new_ids = sorted(set(current) | target_ids)
        act = "재추가"
    else:
        new_ids = sorted(set(current) - target_ids)
        act = "제거"
    print(f"  → {act} 후 목록: {new_ids}")

    if not args.resume and len(new_ids) == len(current):
        print("  (대상이 이미 이 광고에 없음 — 변경 불필요)")
        return
    if not args.resume and not new_ids:
        print("  ⚠️ 제거 후 영상 0개 — App 캠페인 최소개수 위반 가능(API가 거부할 수 있음).")

    if not args.apply:
        print(f"\n[dry-run] AdService.mutate_ads 로 {ad_res} 의 app_ad.youtube_videos 를 위 목록으로 설정 예정(변경 안 함).")
        print("(실제 적용: --apply. App 캠페인이 이 업데이트를 허용하는지가 이 PoC의 핵심 답.)")
        return

    # 실제 mutate
    try:
        svc = client.get_service("AdService")
        op = client.get_type("AdOperation")
        ad = op.update
        ad.resource_name = ad_res
        del ad.app_ad.youtube_videos[:]
        for aid in new_ids:
            v = client.get_type("AdVideoAsset")
            v.asset = f"customers/{cid}/assets/{aid}"
            ad.app_ad.youtube_videos.append(v)
        op.update_mask.paths.append("app_ad.youtube_videos")
        resp = svc.mutate_ads(customer_id=cid, operations=[op])
        print(f"\n  ✅ {act} 성공: {resp.results[0].resource_name}")
    except Exception as e:
        print(f"\n  ❌ {act} 실패: {_short(e)}")
        print("  (이 오류가 App 캠페인 asset 제거 제약을 보여줌 — P0-A 판정 근거.)")


if __name__ == "__main__":
    main()
