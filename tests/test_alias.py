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
    assert u["asset_urls"] == []  # asset_url 없는 행 → 빈 리스트


def test_build_kpi_index_unmatched_collects_distinct_urls():
    """같은 concept 이름에 서로 다른 집행 영상 → asset_urls 에 중복 제거된 다중 링크."""
    from pipeline.main import build_kpi_index

    class K:
        def __init__(self, name, url=None, at="YOUTUBE_VIDEO", impr=10, cost=5.0):
            self.creative_name = name; self.asset_type = at
            self.impressions = impr; self.cost = cost; self.asset_url = url

    yt = "https://www.youtube.com/watch?v="
    rows = [
        K("클래스 소개", url=yt + "AAA", impr=30, cost=3.0),
        K("클래스 소개", url=yt + "BBB", impr=20, cost=2.0),   # 같은 이름·다른 영상
        K("클래스 소개", url=yt + "AAA", impr=10, cost=1.0),   # 중복 URL → 1건으로 합쳐짐
        K("단일 영상", url=yt + "CCC", impr=5, cost=0.5),
    ]
    _index, unmatched = build_kpi_index(rows, {"기타"}, {})
    by_concept = {u["concept"]: u for u in unmatched}
    assert by_concept["클래스 소개"]["asset_urls"] == [yt + "AAA", yt + "BBB"]  # 정렬·중복 제거
    assert by_concept["클래스 소개"]["impressions"] == 60  # 노출은 3행 합산
    assert by_concept["단일 영상"]["asset_urls"] == [yt + "CCC"]


def test_inject_mmp_alias_and_unmatched():
    from pipeline.main import inject_mmp_into_records

    class R:  # duck-typed CreativeRecord
        def __init__(self, cid, name):
            self.creative_id = cid; self.소재명 = name
            self.mmp_source = None; self.mmp_quality_score = None

    class M:  # duck-typed CreativeMmpDaily
        def __init__(self, name, installs=0, impr=0, cost=0.0):
            self.creative_name = name; self.installs = installs
            self.impressions = impr; self.cost = cost; self.channel = "Meta"
            self.clicks = 0; self.retained_d1 = 0; self.revenue_d7 = 0.0; self.conversions = 0

    records = [R("c1", "P-DA-Reward-gacha-01")]
    mmp = [
        M("ConnectBNR", installs=5),    # 별칭 → P-DA-Reward-gacha-01 조인
        M("Rank1", installs=3, impr=50),  # 미매칭(활동O)
        M("Idle0", installs=0, impr=0),   # 활동 없음 → 제외
    ]
    aliases = {"ConnectBNR": "P-DA-Reward-gacha-01"}
    unmatched = inject_mmp_into_records(records, mmp, source_name="appsflyer", aliases=aliases)
    assert records[0].mmp_source == "appsflyer"   # 별칭 조인됨
    assert [u["concept"] for u in unmatched] == ["Rank1"]
    assert unmatched[0]["source"] == "mmp" and unmatched[0]["asset_types"] == []


def test_inject_mmp_empty_returns_list():
    from pipeline.main import inject_mmp_into_records
    assert inject_mmp_into_records([], [], aliases=None) == []
