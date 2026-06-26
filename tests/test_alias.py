"""소재명 별칭 — 로더·apply_alias·스키마 (별칭 매핑 기능)."""
import json
from pathlib import Path

from pipeline.main import _load_creative_aliases, apply_alias


def test_apply_alias_in_candidates():
    assert apply_alias("A-Char-01", {"A-Char-01"}, {"X": "Y"}) == "A-Char-01"


def test_apply_alias_remaps():
    assert apply_alias("ConnectBNR", {"P-DA-Reward-gacha-01"}, {"ConnectBNR": "P-DA-Reward-gacha-01"}) == "P-DA-Reward-gacha-01"


def test_apply_alias_no_alias_returns_self():
    assert apply_alias("ConnectBNR", {"P-DA-Reward-gacha-01"}, {}) == "ConnectBNR"
    assert apply_alias("ConnectBNR", {"P-DA-Reward-gacha-01"}, None) == "ConnectBNR"


def test_load_creative_aliases(tmp_path):
    ov = tmp_path / "js" / "titles_overrides.json"
    ov.parent.mkdir(parents=True)
    ov.write_text(json.dumps({"gd": {"_creative_name_aliases": {"ConnectBNR": "P-DA-Reward-gacha-01"}}}), encoding="utf-8")
    assert _load_creative_aliases("gd", tmp_path) == {"ConnectBNR": "P-DA-Reward-gacha-01"}
    assert _load_creative_aliases("pepp-us", tmp_path) == {}   # 키 없음
    assert _load_creative_aliases("gd", tmp_path / "nope") == {}  # 파일 없음


def test_dataset_unmatched_default():
    from pipeline.schemas import CreativeDataset
    ds = CreativeDataset(title_id="t", generated_at="2026-01-01T00:00:00+09:00")
    assert ds.model_dump(by_alias=True)["unmatched_assets"] == []
