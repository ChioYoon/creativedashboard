"""tagger.py 장르별 프롬프트 시스템 단위 테스트."""
import pytest
from pipeline.tagger import (
    get_system_instruction,
    prompt_version,
    DEFAULT_GENRE,
    GENRE_INSTRUCTIONS,
)


def test_default_genre_constant():
    assert DEFAULT_GENRE == "character_collection_rpg"


def test_genre_instructions_has_both_genres():
    assert "character_collection_rpg" in GENRE_INSTRUCTIONS
    assert "martial_arts_action_rpg" in GENRE_INSTRUCTIONS


def test_get_system_instruction_char_rpg():
    instr = get_system_instruction("character_collection_rpg")
    assert isinstance(instr, str) and len(instr) > 100
    # 펩 전용 캐릭터 가이드 포함 확인
    assert "다수 캐릭터 라인업" in instr or "SD/귀여운" in instr


def test_get_system_instruction_martial_arts():
    instr = get_system_instruction("martial_arts_action_rpg")
    assert isinstance(instr, str) and len(instr) > 100
    # 무협 가이드 포함 확인
    assert "무공" in instr or "무협" in instr or "세계관" in instr


def test_get_system_instruction_unknown_falls_back_to_default():
    instr_unknown = get_system_instruction("unknown_genre_xyz")
    instr_default = get_system_instruction(DEFAULT_GENRE)
    assert instr_unknown == instr_default


def test_prompt_version_includes_genre_suffix():
    v_char = prompt_version("character_collection_rpg")
    v_martial = prompt_version("martial_arts_action_rpg")
    assert v_char.endswith("-char-rpg")
    assert v_martial.endswith("-martial-v1")


def test_prompt_version_different_per_genre():
    """캐시 격리 보장 — 두 버전 문자열이 달라야 함."""
    assert prompt_version("character_collection_rpg") != prompt_version("martial_arts_action_rpg")


def test_prompt_version_default_arg():
    """인수 없이 호출 시 DEFAULT_GENRE 버전 반환."""
    assert prompt_version() == prompt_version(DEFAULT_GENRE)


def test_prompt_version_unknown_genre_falls_back():
    assert prompt_version("unknown_xyz") == prompt_version(DEFAULT_GENRE)
