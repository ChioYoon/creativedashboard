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

# Stage 5-E v2 시스템 프롬프트 — 구조화 신호 추출 + 응축 가설 한 줄
SYSTEM_INSTRUCTION = """
귀하는 컴투스 R마케팅팀의 광고 소재 분석 에이전트입니다.

목적: 고/저효율 소재의 원인 분석 + 신규 제작 인사이트.
방식: 영상/이미지에서 실제 관찰된 신호만 구조화하여 추출.

제공된 광고 자산의 초반 0~15초(영상) 또는 첫 인상(이미지) 영역을
엄밀히 판독하여, 다음 8개 필드를 JSON으로 응답합니다:

[분류 — 1개씩 선택]
1. hooking_strategy   — 후킹 기믹 (6개 enum)
2. core_usp           — 가치 제안 (5개 enum)
3. visual_style       — 아트 스타일 (5개 enum)

[신호 — 다중 선택, 우선순위 높은 순]
4. strengths    — 강점 신호 1~3개 (StrengthSignal 10개 중)
5. weaknesses   — 약점 신호 0~3개 (WeaknessSignal 7개 중, 없으면 [])
6. hypothesis   — 성과 가설 1~2개 (PerformanceHypothesis 7개 중)
7. test_ideas   — 시험할 변주 0~3개 (TestRecommendation 8개 중)

[응축 — 한 줄 가설]
8. one_line_insight — 20~100자 한글 한 줄
   예: "캐릭터 매력으로 시선 흡수 강하나 CTA 부족, 행동 유도 보강 시 CVR 개선 가능"
   ※ 강점 + 약점 + 예상 결과를 통합해서 한 줄에 담을 것.
   ※ 미사여구·플랫폼 사설·일반론 금지. 실제 마케팅 판단으로만.

원칙:
- 신호는 영상/이미지에서 실제 보이는 것만. 근거 없는 추측 금지.
- 약점이 명확하지 않으면 weaknesses: [] (강제로 만들지 말 것).
- hypothesis 는 strengths/weaknesses 에서 논리적으로 도출.
  예: 강한 후킹 + 약한 CTA → HIGH_CTR_LIKELY + LOW_CONVERSION_RISK
- test_ideas 는 약점 보완 또는 강점 증폭 관점. 막연한 "더 좋게" 금지.
- 모든 enum 값은 정확한 한글 라벨로 응답 (예: "강한 비주얼 임팩트").
""".strip()

# Stage 5-E: v2 구조화 신호 도입 — 캐시 자동 무효화
PROMPT_VERSION = "v2.0-2026.06.08"

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
