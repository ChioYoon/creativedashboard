"""scan_by_filename — 멀티 루트 + 파일명 컨벤션 단위테스트."""
from pipeline.scanner import scan_by_filename, parse_filename


def _touch(p):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")


def test_scan_by_filename_multiple_roots_merge(tmp_path):
    """배너/비디오 분리 폴더 → 하나로 합쳐 스캔, 같은 creative_name 은 파일 병합."""
    r1 = tmp_path / "banner"
    r2 = tmp_path / "video"
    _touch(r1 / "250115_BNR_ConceptA_L_728x90_KR.jpg")
    _touch(r1 / "250115_BNR_ConceptB_L_320x50_KR.jpg")
    _touch(r2 / "250213_VID_ConceptA_V_1080x1920_EN.mp4")   # ConceptA 가 두 root 에 존재
    cands = scan_by_filename([r1, r2], types=("BNR", "VID"))
    names = sorted(c.creative_name for c in cands)
    assert names == ["ConceptA", "ConceptB"]
    a = next(c for c in cands if c.creative_name == "ConceptA")
    assert len(a.all_files) == 2                            # 배너 + 비디오 병합(유실 없음)


def test_scan_by_filename_single_root_backward_compat(tmp_path):
    """단일 경로(str/Path) 입력 — 기존 동작 유지."""
    r = tmp_path / "root"
    _touch(r / "260123_BNR_A-AI-Cinematic01A-DA_L_1200x628_EN.jpg")
    cands = scan_by_filename(r, types=("BNR", "VID"))
    assert [c.creative_name for c in cands] == ["A-AI-Cinematic01A-DA"]


def test_parse_filename_trailing_segment_and_3letter_lang():
    """갓앤데몬 컨벤션 — lang 3자(CNT) + 후행 세그먼트(_NONE) 허용."""
    m = parse_filename("250614_VID_L-UA-Character-666662nd-01_V_1080x1920_CNT_NONE.mp4")
    assert m is not None
    assert m["creative_name"] == "L-UA-Character-666662nd-01"
    assert m["type"] == "VID"
    m2 = parse_filename("250115_BNR_L-DA-Model-lee-04_V_768x1024_KR_NONE.jpg")
    assert m2 is not None and m2["creative_name"] == "L-DA-Model-lee-04"


def test_parse_filename_pepp_convention_unchanged():
    """기존 펩 컨벤션(후행 세그먼트 없음·2자 lang) 무회귀."""
    m = parse_filename("260123_BNR_A-AI-Cinematic01A-DA_L_1200x628_EN.jpg")
    assert m is not None and m["creative_name"] == "A-AI-Cinematic01A-DA"


def test_parse_filename_non_ua_rejected():
    """비-UA 소스 파일(원본·웹툰캡쳐 등)은 매칭 안 됨."""
    assert parse_filename("640x116.png") is None
    assert parse_filename("웹툰캡쳐01_sm_250515_1080x1080_x.jpg") is None
