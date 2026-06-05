"""
Gemini 2.5 Flash 태거.

흐름:
1. 대표 파일을 Gemini Files API에 업로드
2. PROCESSING 상태 폴링 (영상은 인코딩에 수십 초 소요)
3. ACTIVE 진입 후 structured output 호출 (response_schema = CreativeTag)
4. Pydantic으로 응답 검증

주의:
- 파일 업로드 quota: 20GB/일 (무료) — 충분
- generate_content quota: 분당 15회 (무료) — 자동 대기 처리
- thinking_budget=0 으로 토큰 효율 극대화
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types
from pydantic import ValidationError

from .schemas import CreativeTag

# 시스템 프롬프트 — 마케터 의도 역추적에 집중
SYSTEM_INSTRUCTION = """
귀하는 컴투스 R마케팅팀의 광고 소재 분석 에이전트입니다.

제공된 광고 자산의 초반 0~15초(영상) 또는 첫 인상(이미지) 영역을
엄밀히 판독하여, 다음 4가지 차원으로 분류합니다:

1. hooking_strategy — 후킹 기믹 1개 선택
2. core_usp — 가치 제안 1개 선택
3. visual_style — 아트 스타일 1개 선택
4. marketer_insight — 3단 서사 (한글, 200~400자)

마케터 인사이트 작성 규칙:
- 반드시 [전략적 의도], [타겟 심리], [성과 예측 및 변주] 3개 태그로 구획
- 각 태그는 줄바꿈 없이 한 단락으로 작성
- 플랫폼 지면 크기·화각 같은 뻔한 사설 금지
- 실제 기획 의도와 타겟 심리의 추론에 집중
- "신규 유저", "코어 유저" 같은 모호한 표현 대신 구체적 페르소나 묘사

응답은 반드시 JSON 형식이며 위 4개 필드만 포함합니다.
""".strip()

PROMPT_VERSION = "v1.0-2026.05.29"  # 변경 시 캐시 자동 무효화

# Files API 폴링 설정
POLL_INTERVAL_SEC = 4
POLL_TIMEOUT_SEC = 180

# generate_content rate limit (무료 분당 15회 → 안전 마진 두고 4초)
GENERATE_MIN_INTERVAL_SEC = 4.5


class GeminiTagger:
    """Gemini 2.5 Flash structured output 호출 래퍼."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self._last_call_at: float = 0.0

    # ──────────────────────────────────────────────────────────
    # Files API
    # ──────────────────────────────────────────────────────────
    def _upload_and_wait(self, file_path: Path):
        """파일 업로드 후 ACTIVE 상태까지 폴링."""
        uploaded = self.client.files.upload(file=str(file_path))
        started_at = time.time()
        while uploaded.state.name == "PROCESSING":
            if time.time() - started_at > POLL_TIMEOUT_SEC:
                raise TimeoutError(
                    f"Files API 처리 시간 초과 ({POLL_TIMEOUT_SEC}s): {file_path.name}"
                )
            time.sleep(POLL_INTERVAL_SEC)
            uploaded = self.client.files.get(name=uploaded.name)
        if uploaded.state.name != "ACTIVE":
            raise RuntimeError(
                f"Files API 상태 비정상: {uploaded.state.name} ({file_path.name})"
            )
        return uploaded

    # ──────────────────────────────────────────────────────────
    # generate_content (rate-limited)
    # ──────────────────────────────────────────────────────────
    def _respect_rate_limit(self) -> None:
        elapsed = time.time() - self._last_call_at
        if elapsed < GENERATE_MIN_INTERVAL_SEC:
            time.sleep(GENERATE_MIN_INTERVAL_SEC - elapsed)
        self._last_call_at = time.time()

    def tag_creative(self, file_path: Path) -> CreativeTag:
        """1개 미디어 파일을 4-compact taxonomy로 태깅.

        503/429 에러는 자동 재시도 (지수 백오프 + retry-after 존중).
        """
        asset = self._upload_and_wait(file_path)

        # 503(서버 일시 부하) / 429(rate limit) 자동 재시도
        # v1.0.1: 최대 3회, 지수 백오프 (5→15→45초)
        max_retries = 3
        last_exc = None
        for attempt in range(max_retries):
            self._respect_rate_limit()
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=[asset, SYSTEM_INSTRUCTION],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=CreativeTag,
                        temperature=0.2,
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                )
                break  # success
            except Exception as e:
                last_exc = e
                msg = str(e)
                # 503 UNAVAILABLE 또는 429 RESOURCE_EXHAUSTED만 재시도
                is_retryable = "503" in msg or "UNAVAILABLE" in msg or \
                               "429" in msg or "RESOURCE_EXHAUSTED" in msg
                if not is_retryable or attempt == max_retries - 1:
                    raise
                # retry-after 파싱 (Gemini가 retryDelay 제공 시)
                import re as _re
                delay_match = _re.search(r"retry[Dd]elay['\"]:\s*['\"](\d+)", msg)
                wait_sec = int(delay_match.group(1)) if delay_match else (5 * (3 ** attempt))
                # 일일 quota 한도(quotaValue: '20')는 재시도해도 무의미 — 즉시 중단
                if "GenerateRequestsPerDayPer" in msg:
                    raise
                print(f"   [재시도] {file_path.name}: {wait_sec}초 후 재시도 (attempt {attempt+2}/{max_retries})")
                time.sleep(wait_sec)
        else:
            raise last_exc

        try:
            return CreativeTag.model_validate_json(response.text)
        except ValidationError as e:
            raise RuntimeError(
                f"Gemini 응답이 스키마와 일치하지 않습니다 ({file_path.name}): {e}\n"
                f"원문: {response.text[:500]}"
            )


def prompt_version() -> str:
    """현재 프롬프트 버전 식별자 (캐시 키에 사용)."""
    return PROMPT_VERSION


def system_instruction() -> str:
    """디버깅용 — 시스템 프롬프트 노출."""
    return SYSTEM_INSTRUCTION
