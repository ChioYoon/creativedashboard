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
