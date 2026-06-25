"""
SHA-256 기반 태깅 결과 캐시.

목적:
- 동일 파일 재태깅 방지 → Gemini API 비용·시간 절감
- 파일 내용 변경 시 자동으로 재태깅 (해시가 바뀌므로)
- 프롬프트 버전이 바뀌면 캐시 자동 무효화

캐시 키 = sha256(파일 바이트) + ":" + prompt_version
캐시 값 = CreativeTag (Pydantic 모델) 의 JSON 직렬화

저장소: 로컬 JSON 파일 (cache/{title_id}_tags.json)
- Stage 7 진입 시 Firestore로 마이그레이션 검토.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

CHUNK_SIZE = 1024 * 1024  # 1 MiB


def file_sha256(path: Path) -> str:
    """파일 바이트의 SHA-256 해시(64자 hex). 큰 영상도 청크 단위로 처리."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


class TagCache:
    """타이틀별 태깅 결과 캐시 (단일 JSON 파일)."""

    def __init__(self, cache_dir: Path, title_id: str):
        self.path = Path(cache_dir) / f"{title_id}_tags.json"
        self._data: dict[str, dict] = {}
        self._load()

    # ─── I/O ───
    def _load(self) -> None:
        if not self.path.exists():
            self._data = {}
            return
        try:
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  [캐시 경고] {self.path} 읽기 실패 ({e}). 새로 시작합니다.")
            self._data = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ─── API ───
    @staticmethod
    def make_key(sha: str, prompt_version: str) -> str:
        return f"{sha}::{prompt_version}"

    def get(self, sha: str, prompt_version: str) -> Optional[dict]:
        """캐시 히트 시 저장된 dict 반환 (Pydantic.model_dump 결과). 미스 시 None."""
        return self._data.get(self.make_key(sha, prompt_version))

    def get_any(
        self, sha: str, exclude_version: Optional[str] = None
    ) -> Optional[tuple[dict, str]]:
        """같은 파일(sha)의 이전 버전 태그 폴백 (carry-forward 용).
        non-pilot 버전 중 버전 문자열 lexical max(≈최신) 반환. 없으면 None.
        """
        prefix = f"{sha}::"
        best_ver: Optional[str] = None
        best_payload: Optional[dict] = None
        for key, payload in self._data.items():
            if not key.startswith(prefix):
                continue
            ver = key[len(prefix):]
            if ver.endswith("-pilot"):
                continue
            if exclude_version is not None and ver == exclude_version:
                continue
            if best_ver is None or ver > best_ver:
                best_ver, best_payload = ver, payload
        if best_ver is None:
            return None
        return (best_payload, best_ver)

    def put(self, sha: str, prompt_version: str, payload: dict) -> None:
        self._data[self.make_key(sha, prompt_version)] = payload

    def stats(self) -> dict:
        return {"path": str(self.path), "entries": len(self._data)}


# ─────────────────────────────────────────────────────────────
# Stage 5: KPI 캐시 — 매체별 일별 성과 지표 캐싱
# ─────────────────────────────────────────────────────────────
class KpiCache:
    """타이틀별 KPI 결과 캐시 (단일 JSON 파일).

    설계 — TagCache와 다른 점:
    - 키: (source, customer_id, creative_name, date) 4-tuple
    - 가변성: 매일 갱신 (Google Ads 데이터는 24~48h 내 retroactive 정정 가능)
    - TTL: 35일 (28일 윈도우 + 7일 마진) — 자동 정리

    파일 위치: cache/{title_id}_kpi.json
    포맷:
        {
          "google_ads::1234567890::A-AI-X::2026-06-04": {
            "impressions": 12345, "clicks": 100, "cost_micros": 50000,
            "cost": 0.05, "conversions": 2.0, "conversions_value": 1.5,
            "_cached_at": "2026-06-05T13:00:00+09:00"
          },
          ...
        }

    사용 패턴 (main.py):
        cache = KpiCache(cfg["cache_dir"], cfg["title"])
        cache.purge_old(ttl_days=35)
        # 신선한 KPI는 API에서 가져오고, 캐시는 백업/오프라인 분석용
        for daily in fetched_kpis:
            cache.put(daily)
        cache.save()
    """

    DEFAULT_TTL_DAYS = 35

    def __init__(self, cache_dir: Path, title_id: str):
        self.path = Path(cache_dir) / f"{title_id}_kpi.json"
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self._data = {}
            return
        try:
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  [KPI 캐시 경고] {self.path} 읽기 실패 ({e}). 새로 시작.")
            self._data = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def make_key(source: str, customer_id: str, creative_name: str, date: str) -> str:
        return f"{source}::{customer_id}::{creative_name}::{date}"

    def get(
        self, source: str, customer_id: str, creative_name: str, date: str
    ) -> Optional[dict]:
        return self._data.get(self.make_key(source, customer_id, creative_name, date))

    def put(self, daily_payload: dict, source: str, customer_id: str) -> None:
        """daily_payload는 CreativeKpiDaily.model_dump() 결과 dict 가정.

        cached_at 필드를 자동 추가해 TTL 회전에 사용.
        """
        from datetime import datetime, timezone, timedelta

        kst = timezone(timedelta(hours=9))
        creative_name = daily_payload["creative_name"]
        date_str = daily_payload["date"]
        key = self.make_key(source, customer_id, creative_name, date_str)
        payload_with_meta = dict(daily_payload)
        payload_with_meta["_cached_at"] = datetime.now(kst).isoformat(timespec="seconds")
        self._data[key] = payload_with_meta

    def purge_old(self, ttl_days: int = DEFAULT_TTL_DAYS) -> int:
        """TTL 초과 엔트리 삭제. 반환: 삭제된 엔트리 수."""
        from datetime import datetime, timezone, timedelta

        kst = timezone(timedelta(hours=9))
        cutoff = datetime.now(kst) - timedelta(days=ttl_days)
        removed = 0
        for key in list(self._data.keys()):
            cached_at_str = self._data[key].get("_cached_at")
            if not cached_at_str:
                continue
            try:
                cached_at = datetime.fromisoformat(cached_at_str)
                if cached_at < cutoff:
                    del self._data[key]
                    removed += 1
            except Exception:
                pass
        return removed

    def stats(self) -> dict:
        return {"path": str(self.path), "entries": len(self._data)}
