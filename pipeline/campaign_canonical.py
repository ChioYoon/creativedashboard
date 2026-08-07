# -*- coding: utf-8 -*-
"""캠페인명 캐노니컬 파싱 — LTV 대시보드 규칙.

규칙: {agency}_{executor}_{title}_{country}_{media}_{ua_type}_{os}_{product}[_{date}]
'_' 구분, 마지막 6자리 숫자 세그먼트는 date(캠페인 시작일). 위치 기반.
(media→media_group 룩업·country/product 마스터 정규화는 LTV 프로젝트 소관 — 여기선 위치 원시값.)
"""
from __future__ import annotations

import re

from .media_normalize import normalize_media

# 이름파싱 media가 '무효'(위치 밀림 잔재·오디언스/OS/ua 토큰·빈값)임을 판별 → MMP 폴백 트리거
_NON_MEDIA_TOKENS = {
    "all", "ios", "aos", "ad", "android", "web", "전체",
    "nu-pre", "rt", "boosting", "nu", "",
}

_FIELDS = ["agency", "executor", "title", "country", "media", "ua_type", "os", "product"]
_KNOWN_UA_TYPES = ("NU-Pre", "RT", "Boosting", "NU")  # NU-Pre 우선(NU 보다 앞)
_DATE_RE = re.compile(r"^\d{6}$")


def parse_campaign_canonical(name: str) -> dict:
    """캠페인명 → 캐노니컬 필드 dict (위치 기반). 부족/위반 시 가능한 필드만, 나머지 None."""
    out: dict = {f: None for f in _FIELDS}
    out["date"] = None
    if not name:
        return out
    segs = name.split("_")
    if segs and _DATE_RE.match(segs[-1]):
        out["date"] = segs[-1]
        segs = segs[:-1]
    for i, f in enumerate(_FIELDS):
        if i < len(segs):
            out[f] = segs[i]
    return out


def campaign_ua_type(name: str) -> str:
    """캠페인명에서 ua_type 추출 — 세그먼트와 정확 일치(NU-Pre 우선). 없으면 ''."""
    if not name:
        return ""
    segs = set(name.split("_"))
    for ua in _KNOWN_UA_TYPES:
        if ua in segs:
            return ua
    return ""


_COUNTRY_RE = re.compile(r"^[A-Z]{2,4}-[A-Z]{2}$")   # US-EN, CA-FR, KR-KR …
_COUNTRY_CODE_RE = re.compile(r"^[A-Z]{2,4}$")       # 위치 기반 단일 국가코드 (KR, US …)
# AD·AOS 모두 Android(타이틀별 표기 상이 — 제우스=AD, GD/PH=AOS), ALL=전체(양 OS).
_OS_MAP = {"ios": "iOS", "aos": "Android", "ad": "Android", "android": "Android", "web": "Web", "all": "전체"}


def campaign_country(name: str) -> str:
    """캠페인명에서 country 추출 — 위치 country 토큰(단일 KR / 지역-국가 KR-KR) 우선, XX-XX 세그 스캔 폴백. 없으면 ''."""
    if not name:
        return ""
    # 1) 위치 기반 country 토큰 (규칙: {agency}_{executor}_{title}_{country}_{media}_…)
    c = (parse_campaign_canonical(name).get("country") or "")
    if "-" in c:                       # XX-XX(지역-국가) → 앞부분(국가)
        c = c.split("-")[0]
    if _COUNTRY_CODE_RE.match(c):
        return c
    # 2) 폴백: 위치가 어긋난 이름은 XX-XX 세그먼트 스캔 (기존 동작 유지)
    for seg in name.split("_"):
        if _COUNTRY_RE.match(seg):
            return seg.split("-")[0]
    return ""


def campaign_os(name: str) -> str:
    """캠페인명에서 os 추출 — 토큰 소문자 매칭 → iOS/Android/Web. 없으면 ''. (라이브 JS parseOS 이식)"""
    if not name:
        return ""
    for seg in name.split("_"):
        v = _OS_MAP.get(seg.lower())
        if v:
            return v
    return ""


def campaign_media(name: str) -> str:
    """캠페인명에서 media 추출 — ua_type 바로 앞 세그먼트(규칙: ..._{media}_{ua_type}_...).

    ua_type 토큰(NU-Pre/RT/Boosting/NU)이 견고하게 탐지되므로, agency_executor 접두
    유무와 무관하게 media 위치를 앵커링한다. ua_type을 못 찾으면 위치 기반(index 4) 폴백.
    (매체명은 개방형이라 고정 목록 매칭 대신 ua_type 상대위치로 잡음.)
    """
    if not name:
        return ""
    segs = name.split("_")
    if segs and _DATE_RE.match(segs[-1]):   # date 꼬리 제거(위치 정합)
        segs = segs[:-1]
    ua = campaign_ua_type(name)
    if ua and ua in segs:
        idx = segs.index(ua)
        if idx >= 1:
            return segs[idx - 1]
    return parse_campaign_canonical(name).get("media") or ""


def resolve_campaign_media(name: str, channel_hint: str = "") -> tuple[str, bool]:
    """이름파싱 우선 + MMP channel 폴백 → (표준 매체명, 충돌여부).

    - 이름파싱 media가 유효하면 그 값을 표준화해 채택(1순위).
    - 이름파싱이 무효(위치 밀림·OS/ua 토큰·빈값)면 MMP channel 표준화값으로 폴백.
    - 이름·MMP 둘 다 유효하고 표준값이 다르면 conflict=True(이름 채택, override 안 함).
    """
    raw = campaign_media(name)
    name_ok = bool(raw and raw.strip().lower() not in _NON_MEDIA_TOKENS)
    name_std = normalize_media(raw) if name_ok else ""
    ch_std = normalize_media(channel_hint) if channel_hint else ""
    if name_std:
        return name_std, bool(ch_std and ch_std != name_std)
    if ch_std:
        return ch_std, False                 # 이름파싱 실패 → MMP 폴백
    return normalize_media(raw), False        # 빈값 등 원시 통과


def build_campaign_canonical(campaign_names, channel_map: dict | None = None) -> dict:
    """고유 campaign_name → {ua_type, country, os, media, product[, media_conflict]} 맵.

    channel_map: {campaign_name: 대표 MMP channel}. media는 이름파싱 우선 + channel 폴백,
    둘 다 표준화(normalize_media)해 매체 축을 단일값으로 수렴. 충돌 시 media_conflict 부착.
    중복 제거·빈/None 제외. 빈 입력 → {}.
    """
    channel_map = channel_map or {}
    out: dict = {}
    for cn in {c for c in (campaign_names or []) if c}:
        pos = parse_campaign_canonical(cn)
        media, conflict = resolve_campaign_media(cn, channel_map.get(cn, ""))
        entry = {
            "ua_type": campaign_ua_type(cn),            # token (견고)
            "country": campaign_country(cn),            # XX-XX 스캔 (라이브 일치)
            "os": campaign_os(cn),                      # 토큰 스캔 (라이브 일치)
            "media": media,                             # 이름앵커 우선 + MMP 폴백, 표준화
            "product": pos["product"] or "",
        }
        if conflict:
            entry["media_conflict"] = {
                "name": normalize_media(campaign_media(cn)),
                "mmp": normalize_media(channel_map.get(cn, "")),
            }
        out[cn] = entry
    return out


if __name__ == "__main__":
    # media 앵커 로직 self-check (접두 유무 양쪽 + 폴백)
    assert campaign_media("Incross_HQ_ZEUS_KR_GA_NU-Pre_ALL_DemandGen_260701") == "GA"   # full 접두
    assert campaign_media("ZEUS_KR_Kakao_NU-Pre_ALL_Conv-Bizboard_260723") == "Kakao"    # 접두 누락 → 앵커
    assert campaign_media("ZEUS_KR_Kakao_NU-Pre_iOS_Install-Display_260723") == "Kakao"   # media였던 자리에 os
    assert campaign_media("Foo_Bar_Title_KR_Meta_RT_ios_x_260101") == "Meta"             # RT 앵커
    assert campaign_media("Ag_Ex_Ti_KR_MediaX_UnknownUa_ios_prod") == "MediaX"           # ua 없음 → 위치폴백(index 4)
    assert campaign_media("") == ""
    # resolve_campaign_media: 이름파싱 우선 + MMP 폴백 + 충돌
    assert resolve_campaign_media("Incross_HQ_ZEUS_KR_GA_NU-Pre_ALL_x_260701") == ("GA", False)          # 이름 유효
    assert resolve_campaign_media("ZEUS_KR_Kakao_NU-Pre_ALL_x_260723", "kakao") == ("Kakao", False)       # 이름=MMP
    assert resolve_campaign_media("Foo_Bar_Ti_KR_FB_RT_ios_x", "") == ("Meta", False)                     # 이름토큰 표준화 FB→Meta
    assert resolve_campaign_media("Ti_KR_ALL_NU_x_260101", "facebook.business") == ("Meta", False)         # 이름무효 → MMP 폴백
    assert resolve_campaign_media("Foo_Bar_Ti_KR_Tiktok_RT_x", "moloco")[1] is True                        # 충돌(이름 채택)
    print("campaign_media / resolve self-check OK")
