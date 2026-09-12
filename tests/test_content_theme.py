"""content_theme 훅 매핑 — 정규화·룩업·신규훅·병존(core_usp) 검증."""
from pipeline.content_theme import assign_theme, normalize_hook, load_map


def test_normalize_strips_suffixes():
    assert normalize_hook("CinematicPV30s") == "CinematicPV"
    assert normalize_hook("Universe03") == "Universe"
    assert normalize_hook("ClassRangerLD") == "ClassRanger"
    assert normalize_hook("CharacterName01") == "CharacterName"
    # 'Market1st'의 '1st'는 2자리숫자 접미가 아님 — 보존
    assert normalize_hook("Market1st") == "Market1st"


def test_single_and_compound_hook_lookup():
    m = load_map()
    assert assign_theme("L-Ingame-ClassArtisan-01-SS", m)["theme_primary"] == "수집·육성"
    # 복합 훅(Dirguide-Artisan) 우선 매칭
    assert assign_theme("L-Genre-Dirguide-Artisan-UA", m)["theme_primary"] == "수집·육성"
    # 지역 변형(Region-Thebes) → Region 폴백
    assert assign_theme("P-Ingame-Region-Thebes-UA", m)["theme_primary"] == "그래픽·비주얼"


def test_na_and_core_usp_coexist():
    # N/A 여도 core_usp 는 채워짐(병존 근거)
    r = assign_theme("L-Event-Market1st-02-DA", load_map())
    assert r["theme_primary"] == "N/A:고지"
    assert r["core_usp"] == "대세감"
    assert r["new_hook"] is False


def test_new_hook_flagged():
    r = assign_theme("L-Genre-CompletelyNovelHook-01-PV", load_map())
    assert r["new_hook"] is True
    assert r["theme_primary"] == "N/A:미상"
    assert r["review_flag"] == "검수"


def test_reviewed_defaults_false():
    # §6 검수 전 판정 미투입 — 항상 False 시작
    assert assign_theme("P-Slogan-CinematicPV30s-01-PV", load_map())["theme_reviewed"] is False
