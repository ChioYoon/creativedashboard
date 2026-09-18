"""CLOOP JSON → BigQuery 병행 적재 (B안 decoupled exporter).

public/data/{title}.json(+_axis.json)을 읽어 BQ 4테이블에 파티션 교체로 적재.
파이프라인·대시보드 무변경. nightly git push 뒤 실행. 게이팅·격리·graceful.
"""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_DATASET = "cloop"


def load_bq_config(env: dict | None = None) -> dict | None:
    """env → BQ 설정 dict. 비활성/키부재면 None(스킵). 순수(파일 존재만 확인).

    Args:
        env: 환경 변수 dict. None이면 os.environ 사용.

    Returns:
        설정 dict (project, dataset, credentials_path) 또는 스킵 신호로 None.
        - BQ_EXPORT_ENABLED != "1" → None
        - GOOGLE_APPLICATION_CREDENTIALS 경로 없음/미존재 → None
        - BQ_PROJECT 비어있음 → None
    """
    e = env if env is not None else os.environ
    if (e.get("BQ_EXPORT_ENABLED") or "") != "1":
        return None
    creds = e.get("GOOGLE_APPLICATION_CREDENTIALS") or ""
    if not creds or not Path(creds).exists():
        return None
    project = e.get("BQ_PROJECT") or ""
    if not project:
        return None
    return {
        "project": project,
        "dataset": e.get("BQ_DATASET") or DEFAULT_DATASET,
        "credentials_path": creds,
    }


def _snapshot_date(dataset_or_axis: dict) -> str:
    """generated_at(ISO)에서 날짜(YYYY-MM-DD)만."""
    g = dataset_or_axis.get("generated_at") or ""
    return g[:10] if len(g) >= 10 else ""


def rows_kpi_daily(dataset: dict, loaded_at: str) -> list[dict]:
    """소재별 kpi_daily(Google Ads)를 독립 행으로 평탄화."""
    tid = dataset.get("title_id", "")
    out = []
    for c in dataset.get("creatives", []) or []:
        for k in c.get("kpi_daily", []) or []:
            out.append({
                "title_id": tid,
                "creative_name": k.get("creative_name", ""),
                "date": k.get("date", ""),
                "source": k.get("source", ""),
                "customer_id": k.get("customer_id", ""),
                "campaign_name": k.get("campaign_name", ""),
                "ad_group_name": k.get("ad_group_name", ""),
                "asset_url": k.get("asset_url"),
                "asset_type": k.get("asset_type"),
                "asset_id": k.get("asset_id"),
                "impressions": k.get("impressions", 0),
                "clicks": k.get("clicks", 0),
                "cost_micros": k.get("cost_micros", 0),
                "cost": k.get("cost", 0.0),
                "conversions": k.get("conversions", 0.0),
                "conversions_value": k.get("conversions_value", 0.0),
                "loaded_at": loaded_at,
            })
    return out


def rows_mmp_daily(dataset: dict, loaded_at: str) -> list[dict]:
    """소재별 mmp_daily(Airbridge/AppsFlyer)를 독립 행으로 평탄화."""
    tid = dataset.get("title_id", "")
    out = []
    for c in dataset.get("creatives", []) or []:
        for m in c.get("mmp_daily", []) or []:
            out.append({
                "title_id": tid,
                "creative_name": m.get("creative_name", ""),
                "date": m.get("date", ""),
                "channel": m.get("channel", ""),
                "campaign_name": m.get("campaign_name", ""),
                "impressions": m.get("impressions", 0),
                "clicks": m.get("clicks", 0),
                "cost": m.get("cost", 0),
                "installs": m.get("installs", 0),
                "retained_d1": m.get("retained_d1", 0),
                "revenue_d7": m.get("revenue_d7", 0),
                "conversions": m.get("conversions", 0),
                "loaded_at": loaded_at,
            })
    return out


# creatives 스냅샷 태그 컬럼(성과 제외)
_CREATIVE_COLS = [
    "creative_id", "소재명", "파일명", "유형", "creative_concept",
    "theme_primary", "theme_reviewed", "launch_date_variant", "theme_partner",
    "intent_axis", "hooking_strategy", "art_style", "player_motivation",
    "color_tone", "cta_type", "one_line_insight",
]


def rows_creatives(dataset: dict, loaded_at: str) -> list[dict]:
    """소재 태그 스냅샷(성과 제외)을 행으로 변환. snapshot_date=generated_at 날짜."""
    tid = dataset.get("title_id", "")
    snap = _snapshot_date(dataset)
    out = []
    for c in dataset.get("creatives", []) or []:
        row = {"title_id": tid, "snapshot_date": snap, "loaded_at": loaded_at,
               "creative_name": c.get("소재명") or c.get("creative_id", "")}
        for col in _CREATIVE_COLS:
            row[col] = c.get(col)
        # 리스트 필드는 REPEATED로 별도 보존
        row["theme_secondary"] = list(c.get("theme_secondary", []) or [])
        row["theme_flags"] = list(c.get("theme_flags", []) or [])
        row["core_usp"] = c.get("USP")  # 스키마상 USP alias → core_usp 컬럼
        out.append(row)
    return out


def rows_axis(axis: dict, title_id: str, loaded_at: str) -> list[dict]:
    """stages.L/P를 stage 컬럼으로 평탄화. snapshot_date=generated_at 날짜."""
    snap = _snapshot_date(axis)
    period = axis.get("period", {}) or {}
    out = []
    for stage, arr in (axis.get("stages", {}) or {}).items():
        for a in arr or []:
            delta = a.get("delta", {}) or {}
            out.append({
                "title_id": title_id,
                "snapshot_date": snap,
                "stage": stage,
                "axis": a.get("axis", ""),
                "status": a.get("status", ""),
                "n": a.get("n", 0),
                "cost": a.get("cost", 0),
                "ipm": a.get("ipm"),
                "cvr": a.get("cvr"),
                "roas7": a.get("roas7"),
                "ga_roas": a.get("ga_roas"),
                "delta_ipm_pct": delta.get("ipm_pct"),
                "reason": a.get("reason", ""),
                "period_from": period.get("from", ""),
                "period_to": period.get("to", ""),
                "loaded_at": loaded_at,
            })
    return out
