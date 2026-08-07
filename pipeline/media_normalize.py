# -*- coding: utf-8 -*-
"""매체명 정규화 — 이름파싱 토큰 + MMP channel/media_source 원시값을 단일 표준값으로 수렴.

두 신호(캠페인명 파싱 media, MMP channel)와 타이틀별 상이한 표기(gd=FB/ML/TT,
zeus=Meta/Kakao/Tiktok, Airbridge=facebook.business, AppsFlyer=facebook ads …)를
하나의 표준 매체명으로 매핑해 대시보드 매체 축 파편화를 막는다.

미매핑 값은 원시값 그대로 통과 + 경고 로그(silent drop 금지). 확정 대기 항목은 아래 PENDING.
"""
from __future__ import annotations

# 표준 매체명(값) ← 원시 표기(키, 소문자). 이름파싱 토큰과 MMP channel 양쪽 흡수.
MEDIA_ALIASES: dict[str, str] = {
    # Meta
    "meta": "Meta", "fb": "Meta", "facebook": "Meta",
    "facebook.business": "Meta", "facebook ads": "Meta", "facebook_ads": "Meta",
    # TikTok
    "tiktok": "TikTok", "tt": "TikTok", "tiktokglobal_int": "TikTok",
    # Moloco
    "moloco": "Moloco", "ml": "Moloco", "moloco_int": "Moloco",
    # Appier
    "appier": "Appier", "ap": "Appier", "appier_int": "Appier",
    # Kakao
    "kakao": "Kakao",
    # Criteo
    "criteo": "Criteo", "criteo_new": "Criteo",
    # Naver
    "naver": "Naver", "navergfa": "Naver", "naver_int": "Naver",
    # Microsoft
    "msn": "MSN", "microsoft.ads": "MSN", "microsoft ads": "MSN",
    # Pangle
    "pangle": "Pangle",
    # Google Ads
    "ga": "GA", "google": "GA", "googleads": "GA",
}

# 확정 대기(마케터 확인) — 매핑 없이 원시값 통과. 확정되면 위 MEDIA_ALIASES로 이동.
#   da        : Airbridge zeus 38건, 정체 불명(디스플레이 총칭? 특정 매체?)
#   tt-pg,tt-tt: TikTok 계열 세부(Pangle 등?) 여부 불명 — 잘못 병합 방지 위해 보류
PENDING = {"da", "tt-pg", "tt-tt"}


def normalize_media(value: str) -> str:
    """원시 매체 표기 → 표준 매체명. 미매핑/보류/빈값은 원시값 그대로 반환."""
    if not value:
        return ""
    key = value.strip().lower()
    if key in PENDING:
        return value.strip()          # 보류: 원시값 유지(경고는 호출측 집계에서)
    return MEDIA_ALIASES.get(key, value.strip())


def unmapped_media(values) -> set:
    """정규화 실패(표준 매핑 없음) 원시값 집합 — 경고/검수 로그용. 보류값 포함."""
    out = set()
    for v in values or []:
        if not v:
            continue
        key = v.strip().lower()
        if key not in MEDIA_ALIASES:
            out.add(v.strip())
    return out


if __name__ == "__main__":
    assert normalize_media("facebook.business") == "Meta"
    assert normalize_media("facebook ads") == "Meta"
    assert normalize_media("FB") == "Meta"
    assert normalize_media("Meta") == "Meta"
    assert normalize_media("tiktokglobal_int") == "TikTok"
    assert normalize_media("moloco_int") == "Moloco" and normalize_media("ML") == "Moloco"
    assert normalize_media("Kakao") == "Kakao"
    assert normalize_media("da") == "da"           # 보류 → 원시값
    assert normalize_media("우주매체") == "우주매체"  # 미매핑 → 원시값(통과)
    assert normalize_media("") == ""
    assert unmapped_media(["FB", "da", "우주매체"]) == {"da", "우주매체"}
    print("media_normalize self-check OK")
