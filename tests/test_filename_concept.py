"""filename_to_concept / resolve_concept — 비표준 자산명 concept 추출 회귀 (QA P0-B · #2)."""
from pipeline.main import filename_to_concept, resolve_concept


def test_pepp_style_unchanged():
    # 기존 펩 컨벤션은 그대로 추출 (무회귀)
    assert filename_to_concept("251104_BNR_A-Character-Adventure01A-DA_L_1200x628_EN.jpg") == "A-Character-Adventure01A-DA"
    assert filename_to_concept("251104_VID_A-Character-Combat01A-UA_L_1920x1080_EN") == "A-Character-Combat01A-UA"


def test_gd_style_trailing_segments():
    # 후행 _NONE/_KR_NONE · 3자 lang CNT — scanner.py FILENAME_PATTERN 과 정합되어야 KPI 조인됨
    assert filename_to_concept("241211_BNR_Copy-Character-V1_V_1200x1500_NONE_KR_NONE.png") == "Copy-Character-V1"
    assert filename_to_concept("250614_VID_L-UA-Character-666662nd-01_V_1080x1920_CNT_NONE.mp4") == "L-UA-Character-666662nd-01"


def test_duplicate_suffix():
    assert filename_to_concept("251104_BNR_A-Character-Adventure01A-DA_L_1200x628_EN (1).jpg") == "A-Character-Adventure01A-DA"


def test_unparseable_returns_none():
    assert filename_to_concept("random_garbage_file.png") is None
    assert filename_to_concept("") is None


# ── resolve_concept: KPI·MMP 조인 공용 관대 추출 (#2) ──

def test_resolve_concept_standard():
    assert resolve_concept("251104_BNR_A-Character-Adventure01A-DA_L_1200x628_EN.jpg") == "A-Character-Adventure01A-DA"


def test_resolve_concept_google_ads_autogen():
    # Google Ads 자동생성명(타임스탬프·종횡비 1.91:1) — strict 실패 → parts[2] 폴백으로 베이스 소재명
    assert resolve_concept("260123_BNR_A-AI-Figure01A-DA_L_1200x628_EN_2026-01-22_17-38-56_1.91:1") == "A-AI-Figure01A-DA"
    # size-letter 누락(_1200x1500_ES)
    assert resolve_concept("251111_BNR_A-Character-Adventure02A-DA_1200x1500_ES") == "A-Character-Adventure02A-DA"


def test_resolve_concept_facebook_mixed():
    # Airbridge Facebook _ALL_Mixed_ (기존 mmp_concept 동작 유지)
    assert resolve_concept("251104_BNR_A-Character-Keyart01A-DA_ALL_Mixed_EN") == "A-Character-Keyart01A-DA"


def test_resolve_concept_empty():
    assert resolve_concept("") == ""
