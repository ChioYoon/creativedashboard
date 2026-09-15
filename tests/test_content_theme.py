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


def test_typo_alias_resolves(tmp_path):
    # 오타 훅 → 별칭 → 정규 매핑 (theme_map v2.1)
    m = load_map()
    assert assign_theme("L-Genre-MarketReveiw-01-UA", m)["theme_primary"] == "N/A:고지"       # Reveiw→Review
    assert assign_theme("P-Ingame-ClassElimentalist-01-PV", m)["theme_primary"] == "전투 쾌감"  # Elimentalist→Elementalist
    # 정규 철자도 동일 매핑
    assert assign_theme("P-Ingame-ClassElementalist-01-PV", m)["theme_primary"] == "전투 쾌감"


def test_colosseum_pvp():
    # 미제작이던 경쟁(PvP) 축이 신규 훅으로 채워짐
    assert assign_theme("L-Event-Colosseum-01-DA", load_map())["theme_primary"] == "경쟁(PvP)"


def test_ld_launch_date_variant_flag():
    # LD = Launch Date 변형: theme 통합 + launch_date_variant 플래그 보존 (패치 v2.1 correction)
    r = assign_theme("L-Ingame-ClassRangerLD-01-PV", load_map())
    assert r["theme_primary"] == "전투 쾌감" and r["launch_date_variant"] is True
    r2 = assign_theme("P-Ingame-ClassRanger-01-PV", load_map())
    assert r2["theme_primary"] == "전투 쾌감" and r2["launch_date_variant"] is False


def test_partner_field_preserved():
    # 컬쳐랜드 제휴 소재 — partner 필드 보존, 판정 대상 유지
    assert assign_theme("L-Genre-CL-Cash-PV", load_map())["partner"] == "cultureland"
    assert assign_theme("L-Genre-CL-Brand-PV", load_map())["partner"] == "cultureland"


def test_reviewed_defaults_false():
    # §6 검수 전 판정 미투입 — 항상 False 시작
    assert assign_theme("P-Slogan-CinematicPV30s-01-PV", load_map())["theme_reviewed"] is False


# ── 도원암귀 전용 훅맵 (theme_map_tougenanki.json, R팀 회신 v1) ──

def test_tougenanki_title_map():
    # 도원암귀 네이밍은 zeus 맵서 전부 미매핑 → 전용 맵으로 매칭
    assert assign_theme("FGT-IP-MudanoSSR01-DA")["new_hook"] is True                    # 기본(zeus) 맵: 미매핑
    r = assign_theme("FGT-IP-MudanoSSR01-DA", title="tougenanki")
    # 훅맵 v1.3(T3 확정): SSR 3훅은 지급 고지 확인 → 보상·혜택으로 전환 (v1.1 IP·캐릭터에서 변경)
    assert r["theme_primary"] == "보상·혜택" and r["new_hook"] is False


def test_tougenanki_execution_status():
    # 훅맵 v1.7: 제작 자산 ≠ 집행 예정. FGT 원본 2건 미집행 · MudanoSSR 1쌍 중복 등록
    from pipeline.content_theme import execution_of
    assert execution_of("FGT-IP-OniMainTVA01-DA", "tougenanki")["execution_status"] == "not_planned"
    assert execution_of("FGT-IP-MudanoSSR01-DA", "tougenanki")["duplicate_of"] == "P-Reward-MudanoSSR01-DA"
    planned = execution_of("P-Gamer-RasetsuBattle01-DA", "tougenanki")
    assert planned["execution_status"] == "planned" and planned["duplicate_of"] is None
    # 훅맵 없는 타이틀(zeus)은 전량 planned
    assert execution_of("NU-Class-ClassArtisan01", "zeus")["execution_status"] == "planned"


def test_tougenanki_flags_deduped():
    # 훅맵 v1.7에 동일 ip_guard 중복 기재분 존재 → 로더에서 dedupe(제작 브리프 중복 줄 방지)
    f = assign_theme("P-Reward-RasetsuSSR01-DA", title="tougenanki")["theme_flags"]
    assert len(f) == len(set(f))


def test_tougenanki_one_digit_variation():
    # 도원암귀 정규화: \d{1,2}$ — 1자리 번호(Cutscene0)도 제거. zeus \d{2}$ 였으면 미매칭
    assert assign_theme("P-Character-Cutscene0-DA", title="tougenanki")["theme_primary"] == "스토리·세계관"


def test_tougenanki_alias_typo_and_case():
    # alias 3종: 오타 + 대소문자
    assert assign_theme("P-Battle-Freindship02-DA", title="tougenanki")["theme_primary"] == "스토리·세계관"   # Freindship→Friendship
    assert assign_theme("L-Story-OnivsMomotaro01-DA", title="tougenanki")["theme_primary"] == "스토리·세계관"  # 대소문자
    assert assign_theme("L-Story-kyotostory01-DA", title="tougenanki")["theme_primary"] == "스토리·세계관"     # 선두 소문자


def test_tougenanki_intent_axis_and_flags():
    # intent_axis(2번째 세그) 보존 + 훅 flags(ssr_grade 등) 보존
    r = assign_theme("P-Reward-MudanoSSR01-DA", title="tougenanki")
    assert r["intent_axis"] == "Reward"                 # content_theme 판정엔 미사용, 별도 보존
    assert "ssr_grade" in r["theme_flags"]
    # zeus 소재는 intent_axis 없음(2번째 세그=Category)
    assert assign_theme("P-Ingame-Region-Thebes-UA")["intent_axis"] is None


def test_tougenanki_new_hook_review_queue():
    # gate_binding.new_hook_policy=REVIEW_QUEUE — 미등록 훅은 자동분류 없이 N/A:미상+검수
    r = assign_theme("P-Battle-TotallyUnknownHook-01-DA", title="tougenanki")
    assert r["theme_primary"] == "N/A:미상" and r["review_flag"] == "검수"
    assert r["intent_axis"] == "Battle"                 # intent는 세그먼트라 미등록 훅에도 잡힘
