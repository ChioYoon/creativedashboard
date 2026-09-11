"""pause_tool.mapping 순수 로직 검증(파일·API 무의존)."""
from pause_tool import mapping

CSV = "﻿소재명,유형,추천 사유\nP-Ingame-A,VID,피로\nP-Ingame-B,VID,저효율\nP-Ingame-A,VID,중복\n"

TITLE = {"creatives": [
    {"creative_id": "P-Ingame-A", "유형": "VID", "kpi_daily": [
        {"creative_name": "260807_VID_A_L", "asset_type": "YOUTUBE_VIDEO", "asset_id": "111"},
        {"creative_name": "260807_VID_A_S", "asset_type": "YOUTUBE_VIDEO", "asset_id": None},
        {"creative_name": "260807_BNR_A", "asset_type": "IMAGE", "asset_id": "999"},
        {"creative_name": "260807_VID_A_L", "asset_type": "YOUTUBE_VIDEO", "asset_id": "111"},  # 중복 이름
    ]},
    {"creative_id": "P-Ingame-B", "유형": "VID", "kpi_daily": []},
]}


def test_parse_csv_dedup_and_header():
    assert mapping.parse_reco_csv(CSV) == ["P-Ingame-A", "P-Ingame-B"]


def test_parse_csv_empty():
    assert mapping.parse_reco_csv("") == []


def test_expand_splits_video_image_and_dedups():
    ex = mapping.expand_assets(TITLE["creatives"][0])
    assert [v["name"] for v in ex["videos"]] == ["260807_VID_A_L", "260807_VID_A_S"]
    assert [v["name"] for v in ex["images"]] == ["260807_BNR_A"]


def test_build_candidates_asset_ids_and_names_split():
    cs = mapping.build_candidates(["P-Ingame-A", "P-Ingame-B", "P-Ghost"], TITLE)
    a, b, ghost = cs
    assert a["found"] and a["video_count"] == 2 and a["image_count"] == 1
    assert a["video_asset_ids"] == ["111"]          # asset_id 있는 것만
    assert a["video_names"] == ["260807_VID_A_S"]    # asset_id 없으면 이름 resolve 대상
    assert a["missing_asset_id"] == 1
    assert b["found"] and b["video_count"] == 0      # kpi_daily 없음 → 제거 대상 없음
    assert ghost["found"] is False                    # JSON에 없음


if __name__ == "__main__":
    for fn in list(globals().values()):
        if callable(fn) and getattr(fn, "__name__", "").startswith("test_"):
            fn()
    print("test_pause_tool_mapping OK")
