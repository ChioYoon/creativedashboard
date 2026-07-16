"""tagger.py 장르별 프롬프트 시스템 단위 테스트."""
import pytest
from pathlib import Path
from pipeline.main import _load_game_context
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
    assert "dark_fantasy_card_rpg" in GENRE_INSTRUCTIONS


def test_get_system_instruction_char_rpg():
    instr = get_system_instruction("character_collection_rpg")
    assert isinstance(instr, str) and len(instr) > 100
    # 펩 전용 캐릭터 가이드 포함 확인
    assert "다수 캐릭터 라인업" in instr or "SD/귀여운" in instr


def test_get_system_instruction_dark_fantasy():
    instr = get_system_instruction("dark_fantasy_card_rpg")
    assert isinstance(instr, str) and len(instr) > 100
    # 도원암귀 전용 가이드 포함 확인
    assert "인페르노 스킬" in instr or "다크 판타지" in instr or "카드 배틀" in instr


def test_genre_instructions_has_idle_rpg():
    assert "idle_rpg" in GENRE_INSTRUCTIONS


def test_get_system_instruction_idle_rpg():
    instr = get_system_instruction("idle_rpg")
    assert isinstance(instr, str) and len(instr) > 100
    # 방치형 전용 가이드 포함 확인
    assert "방치형" in instr and ("자동 전투" in instr or "편의성" in instr)


def test_prompt_version_idle_suffix():
    v_idle = prompt_version("idle_rpg")
    assert v_idle.endswith("-idle-v1")


def test_prompt_version_idle_distinct():
    """idle 캐시 격리 — 다른 장르 버전과 모두 달라야 함."""
    versions = {prompt_version(g) for g in ("character_collection_rpg", "dark_fantasy_card_rpg", "idle_rpg")}
    assert len(versions) == 3


def test_genre_instructions_has_mmorpg():
    assert "mmorpg" in GENRE_INSTRUCTIONS


def test_get_system_instruction_mmorpg():
    instr = get_system_instruction("mmorpg")
    assert isinstance(instr, str) and len(instr) > 100
    # MMORPG 전용 가이드 포함 확인
    assert "MMORPG" in instr and ("공성" in instr or "길드" in instr or "대규모 전투" in instr)


def test_prompt_version_mmorpg_suffix():
    # v2: 동기+정형 필드(11~14) 추가 — zeus(mmorpg)만 재태깅 격리
    assert prompt_version("mmorpg").endswith("-mmorpg-v2")


def test_prompt_version_all_genres_distinct():
    """캐시 격리 — 4개 장르 버전이 모두 달라야 함."""
    versions = {prompt_version(g) for g in
                ("character_collection_rpg", "dark_fantasy_card_rpg", "idle_rpg", "mmorpg")}
    assert len(versions) == 4


def test_get_system_instruction_unknown_falls_back_to_default():
    instr_unknown = get_system_instruction("unknown_genre_xyz")
    instr_default = get_system_instruction(DEFAULT_GENRE)
    assert instr_unknown == instr_default


def test_prompt_version_char_rpg_is_base_version():
    # 펩(character_collection_rpg)은 기존 BASE 버전 그대로 — suffix 없음.
    # (suffix 추가 시 캐시 전체 무효화 → 무료 quota로 재태깅 불가 → 출력 붕괴)
    from pipeline.tagger import BASE_PROMPT_VERSION
    assert prompt_version("character_collection_rpg") == BASE_PROMPT_VERSION


def test_prompt_version_dark_fantasy_suffix():
    v_dark = prompt_version("dark_fantasy_card_rpg")
    assert v_dark.endswith("-darkfantasy-v1")


def test_prompt_version_different_per_genre():
    """캐시 격리 보장 — 두 버전 문자열이 달라야 함."""
    assert prompt_version("character_collection_rpg") != prompt_version("dark_fantasy_card_rpg")


def test_prompt_version_default_arg():
    """인수 없이 호출 시 DEFAULT_GENRE 버전 반환."""
    assert prompt_version() == prompt_version(DEFAULT_GENRE)


def test_prompt_version_unknown_genre_falls_back():
    assert prompt_version("unknown_xyz") == prompt_version(DEFAULT_GENRE)


def test_load_game_context_returns_content(tmp_path):
    md = tmp_path / "ctx.md"
    md.write_text("# 테스트 게임\n장르: RPG", encoding="utf-8")
    result = _load_game_context("ctx.md", tmp_path)
    assert "테스트 게임" in result


def test_load_game_context_missing_file_returns_empty(tmp_path, capsys):
    result = _load_game_context("nonexistent.md", tmp_path)
    assert result == ""
    captured = capsys.readouterr()
    assert "WARNING" in captured.out


def test_load_game_context_empty_path_returns_empty(tmp_path):
    result = _load_game_context("", tmp_path)
    assert result == ""
