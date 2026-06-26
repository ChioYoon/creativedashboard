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


def test_build_kpi_index_alias_and_unmatched():
    from pipeline.main import build_kpi_index

    class K:  # duck-typed CreativeKpiDaily
        def __init__(self, name, at="IMAGE", impr=10, cost=5.0):
            self.creative_name = name; self.asset_type = at
            self.impressions = impr; self.cost = cost

    candidates = {"P-DA-Reward-gacha-01", "A-Char-01"}
    aliases = {"ConnectBNR": "P-DA-Reward-gacha-01"}
    rows = [
        K("251104_BNR_A-Char-01_L_1200x628_EN.jpg"),   # 표준 → A-Char-01 조인
        K("ConnectBNR"),                                # 별칭 → P-DA-Reward-gacha-01 조인
        K("Rank1", impr=100, cost=20.0),                # 미매칭(IMAGE, impr>0)
        K("TextAsset", at="TEXT", impr=50),             # TEXT → 미매칭 제외
        K("ZeroImpr", impr=0),                          # impr=0 → 제외
    ]
    index, unmatched = build_kpi_index(rows, candidates, aliases)
    assert set(index.keys()) == {"A-Char-01", "P-DA-Reward-gacha-01"}
    assert [u["concept"] for u in unmatched] == ["Rank1"]
    u = unmatched[0]
    assert u["source"] == "google_ads" and u["impressions"] == 100 and u["asset_types"] == ["IMAGE"]
