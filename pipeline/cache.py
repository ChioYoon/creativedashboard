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

    def put(self, sha: str, prompt_version: str, payload: dict) -> None:
        self._data[self.make_key(sha, prompt_version)] = payload

    def stats(self) -> dict:
        return {"path": str(self.path), "entries": len(self._data)}
