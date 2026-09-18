"""CLOOP JSON → BigQuery 병행 적재 (B안 decoupled exporter).

public/data/{title}.json(+_axis.json)을 읽어 BQ 4테이블에 파티션 교체로 적재.
파이프라인·대시보드 무변경. nightly git push 뒤 실행. 게이팅·격리·graceful.
"""
from __future__ import annotations

import argparse
import glob
import json as _json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from google.cloud import bigquery

log = logging.getLogger("bq_export")

DEFAULT_DATASET = "cloop"

_SF = bigquery.SchemaField

# 테이블별 BQ 스키마·파티션 필드·클러스터링 키
TABLE_SPECS: dict[str, dict] = {
    "kpi_daily": {
        "partition_field": "date",
        "clustering": ["title_id", "creative_name", "campaign_name"],
        "schema": [
            _SF("title_id", "STRING"), _SF("creative_name", "STRING"),
            _SF("date", "DATE"), _SF("source", "STRING"), _SF("customer_id", "STRING"),
            _SF("campaign_name", "STRING"), _SF("ad_group_name", "STRING"),
            _SF("asset_url", "STRING"), _SF("asset_type", "STRING"), _SF("asset_id", "STRING"),
            _SF("impressions", "INT64"), _SF("clicks", "INT64"),
            _SF("cost_micros", "INT64"), _SF("cost", "FLOAT64"),
            _SF("conversions", "FLOAT64"), _SF("conversions_value", "FLOAT64"),
            _SF("loaded_at", "TIMESTAMP"),
        ],
    },
    "mmp_daily": {
        "partition_field": "date",
        "clustering": ["title_id", "channel", "creative_name"],
        "schema": [
            _SF("title_id", "STRING"), _SF("creative_name", "STRING"),
            _SF("date", "DATE"), _SF("channel", "STRING"), _SF("campaign_name", "STRING"),
            _SF("impressions", "INT64"), _SF("clicks", "INT64"), _SF("cost", "INT64"),
            _SF("installs", "INT64"), _SF("retained_d1", "INT64"),
            _SF("revenue_d7", "INT64"), _SF("conversions", "INT64"),
            _SF("loaded_at", "TIMESTAMP"),
        ],
    },
    "creatives": {
        "partition_field": "snapshot_date",
        "clustering": ["title_id", "creative_name"],
        "schema": [
            _SF("title_id", "STRING"), _SF("snapshot_date", "DATE"),
            _SF("creative_name", "STRING"), _SF("creative_id", "STRING"),
            _SF("소재명", "STRING"), _SF("파일명", "STRING"), _SF("유형", "STRING"),
            _SF("creative_concept", "STRING"), _SF("theme_primary", "STRING"),
            _SF("theme_secondary", "STRING", mode="REPEATED"),
            _SF("theme_reviewed", "BOOL"), _SF("launch_date_variant", "BOOL"),
            _SF("theme_partner", "STRING"), _SF("intent_axis", "STRING"),
            _SF("theme_flags", "STRING", mode="REPEATED"), _SF("core_usp", "STRING"),
            _SF("hooking_strategy", "STRING"), _SF("art_style", "STRING"),
            _SF("player_motivation", "STRING"), _SF("color_tone", "STRING"),
            _SF("cta_type", "STRING"), _SF("one_line_insight", "STRING"),
            _SF("loaded_at", "TIMESTAMP"),
        ],
    },
    "axis": {
        "partition_field": "snapshot_date",
        "clustering": ["title_id", "axis"],
        "schema": [
            _SF("title_id", "STRING"), _SF("snapshot_date", "DATE"),
            _SF("stage", "STRING"), _SF("axis", "STRING"), _SF("status", "STRING"),
            _SF("n", "INT64"), _SF("cost", "INT64"),
            _SF("ipm", "FLOAT64"), _SF("cvr", "FLOAT64"), _SF("roas7", "FLOAT64"),
            _SF("ga_roas", "FLOAT64"), _SF("delta_ipm_pct", "FLOAT64"),
            _SF("reason", "STRING"), _SF("period_from", "STRING"), _SF("period_to", "STRING"),
            _SF("loaded_at", "TIMESTAMP"),
        ],
    },
}


def partition_range(rows: list[dict], field: str) -> tuple[str, str] | None:
    """행들의 field 값 min..max. 빈 리스트/빈 값 없으면 None."""
    vals = [r[field] for r in rows if r.get(field)]
    if not vals:
        return None
    return (min(vals), max(vals))


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


def replace_partition(client, dataset: str, table: str, rows: list[dict],
                       *, dry_run: bool = False) -> dict:
    """파티션 교체: 행 date/snapshot_date 범위 파티션 삭제 후 재삽입.
    DELETE는 load 직전, 빈 rows면 무동작. client는 주입(테스트 fake 가능)."""
    spec = TABLE_SPECS[table]
    field = spec["partition_field"]
    rng = partition_range(rows, field)
    if rng is None:
        return {"table": table, "deleted_range": None, "loaded": 0}
    if dry_run:
        return {"table": table, "deleted_range": rng, "loaded": len(rows)}
    lo, hi = rng
    table_ref = f"{dataset}.{table}"
    # 테이블은 여러 타이틀이 공유 → title_id 없이 날짜만 지우면 같은 창의
    # 다른 타이틀 행까지 삭제됨(타이틀별 순차 호출 시 이전 타이틀 데이터 소실).
    # rows에 있는 title_id만 골라 IN 절로 격리.
    tids = sorted({r["title_id"] for r in rows if r.get("title_id")})
    del_sql = (f"DELETE FROM `{table_ref}` "
               f"WHERE {field} BETWEEN DATE('{lo}') AND DATE('{hi}')")
    if tids:
        tid_list = ",".join(f"'{t}'" for t in tids)
        del_sql += f" AND title_id IN ({tid_list})"
    client.query(del_sql).result()
    client.load_table_from_json(rows, table_ref).result()
    return {"table": table, "deleted_range": rng, "loaded": len(rows)}


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


# 테이블명 → (dataset, axis, title_id, loaded_at)에서 행을 뽑는 함수
_TABLE_ROWS = {
    "kpi_daily": lambda ds, ax, tid, la: rows_kpi_daily(ds, la),
    "mmp_daily": lambda ds, ax, tid, la: rows_mmp_daily(ds, la),
    "creatives": lambda ds, ax, tid, la: rows_creatives(ds, la),
    "axis": lambda ds, ax, tid, la: rows_axis(ax, tid, la) if ax else [],
}


def ensure_table(client, dataset: str, table: str) -> None:
    """데이터셋·테이블 멱등 생성(파티션·클러스터). client는 주입(테스트 fake 가능)."""
    spec = TABLE_SPECS[table]
    ds_ref = bigquery.Dataset(f"{client.project}.{dataset}")
    client.create_dataset(ds_ref, exists_ok=True)
    t = bigquery.Table(f"{client.project}.{dataset}.{table}", schema=spec["schema"])
    t.time_partitioning = bigquery.TimePartitioning(field=spec["partition_field"])
    t.clustering_fields = spec["clustering"]
    client.create_table(t, exists_ok=True)


def export_title(client, dataset: str, title_id: str, data_dir: str,
                  loaded_at: str, *, dry_run: bool = False) -> list[dict]:
    """한 타이틀의 {title}.json(+{title}_axis.json)을 읽어 4테이블 replace_partition.
    테이블별 독립 try/except — 하나 실패가 나머지 테이블을 막지 않음."""
    p = Path(data_dir)
    ds_path = p / f"{title_id}.json"
    if not ds_path.exists():
        log.warning("bq_export: %s 없음 — 스킵", ds_path)
        return []
    ax_path = p / f"{title_id}_axis.json"
    try:
        ds = _json.loads(ds_path.read_text(encoding="utf-8"))
        ax = _json.loads(ax_path.read_text(encoding="utf-8")) if ax_path.exists() else None
    except Exception as e:  # 손상된 JSON도 격리 — 이 타이틀만 실패 처리, main() 루프는 계속
        log.error("bq_export: %s JSON 로드 실패: %s", title_id, e)
        return [{"table": "_load", "error": str(e)}]
    results = []
    for table, rowfn in _TABLE_ROWS.items():
        try:
            rows = rowfn(ds, ax, title_id, loaded_at)
            if not dry_run:
                ensure_table(client, dataset, table)
            results.append(replace_partition(client, dataset, table, rows, dry_run=dry_run))
        except Exception as e:  # 테이블 격리 — 하나 실패가 나머지 막지 않음
            log.error("bq_export: %s.%s 실패: %s", title_id, table, e)
            results.append({"table": table, "error": str(e)})
    return results


def _title_ids(data_dir: str) -> list[str]:
    """public/data 디렉터리에서 타이틀 목록 스캔(*_axis.json·*.pilot.json 제외)."""
    out = []
    for f in glob.glob(str(Path(data_dir) / "*.json")):
        name = Path(f).name
        if name.endswith("_axis.json") or name.endswith(".pilot.json"):
            continue
        out.append(name[:-5])  # ".json" 제거
    return sorted(out)


def main(argv=None) -> int:
    """CLOOP JSON → BigQuery 적재 CLI. load_bq_config로 게이팅, 비활성이면 graceful 스킵."""
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser(description="CLOOP JSON → BigQuery 적재")
    ap.add_argument("--all-titles", action="store_true")
    ap.add_argument("--title", default="")
    ap.add_argument("--data-dir", default="public/data")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    cfg = load_bq_config()
    if cfg is None:
        log.info("bq_export: 비활성(BQ_EXPORT_ENABLED≠1 또는 키 부재) — 스킵")
        return 0

    client = bigquery.Client.from_service_account_json(
        cfg["credentials_path"], project=cfg["project"])
    loaded_at = datetime.now(timezone.utc).isoformat()
    titles = _title_ids(args.data_dir) if args.all_titles else (
        [args.title] if args.title else [])
    if not titles:
        log.warning("bq_export: 대상 타이틀 없음")
        return 0
    for tid in titles:
        try:
            res = export_title(client, cfg["dataset"], tid, args.data_dir, loaded_at,
                                dry_run=args.dry_run)
            log.info("bq_export %s: %s", tid, res)
        except Exception as e:  # 타이틀 격리 — 하나가 예외로 죽어도 나머지 타이틀은 계속
            log.error("bq_export: %s 처리 중 예기치 않은 오류: %s", tid, e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
