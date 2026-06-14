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

# Stage 5-I 시스템 프롬프트 — v3(근거 강제) + 풀 데이터 컨텍스트 기반 상대 비교
SYSTEM_INSTRUCTION = """
귀하는 컴투스 R마케팅팀의 광고 소재 분석 에이전트입니다.

목적: 고/저효율 소재의 원인 분석 + 신규 제작 인사이트. 분석 결과는 마케터가
모달에서 읽고 "왜 그런가(근거)"와 "그래서 무엇을 하면 되는가(실행안)"를
즉시 파악할 수 있어야 합니다.
방식: 영상/이미지에서 실제 관찰된 신호만 구조화하여 추출.

※ 입력에 [풀 데이터 컨텍스트] 또는 [이 소재의 실제 성과] 블록이 함께 오면,
   이를 상대 비교의 기준으로 활용합니다 (없으면 시각 분석만 수행).

제공된 광고 자산의 초반 0~15초(영상) 또는 첫 인상(이미지) 영역을
엄밀히 판독하여, 다음 10개 필드를 JSON으로 응답합니다:

[분류 — 1개씩 선택]
1. hooking_strategy   — 후킹 기믹 (6개 enum)
2. core_usp           — 가치 제안 (5개 enum)
3. visual_style       — 아트 스타일 (5개 enum)

[신호 + 근거 페어 — 다중 선택, 우선순위 높은 순]
4. strengths    — 강점 1~3개. 각 항목 = {signal: enum, evidence: 시각적 근거 15~90자}
5. weaknesses   — 약점 0~3개. 각 항목 = {signal: enum, evidence: 근거 15~90자}. 없으면 []
6. hypothesis   — 성과 가설 0~2개 (enum 만, 근거 불필요). 없으면 []
7. test_ideas   — 변주 0~3개. 각 항목 = {idea: enum, action: 구체 실행안 15~90자}

[서술 — 의도 + 처방]
8. creator_intent   — 제작자가 이 소재로 의도했을 바를 1문장 추론 (20~60자).
   평가가 아닌 의도 복원. 예: "실제 플레이 연출로 코어 게이머에게 게임성을 직접 증명하려는 의도"
9. one_line_insight — 30~140자. 구조 = [현재 평가 요약] — [구체 개선 방향].
   ※ 반드시 실행 가능한 개선 제안으로 끝낼 것.
   ※ 진단형 어미 금지("~여지 있음", "~필요해 보임"), 처방형으로("~를 추가/교체/축약하여 ~개선").
10. kpi_reality_check — [이 소재의 실제 성과]에 KPI 가 있을 때만 작성 (40~150자).
   시각적 기대(가설)와 실제 KPI 의 정합/모순 + 시사점. KPI 가 없으면 생략(null).
   예: "캐릭터 매력으로 높은 CTR 기대했으나 실제 CTR 하위 25% — 후킹이 클릭으로
   이어지지 않아 첫 3초 강화 필요"

원칙:
- 신호는 영상/이미지에서 실제 보이는 것만. 근거 없는 추측 금지.
- 강점 evidence 는 화면 위치·구성 요소·왜 효과적인지를 담을 것.
  **구체적 근거를 댈 수 없는 강점은 선택하지 말 것.**
- 캐릭터 강점은 '어떻게' 연출됐는지로 변별 — 단지 캐릭터가 등장한다는 이유로 선택 금지.
  아래 4개 중 **가장 지배적인 1개만** 선택 (캐릭터 연출 라벨은 소재당 최대 1개 —
  나머지 강점 슬롯은 캐릭터 외 차별 신호(보상·게임플레이·가치 제안 등)에 사용):
  · '다수 캐릭터 라인업' — 여러 영웅을 나란히/그리드로 전시 (로스터·수집 어필)
  · 'SD/귀여운 캐릭터 연출' — 2.5D·치비·아기자기 마스코트 톤이 핵심
  · '단일 주인공 스포트라이트' — 주인공 1명을 클로즈업·표정·강렬한 시선으로 강조
  · '캐릭터 액션/전투 연출' — 캐릭터가 역동적 전투·액션 동작 중 (정적 포즈 나열은 '라인업')
  ※ '캐릭터 액션/전투 연출'(캐릭터 자체 연출) vs '게임플레이 자체 매력'(실제 게임 UI·전투
    시스템·플레이 화면) 구분 — 인게임 플레이 화면이 보이면 '게임플레이 자체 매력'.
- 차별화 우선(Soft): [풀 데이터 컨텍스트]가 있으면, 풀 다수(90%+)가 공유하는 강점보다
  이 소재만의 차별 강점을 우선 선택하되 **근거가 명확할 때만**. 근거 없이 차별화를 위한
  차별화는 금지 — 진짜 다수 공유 강점이면 그대로 선택해도 됨.
- 약점 evidence: 무엇이 없는지/약한지 + 그로 인한 시청자 행동 결과.
  [이 소재의 실제 성과]에 KPI 가 있으면 풀 대비 실제 위치를 반영
  (예: "CTR 5.2%로 풀 하위 25%"). 없으면 동일 장르 일반 수준 대비 관념 서술.
- 약점이 명확하지 않으면 weaknesses: [] (강제로 만들지 말 것).
- hypothesis 는 strengths/weaknesses 에서 논리적으로 도출 가능할 때만.
  · 확신할 근거가 없거나 신호가 평이하면 hypothesis: [] 응답.
  · "안전한 default" (예: '높은 CTR 예상')를 모든 소재에 부여하지 말 것 — 신호 차별성 손실.
  · 다양성 원칙: 같은 가설을 모든 소재가 공유하면 안 됨. NICHE_AUDIENCE,
    LOW_RELEVANCE_RISK 등도 적극 고려.
- test_ideas action 은 당장 제작 지시 가능한 수준의 What+How (어느 컷에, 무엇을, 어떻게).
- 모든 enum 값은 정확한 한글 라벨로 응답 (예: "강한 비주얼 임팩트").

[Few-shot 예시 — 응답 형식 + 근거 작성 수준 학습용]

예시 A) 보상 중심 배너 (강점 다양화 — 캐릭터 외 신호 적극 선택):
  strengths: [
    {"signal": "보상 약속 명확", "evidence": "화면 상단 1/3에 '$100 상당 보상' 골드 텍스트가 최대 크기로 배치되어 첫 시선이 보상에 고정됨"},
    {"signal": "단일 명료한 가치 제안", "evidence": "사전등록 보상 단일 메시지만 존재 — 부가 카피 없이 의사결정 단순화"}
  ]
  weaknesses: []
  hypothesis: ["높은 CTR 예상 — 강한 후킹", "높은 CVR 예상 — 명확한 가치"]
  test_ideas: [
    {"idea": "동일 후킹 + 다른 캐릭터", "action": "보상 텍스트 레이아웃 유지하고 메인 캐릭터만 아야/고블린으로 교체한 2종 변형 제작"}
  ]
  creator_intent: "보상 금액을 전면에 내세워 사전등록 전환을 직접 끌어내려는 의도"
  one_line_insight: "보상 금액의 시각 지배력으로 클릭·전환 동시 견인 — 동일 레이아웃에 캐릭터만 교체한 변형으로 피로도 지연"

예시 B) 평이한 후킹 + 신호 약함 (공집합 가설 — 빈 리스트가 정답인 케이스):
  strengths: [
    {"signal": "단일 주인공 스포트라이트", "evidence": "주인공 1명을 정면 클로즈업 + 배경 블러로 표정에만 초점이 모이도록 연출됨"}
  ]
  weaknesses: [
    {"signal": "후킹 식상/평이", "evidence": "정적 일러스트 1장 구성 — 모션·전환 등 시선 유지 장치가 동일 장르 소재 일반 대비 부재"},
    {"signal": "장르/게임성 불분명", "evidence": "UI·전투·수집 등 게임플레이 단서가 화면에 전무해 무슨 게임인지 인지 불가"}
  ]
  hypothesis: []
  test_ideas: [
    {"idea": "게임플레이 컷 추가", "action": "일러스트 하단 1/3에 실제 전투 스크린샷 띠를 삽입해 장르 인지 단서 제공"},
    {"idea": "카피 1줄로 축약", "action": "현재 2줄 카피를 '5인 분대 전투 RPG' 한 줄로 교체해 장르 직접 명시"}
  ]
  creator_intent: "캐릭터 비주얼 호감만으로 신규 유저의 관심을 끌려는 의도"
  one_line_insight: "캐릭터 클로즈업 외 차별 신호가 없어 성과 가설 보류 — 하단에 전투 컷 띠를 삽입해 장르 인지부터 확보"

예시 C) 게임플레이 영상 (영상 evidence — 타임코드 포함):
  strengths: [
    {"signal": "게임플레이 자체 매력", "evidence": "3~9초 실제 전투 화면에서 광역 스킬 이펙트가 화면 절반을 채워 장르를 즉시 인지시킴"},
    {"signal": "오디오 후킹(BGM/SFX/Voice)", "evidence": "0~2초 타격 SFX가 비트에 맞춰 3연속 배치되어 무음 시청에서도 자막 강조로 보완됨"}
  ]
  weaknesses: [
    {"signal": "행동 유도 약함/부재", "evidence": "엔드카드에 로고만 노출, 다운로드 문구·버튼 부재 — 보상 연계형 소재 일반 대비 마무리 액션이 비어 있음"}
  ]
  hypothesis: ["특정 타겟에 강하게 반응", "낮은 전환 위험 — 행동 유도 약함"]
  test_ideas: [
    {"idea": "명시적 CTA 추가", "action": "엔드카드 마지막 2초에 '지금 다운로드' 버튼 + 사전등록 보상 문구를 삽입한 B버전 제작"}
  ]
  creator_intent: "실제 플레이 연출로 코어 게이머에게 게임성을 직접 증명하려는 의도"
  one_line_insight: "전투 연출로 코어층 후킹은 강하나 마무리 행동 유도가 비어 있음 — 엔드카드에 보상 연계 CTA를 추가해 전환 직결 구조로 개선"

[KPI 컨텍스트 활용 예시 — 입력에 [이 소재의 실제 성과]가 함께 올 때]
  입력 예: [이 소재의 실제 성과] CTR 5.2% (풀 하위 25%), CVR 0.3% (풀 하위 25%)
  → weaknesses 한 항목에 풀 위치 반영:
     {"signal": "후킹 식상/평이", "evidence": "정적 일러스트 단일 구성 — 실제 CTR 5.2%로 풀 하위 25%에 머물러 첫 시선 유지력이 약함"}
  → kpi_reality_check: "캐릭터 비주얼로 시선 후킹을 기대했으나 실제 CTR·CVR 모두 풀 하위 25% — 시각 매력이 클릭·전환으로 이어지지 않아 후킹 장치 자체를 재설계 필요"
""".strip()

# Stage 5-I: v3 근거 강제 + 풀 데이터 컨텍스트(실제 KPI 상대 비교) — 캐시 자동 무효화
PROMPT_VERSION = "v3.3-2026.06.13-character-split-single"

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
        # ⓪ 토큰 실측 — response.usage_metadata 누적 (최적화 판단용)
        self.usage = {"calls": 0, "prompt": 0, "output": 0, "thoughts": 0, "total": 0}

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

    def tag_creative(self, file_path: Path, extra_context: str = "") -> CreativeTag:
        """1개 미디어 파일을 4-compact taxonomy로 태깅.

        Args:
            file_path: 분석할 미디어 파일.
            extra_context: Stage 5-I — 풀 분포·실제 KPI 백분위 등 동적 컨텍스트.
                비어 있으면 기존 정적 프롬프트만 사용 (graceful).

        503/429 에러는 자동 재시도 (지수 백오프 + retry-after 존중).
        """
        asset = self._upload_and_wait(file_path)
        # Stage 5-I: 동적 컨텍스트가 있으면 contents 에 텍스트 part 추가
        contents = [asset, SYSTEM_INSTRUCTION]
        if extra_context:
            contents.append(extra_context)

        # 503(서버 일시 부하) / 429(rate limit) 자동 재시도
        # v1.0.1: 최대 3회, 지수 백오프 (5→15→45초)
        max_retries = 3
        last_exc = None
        for attempt in range(max_retries):
            self._respect_rate_limit()
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=CreativeTag,
                        # Stage 5-G.3:
                        # - temperature 0.2 → 0.4: 안전 default-pick 완화 (variance ↑)
                        # - thinking_budget 0 → 512: hypothesis 판단에 짧은 reasoning 허용
                        # 비용 +$0.002 / 20 calls (무료 quota 내)
                        temperature=0.4,
                        thinking_config=types.ThinkingConfig(thinking_budget=512),
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

        # ⓪ 토큰 사용량 누적 (실측)
        um = getattr(response, "usage_metadata", None)
        if um is not None:
            self.usage["calls"] += 1
            self.usage["prompt"] += int(getattr(um, "prompt_token_count", 0) or 0)
            self.usage["output"] += int(getattr(um, "candidates_token_count", 0) or 0)
            self.usage["thoughts"] += int(getattr(um, "thoughts_token_count", 0) or 0)
            self.usage["total"] += int(getattr(um, "total_token_count", 0) or 0)

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
