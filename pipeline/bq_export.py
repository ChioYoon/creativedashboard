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
