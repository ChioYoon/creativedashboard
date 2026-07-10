# -*- coding: utf-8 -*-
"""캠페인명 캐노니컬 파싱 — LTV 대시보드 규칙.

규칙: {agency}_{executor}_{title}_{country}_{media}_{ua_type}_{os}_{product}[_{date}]
'_' 구분, 마지막 6자리 숫자 세그먼트는 date(캠페인 시작일). 위치 기반.
(media→media_group 룩업·country/product 마스터 정규화는 LTV 프로젝트 소관 — 여기선 위치 원시값.)
"""
from __future__ import annotations

import re

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


def build_campaign_canonical(campaign_names) -> dict:
    """고유 campaign_name → {ua_type, country, os, media, product} 맵.

    중복 제거·빈/None 제외. 추출 실패 필드는 '' (대시보드가 '미상' 버킷 처리). 빈 입력 → {}.
    """
    out: dict = {}
    for cn in {c for c in (campaign_names or []) if c}:
        pos = parse_campaign_canonical(cn)
        out[cn] = {
            "ua_type": campaign_ua_type(cn),            # token (견고)
            "country": campaign_country(cn),            # XX-XX 스캔 (라이브 일치)
            "os": campaign_os(cn),                      # 토큰 스캔 (라이브 일치)
            "media": pos["media"] or "",                # positional best-effort
            "product": pos["product"] or "",
        }
    return out
