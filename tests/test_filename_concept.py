"""filename_to_concept — gd식 후행 세그먼트 처리 회귀 (QA P0-B)."""
from pipeline.main import filename_to_concept


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
