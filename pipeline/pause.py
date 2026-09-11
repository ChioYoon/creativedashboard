"""
Google Ads 저효율 소재 제외(제거/복원) — 정식 모듈. (스펙: docs/superpowers/specs/2026-08-11-google-ads-pause-design.md)

UAC/Demand Gen 캠페인은 소재를 개별 pause할 링크가 없고 광고에 임베드됨 → 서빙 중단 =
광고의 영상 asset 리스트에서 제거(복원=재추가). AdService.mutate_ads.

핵심:
- 광고 타입별 영상 리스트 필드 상이(TYPE_FIELD).
- 한 소재가 여러 광고·여러 타입에 붙음 → 완전 중단하려면 각 광고에서 제거.
- 최소 개수 가드: 제거 후 영상 0개면 API 거부 → min_keep(기본 1) 미만이면 그 광고는 skip.
- 라이브 영상 목록을 광고 필드 직접 조회로 읽어 재구성(ad_group_ad_asset_view는 날짜필터라 부정확).

⚠️ apply=True 는 라이브 광고를 실제 변경(비용·서빙 영향). 반드시 사람 승인 후. 기본 dry-run.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from google.ads.googleads.client import GoogleAdsClient

# 광고 타입 → (Ad 하위 필드, 영상 리스트 필드).
# Demand Gen: apply 양방향 검증(2026-08-14). APP_PRE_REG: 라이브 읽기 검증(동일). APP_AD: 미검증.
TYPE_FIELD = {
    "APP_AD": ("app_ad", "youtube_videos"),
    "APP_PRE_REGISTRATION_AD": ("app_pre_registration_ad", "youtube_videos"),
    "DEMAND_GEN_VIDEO_RESPONSIVE_AD": ("demand_gen_video_responsive_ad", "videos"),
}
DEFAULT_FIELD_TYPE = "YOUTUBE_VIDEO"


def load_client(config_path: str = ".secrets/google_ads.yaml") -> GoogleAdsClient:
    return GoogleAdsClient.load_from_storage(config_path)


def customer_id_for_title(title_id: str, titles_path: str = "js/titles.json") -> str:
    titles = json.loads(Path(titles_path).read_text(encoding="utf-8"))
    m = next((t for t in titles if t.get("id") == title_id), None)
    if not m:
        raise ValueError(f"titles.json 에 title='{title_id}' 없음")
    cid = (m.get("_pipeline_google_ads_customer_id") or "").replace("-", "").strip()
    if not cid:
        raise ValueError(f"'{title_id}' 의 _pipeline_google_ads_customer_id 비어있음")
    return cid


def _esc(s: str) -> str:
    return s.replace("'", "\\'")


def _rows(ga, cid, q):
    out = []
    for b in ga.search_stream(customer_id=cid, query=q):
        out.extend(b.results)
    return out


def resolve_asset_ids(ga, cid, asset_name: str, start: str, end: str) -> set[str]:
    """소재 이름 → asset id 집합. IMAGE=asset.name, VIDEO=youtube_video_title(확장자 없는 파일명).
    (파이프라인이 creative에 asset_id를 저장하면 이 조회 없이 바로 쓸 수 있음 — Phase 1b.)"""
    import re
    ids: set[str] = set()
    for cand in {asset_name, re.sub(r"\.(mp4|jpg|jpeg|png|gif)$", "", asset_name, flags=re.I)}:
        c = _esc(cand)
        for field in ("asset.name", "asset.youtube_video_asset.youtube_video_title"):
            q = (f"SELECT asset.id FROM ad_group_ad_asset_view "
                 f"WHERE segments.date BETWEEN '{start}' AND '{end}' AND {field} IN ('{c}')")
            try:
                for r in _rows(ga, cid, q):
                    ids.add(str(r.asset.id))
            except Exception:
                pass
    return ids


def find_ads_for_assets(ga, cid, asset_ids: set[str], start: str, end: str,
                        field_type: str = DEFAULT_FIELD_TYPE, campaign_name: Optional[str] = None) -> list[dict]:
    """대상 asset이 붙은 광고(ad_group_ad) 목록 + 타입·캠페인."""
    if not asset_ids:
        return []
    ids_csv = ", ".join(sorted(asset_ids))
    where = (f"segments.date BETWEEN '{start}' AND '{end}' AND asset.id IN ({ids_csv}) "
             f"AND ad_group_ad_asset_view.field_type = '{field_type}'")
    if campaign_name:
        where += f" AND campaign.name = '{_esc(campaign_name)}'"
    q = (f"SELECT ad_group_ad.resource_name, ad_group_ad.ad.type, campaign.name "
         f"FROM ad_group_ad_asset_view WHERE {where}")
    seen, ads = set(), []
    for r in _rows(ga, cid, q):
        res = r.ad_group_ad.resource_name
        if res in seen:
            continue
        seen.add(res)
        ads.append({"ad_group_ad": res, "ad_type": r.ad_group_ad.ad.type_.name, "campaign": r.campaign.name})
    return ads


def live_video_asset_ids(ga, cid, ad_group_ad_resource: str, ad_type: str) -> list[str]:
    """광고의 '라이브' 영상 asset id 목록 — 광고 필드 직접 조회(뷰 아님). 실패 시 [] 반환."""
    if ad_type not in TYPE_FIELD:
        return []
    ad_field, list_field = TYPE_FIELD[ad_type]
    q = (f"SELECT ad_group_ad.ad.{ad_field}.{list_field} FROM ad_group_ad "
         f"WHERE ad_group_ad.resource_name = '{_esc(ad_group_ad_resource)}'")
    rows = _rows(ga, cid, q)
    if not rows:
        return []
    videos = getattr(getattr(rows[0].ad_group_ad.ad, ad_field), list_field)
    return [v.asset.split("/assets/")[-1] for v in videos if v.asset]


def _ad_resource(cid: str, ad_group_ad_resource: str) -> str:
    # customers/{cid}/adGroupAds/{adGroupId}~{adId} → customers/{cid}/ads/{adId}
    return f"customers/{cid}/ads/{ad_group_ad_resource.split('~')[-1]}"


def set_ad_videos(client, cid: str, ad_group_ad_resource: str, ad_type: str, new_asset_ids: list[str]) -> str:
    """광고의 영상 리스트를 new_asset_ids로 설정(실제 변경). resource_name 반환."""
    ad_field, list_field = TYPE_FIELD[ad_type]
    svc = client.get_service("AdService")
    op = client.get_type("AdOperation")
    ad = op.update
    ad.resource_name = _ad_resource(cid, ad_group_ad_resource)
    vids = getattr(getattr(ad, ad_field), list_field)
    del vids[:]
    for aid in new_asset_ids:
        v = client.get_type("AdVideoAsset")
        v.asset = f"customers/{cid}/assets/{aid}"
        vids.append(v)
    op.update_mask.paths.append(f"{ad_field}.{list_field}")
    resp = svc.mutate_ads(customer_id=cid, operations=[op])
    return resp.results[0].resource_name


def plan_change(live, asset_ids, remove: bool = True, min_keep: int = 1):
    """순수 함수 — 라이브 영상 목록 + 대상 asset → (새 목록, skip 사유 or None).

    제거: 대상 빼되, 이미 없으면/최소개수 미만이면 skip. 복원: 대상 추가하되 이미 있으면 skip.
    """
    live = list(live)
    tgt = set(asset_ids)
    if remove:
        new = [a for a in live if a not in tgt]
        if new == live:
            return new, "대상이 이미 없음"
        if len(new) < min_keep:
            return new, f"최소 개수({min_keep}) 미만 — API 거부 방지 skip"
        return new, None
    new = sorted(set(live) | tgt)
    if set(new) == set(live):
        return new, "이미 있음"
    return new, None


def change_asset(client, ga, cid: str, asset_ids: set[str], ads: list[dict], *,
                 remove: bool = True, apply: bool = False, min_keep: int = 1) -> list[dict]:
    """asset_ids를 각 광고에서 제거(remove=True) 또는 재추가(False). dry-run 기본.

    Returns: 광고별 결과 dict 리스트(action/skip/error/before/after).
    """
    results = []
    for ad in ads:
        res, atype = ad["ad_group_ad"], ad["ad_type"]
        row = {"ad_group_ad": res, "ad_type": atype, "campaign": ad.get("campaign", "")}
        if atype not in TYPE_FIELD:
            row.update(status="skip", reason=f"미지원 타입 {atype}")
            results.append(row); continue
        try:
            live = live_video_asset_ids(ga, cid, res, atype)
        except Exception as e:
            row.update(status="error", reason=f"라이브 목록 조회 실패: {e}")
            results.append(row); continue
        new, skip = plan_change(live, asset_ids, remove=remove, min_keep=min_keep)
        row.update(before=live, after=new)
        if skip:
            row.update(status="skip", reason=skip); results.append(row); continue
        if not apply:
            row.update(status="dry-run"); results.append(row); continue
        try:
            done = set_ad_videos(client, cid, res, atype, new)
            row.update(status="applied", result=done)
        except Exception as e:
            row.update(status="error", reason=str(e))
        results.append(row)
    return results


def scan_campaign_ad_types(ga, cid: str, campaign_name: str) -> list[dict]:
    """캠페인의 광고를 타입별 집계 + TYPE_FIELD 커버리지 표시(타입 테스트 준비용).

    ad_group_ad는 config 리소스라 segments.date 불필요. 각 타입이 제거 대상 필드 있는지 반환.
    """
    q = (f"SELECT ad_group_ad.ad.type, ad_group_ad.resource_name FROM ad_group_ad "
         f"WHERE campaign.name = '{_esc(campaign_name)}'")
    counts: dict[str, int] = {}
    sample: dict[str, str] = {}
    for r in _rows(ga, cid, q):
        t = r.ad_group_ad.ad.type_.name
        counts[t] = counts.get(t, 0) + 1
        sample.setdefault(t, r.ad_group_ad.resource_name)
    out = []
    for t, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        out.append({"ad_type": t, "count": n, "supported": t in TYPE_FIELD,
                    "field": ".".join(TYPE_FIELD[t]) if t in TYPE_FIELD else None,
                    "sample_ad": sample[t]})
    return out


def _cli():
    p = argparse.ArgumentParser(description="Google Ads 저효율 소재 제외(제거/복원)")
    p.add_argument("--title", default="zeus")
    p.add_argument("--asset-name", help="소재 이름(asset-id 미지정 시)")
    p.add_argument("--asset-id", action="append", help="asset id 직접 지정(반복 가능)")
    p.add_argument("--campaign-name", default=None)
    p.add_argument("--customer-id", default=None)
    p.add_argument("--start", default=str(date.today() - timedelta(days=30)))
    p.add_argument("--end", default=str(date.today()))
    p.add_argument("--min-keep", type=int, default=1)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--resume", action="store_true", help="제거가 아니라 재추가(복원)")
    p.add_argument("--scan-campaign", action="store_true",
                   help="--campaign-name의 광고 타입·커버리지만 진단(mutate 안 함)")
    a = p.parse_args()

    cid = a.customer_id.replace("-", "").strip() if a.customer_id else customer_id_for_title(a.title)
    client = load_client()
    ga = client.get_service("GoogleAdsService")

    if a.scan_campaign:
        if not a.campaign_name:
            sys.exit("⚠️ --scan-campaign 은 --campaign-name 필요.")
        rows = scan_campaign_ad_types(ga, cid, a.campaign_name)
        print(f"cid={cid} · 캠페인={a.campaign_name} · 광고 타입 {len(rows)}종")
        for r in rows:
            mark = "✅" if r["supported"] else "❌ 미지원"
            fld = f" · {r['field']}" if r["field"] else ""
            print(f"  {mark} {r['ad_type']} ({r['count']}건){fld}")
        if any(not r["supported"] for r in rows):
            print("(❌ 타입은 TYPE_FIELD에 필드 추가 필요 — 영상 리스트 필드명 확인 후 등록.)")
        return

    asset_ids = set(a.asset_id or [])
    if not asset_ids:
        if not a.asset_name or "실제" in a.asset_name or "여기에" in a.asset_name:
            sys.exit("⚠️ --asset-id 또는 실제 --asset-name 필요.")
        asset_ids = resolve_asset_ids(ga, cid, a.asset_name, a.start, a.end)
    if not asset_ids:
        sys.exit("❌ 대상 asset id 못 찾음.")
    print(f"cid={cid} · asset_ids={sorted(asset_ids)} · {'APPLY' if a.apply else 'DRY-RUN'}"
          f"{' · RESUME' if a.resume else ' · REMOVE'}")

    ads = find_ads_for_assets(ga, cid, asset_ids, a.start, a.end, campaign_name=a.campaign_name)
    print(f"붙은 광고 {len(ads)}건" + (f" (캠페인={a.campaign_name})" if a.campaign_name else ""))
    res = change_asset(client, ga, cid, asset_ids, ads, remove=not a.resume, apply=a.apply, min_keep=a.min_keep)
    for r in res:
        line = f"  [{r['status']}] {r['ad_type']} {r['ad_group_ad']}"
        if "before" in r:
            line += f" · {r.get('before')}→{r.get('after')}"
        if r.get("reason"):
            line += f" · {r['reason']}"
        print(line)
    if not a.apply:
        print("(변경 없음. 실제 적용은 --apply. 복원은 --resume.)")


if __name__ == "__main__":
    _cli()
