from pipeline.main import _context_sha, _context_stale
from pipeline.schemas import CreativeDataset


def test_context_sha_deterministic_and_empty():
    assert _context_sha("") == ""
    a = _context_sha("게임 컨텍스트 A")
    assert a == _context_sha("게임 컨텍스트 A")
    assert len(a) == 16
    assert _context_sha("게임 컨텍스트 B") != a


def test_context_stale_branches():
    assert _context_stale("aaa", "bbb") is True      # 변경됨
    assert _context_stale("aaa", "aaa") is False      # 동일
    assert _context_stale("", "bbb") is False          # 이전 기록 없음
    assert _context_stale("aaa", "") is False          # 현재 컨텍스트 없음


def test_dataset_serializes_game_context():
    ds = CreativeDataset(title_id="zeus", generated_at="2026-07-09T09:00:00+09:00",
                         game_context="[게임 컨텍스트] 테스트")
    dumped = ds.model_dump(by_alias=True)
    assert dumped["game_context"] == "[게임 컨텍스트] 테스트"

    ds2 = CreativeDataset(title_id="zeus", generated_at="2026-07-09T09:00:00+09:00")
    assert ds2.model_dump(by_alias=True)["game_context"] == ""   # 기본값(무회귀)
