# -*- coding: utf-8 -*-
"""v5.8 CreativeTag 신필드(동기+정형 시각) — mmorpg 한정 프롬프트 게이트, 스키마는 공용 Optional."""
import json
import pytest
from pydantic import ValidationError

from pipeline.schemas import CreativeTag


def _base(**extra):
    d = {
        "hooking_strategy": "실패/분노 유도",
        "core_usp": "혜택형(무료뽑기/보상)",
        "visual_style": "2D 일러스트",
        "strengths": [{"signal": "강한 비주얼 임팩트", "evidence": "0~3초 고퀄 3D 캐릭터 클로즈업으로 시선 고정"}],
        "creator_intent": "고퀄 그래픽으로 코어 유저의 전환을 끌어내려는 의도",
        "one_line_insight": "비주얼 후킹은 강하나 행동 유도가 비어 있음 — 엔드카드에 사전예약 CTA를 추가해 전환 구조로 개선",
    }
    d.update(extra)
    return d


def test_new_fields_parse():
    """mmorpg 응답: 동기/캐릭터/컬러톤/CTA 파싱."""
    tag = CreativeTag.model_validate_json(json.dumps(_base(
        player_motivation="경쟁형",
        main_characters=["제우스", "레인저"],
        color_tone="골드·다크 판타지",
        has_cta=False,
    ), ensure_ascii=False))
    assert tag.player_motivation == "경쟁형"
    assert tag.main_characters == ["제우스", "레인저"]
    assert tag.color_tone == "골드·다크 판타지"
    assert tag.has_cta is False


def test_new_fields_absent_defaults():
    """타 장르 응답(신필드 미출력) → 기본값으로 하위 호환."""
    tag = CreativeTag.model_validate_json(json.dumps(_base(), ensure_ascii=False))
    assert tag.player_motivation is None
    assert tag.main_characters == []
    assert tag.color_tone is None
    assert tag.has_cta is None


def test_invalid_motivation_rejected():
    with pytest.raises(ValidationError):
        CreativeTag.model_validate_json(json.dumps(_base(player_motivation="수집형"), ensure_ascii=False))
