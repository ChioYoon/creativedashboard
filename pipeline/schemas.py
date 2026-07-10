"""
Pydantic 모델 — Stage 5-E (v2 구조화 taxonomy).

Stage 2 MVP 4-compact + Stage 5-E 신호 기반 구조화:
  1. 후킹 전략 (Hooking Strategy) — 6개 enum (기존)
  2. 핵심 메시지 소구 (Core USP) — 5개 enum (기존)
  3. 비주얼/아트 스타일 (Visual/Art Style) — 5개 enum (기존)
  4. 강점 신호 (Strength Signals) — 10개 enum, 1-3개 다중 선택 (신규)
  5. 약점 신호 (Weakness Signals) — 7개 enum, 0-3개 다중 선택 (신규)
  6. 성과 가설 (Performance Hypothesis) — 7개 enum, 1-2개 다중 선택 (신규)
  7. 테스트 변주 (Test Recommendations) — 8개 enum, 0-3개 다중 선택 (신규)
  8. one_line_insight — 100자 미만 응축 가설 (서술형 593자 → 80자 평균, -86%)

목적:
- 고/저효율 소재의 원인 분석을 자동 집계 가능하게 함 (KPI cross-tab)
- 신규 제작 시 시험할 변주를 데이터로 추출 (test_ideas Top N)
- Gemini 응답 토큰 약 73% 절감 (425 → 113 토큰/소재)

산출 JSON 스키마 v2 — js/data-source.js의 normalizeFromJson() 과 호환.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ─────────────────────────────────────────────────────────────
# 1. 4-compact taxonomy enums
# ─────────────────────────────────────────────────────────────
class HookingStrategy(str, Enum):
    """초반 0~15초 후킹 기믹 분류."""

    FAILURE_ANGER = "실패/분노 유도"
    CHARACTER_LOOK = "캐릭터 외형 소구"
    OVERWHELMING_REWARD = "압도적 보상"
    QUESTION_CHOICE = "질문/선택 상황 제시"
    VISUAL_IMPACT = "비주얼 임팩트"
    TREND_MEME = "트렌드/인터넷 밈"


class CoreUSP(str, Enum):
    """시청자에게 약속하는 가치 제안."""

    BENEFIT = "혜택형(무료뽑기/보상)"
    STRATEGY = "전략/경쟁형(상성/조합)"
    EMOTION = "감성 유대형(교감/서사)"
    CONVENIENCE = "편의성형(방치/빠른성장)"
    BUZZ = "대세감(출시일/사전등록수)"


class VisualStyle(str, Enum):
    """아트 표현 기법."""

    ILLUSTRATION_2D = "2D 일러스트"
    CELL_SHADING_3D = "3D 셀셰이딩"
    FIGURE_25D = "2.5D 피규어 입체 화풍"
    PIXEL_RETRO = "도트/픽셀 레트로"
    CINEMATIC_LIVE = "시네마틱 실사 합성"


# ─────────────────────────────────────────────────────────────
# Stage 5-E: 신호 기반 구조화 enums (분석·집계 가능)
# ─────────────────────────────────────────────────────────────
class StrengthSignal(str, Enum):
    """이 소재의 강점 (1-3개 다중 선택)."""

    HOOK_VISUAL_IMPACT     = "강한 비주얼 임팩트"
    # Stage 5-K: '캐릭터 매력 전면 노출'(91% catch-all) → 연출 방식별 4분할로 변별
    CHAR_ROSTER            = "다수 캐릭터 라인업"
    CHAR_CUTE_SD           = "SD/귀여운 캐릭터 연출"
    CHAR_HERO_SPOTLIGHT    = "단일 주인공 스포트라이트"
    CHAR_ACTION            = "캐릭터 액션/전투 연출"
    HOOK_REWARD_PROMISE    = "보상 약속 명확"
    HOOK_CURIOSITY         = "호기심/궁금증 유발"
    VALUE_PROP_CLEAR       = "단일 명료한 가치 제안"
    PROOF_SOCIAL_NUMBERS   = "수치·수상 사회증명"
    EMOTIONAL_BOND         = "감성 유대/스토리텔링"
    URGENCY_SCARCITY       = "출시일·한정 강조"
    GAMEPLAY_SHOWCASE      = "게임플레이 자체 매력"
    AUDIO_HOOK             = "오디오 후킹(BGM/SFX/Voice)"


class WeaknessSignal(str, Enum):
    """우려되는 약점 (0-3개 다중 선택)."""

    UNCLEAR_GENRE          = "장르/게임성 불분명"
    INFO_OVERLOAD          = "정보 과적 (텍스트/UI 산만)"
    GENERIC_HOOK           = "후킹 식상/평이"
    WEAK_CTA               = "행동 유도 약함/부재"
    SMALL_TEXT_MOBILE      = "모바일 가독성 떨어지는 텍스트"
    BRAND_INVISIBLE        = "타이틀/브랜드 인지 약함"
    SLOW_PAYOFF            = "초반 3초 안에 가치 전달 실패"


class PerformanceHypothesis(str, Enum):
    """예상 성과 패턴 (1-2개 다중 선택). KPI cross-tab 검증용 가설."""

    HIGH_CTR_LIKELY        = "높은 CTR 예상 — 강한 후킹"
    HIGH_CVR_LIKELY        = "높은 CVR 예상 — 명확한 가치"
    LOW_RELEVANCE_RISK     = "낮은 관련성 위험 — 정보 부족"
    LOW_CONVERSION_RISK    = "낮은 전환 위험 — 행동 유도 약함"
    NICHE_AUDIENCE         = "특정 타겟에 강하게 반응"
    BROAD_APPEAL           = "범용 어필(Mass-market)"
    HIGH_FATIGUE_RISK      = "피로도 빠를 위험 — 변주 필요"


class TestRecommendation(str, Enum):
    """다음 제작 시 시험할 변주 (0-3개 다중 선택). 신규 제작 가이드용."""

    REPLICATE_HOOK_OTHER_CHAR   = "동일 후킹 + 다른 캐릭터"
    SIMPLIFY_COPY               = "카피 1줄로 축약"
    ADD_EXPLICIT_CTA            = "명시적 CTA 추가"
    SHORTEN_TO_15SEC            = "15초 컷 테스트"
    ADD_GAMEPLAY_CUT            = "게임플레이 컷 추가"
    LOCALIZE_VARIANT            = "지역/언어 변주"
    AB_TEST_VISUAL_STYLE        = "다른 art_style 변주 (A/B)"
    SWAP_USP_ANGLE              = "다른 core_usp 각도 변주"


# ─────────────────────────────────────────────────────────────
# Stage 5-E 보강: 가설 ↔ KPI 메타 매핑 (analyze-signals.py 가설3 검증용)
#
# 한글 substring 매칭(이전 분석 스크립트의 verdict 로직)을 제거하고,
# enum 변경 시 schema 한 곳만 수정하면 분석/대시보드/검증 step 모두
# 자동 갱신되도록 메타데이터를 schema 옆에 둔다.
#
# 키 = enum.value (한글 라벨), 값 = (target_metric, direction).
# - target_metric: 'CTR' | 'CVR' | 'CPA'
# - direction:     'high' (값이 전체 평균보다 크면 가설 확증) | 'low' (작으면 확증)
#                  None 이면 자동 verdict 보류 (사람이 보고 판단).
# ─────────────────────────────────────────────────────────────
HYPOTHESIS_KPI_MAP: dict[str, tuple[str, str | None]] = {
    PerformanceHypothesis.HIGH_CTR_LIKELY.value:    ("CTR", "high"),
    PerformanceHypothesis.HIGH_CVR_LIKELY.value:    ("CVR", "high"),
    PerformanceHypothesis.LOW_RELEVANCE_RISK.value: ("CTR", "low"),
    PerformanceHypothesis.LOW_CONVERSION_RISK.value: ("CVR", "low"),
    PerformanceHypothesis.NICHE_AUDIENCE.value:      ("CPA", None),
    PerformanceHypothesis.BROAD_APPEAL.value:        ("CTR", None),
    PerformanceHypothesis.HIGH_FATIGUE_RISK.value:   ("CTR", None),
}


SIGNAL_FIELDS: tuple[str, ...] = ("strengths", "weaknesses", "hypothesis", "test_ideas")


def signal_distribution(creatives: list[dict]) -> dict[str, "Counter"]:
    """소재 리스트의 v2 신호 4종 분포를 Counter dict 로 반환.

    analyze-signals.py / check-pipeline-output.py 양쪽에서 같은 패턴을 쓰던
    것을 통일. 신호 필드 추가 시 SIGNAL_FIELDS 만 수정하면 전 분석 도구가
    자동 인식.

    Returns:
        dict[field_name, Counter[signal_label, count]]
    """
    from collections import Counter  # local import — 모듈 import overhead 회피
    counters = {f: Counter() for f in SIGNAL_FIELDS}
    for r in creatives:
        for f in SIGNAL_FIELDS:
            for v in r.get(f) or []:
                counters[f][v] += 1
    return counters


# ─────────────────────────────────────────────────────────────
# Stage 5-H: 신호 + 근거 페어 모델 (Gemini 경계 전용)
#
# object-list 가 1:1 정렬을 구조적으로 강제한다 — parallel-list 의
# 순서 어긋남(탐지 불가 신뢰 문제)을 원천 차단. main.py 가 CreativeRecord
# 로 평탄화하므로 signal_distribution/validators/대시보드는 무변경.
# ─────────────────────────────────────────────────────────────
class StrengthItem(BaseModel):
    """강점 신호 + 시각적 근거 페어."""

    signal: StrengthSignal = Field(..., description="강점 신호 enum")
    evidence: str = Field(
        ...,
        min_length=15,
        max_length=250,  # 목표 90자 (description). 영어 인용 포함 evidence 는 130자도 초과 (2026-06-11 minigame 3건) — 거부 비용이 커서 충분히 관대하게
        description=(
            "이 강점의 시각적 근거 (15-90자). 화면 위치·구성 요소·왜 효과적인지. "
            "예: '3~9초 실제 전투 화면에서 광역 스킬 이펙트가 화면 절반을 채워 장르를 즉시 인지시킴'."
        ),
    )


class WeaknessItem(BaseModel):
    """약점 신호 + 근거 페어."""

    signal: WeaknessSignal = Field(..., description="약점 신호 enum")
    evidence: str = Field(
        ...,
        min_length=15,
        max_length=250,  # 목표 90자 (description). 영어 인용 포함 evidence 는 130자도 초과 (2026-06-11 minigame 3건) — 거부 비용이 커서 충분히 관대하게
        description=(
            "이 약점의 근거 (15-90자). 무엇이 없는지/약한지 + 그로 인한 시청자 행동 결과. "
            "가능하면 동일 장르 소재 일반 수준 대비 서술."
        ),
    )


class TestIdeaItem(BaseModel):
    """테스트 변주 + 구체 실행안 페어."""

    idea: TestRecommendation = Field(..., description="변주 enum")
    action: str = Field(
        ...,
        min_length=15,
        max_length=250,  # 목표 90자 (description). 영어 인용 포함 evidence 는 130자도 초과 (2026-06-11 minigame 3건) — 거부 비용이 커서 충분히 관대하게
        description=(
            "당장 제작 지시 가능한 수준의 What+How (15-90자). 어느 컷에, 무엇을, 어떻게. "
            "예: '엔드카드 마지막 2초에 다운로드 버튼 + 사전등록 보상 문구를 삽입한 B버전 제작'."
        ),
    )


# ─────────────────────────────────────────────────────────────
# 2. 단일 소재 태깅 결과 (Gemini structured output)
# ─────────────────────────────────────────────────────────────
class CreativeTag(BaseModel):
    """Gemini가 1개 소재를 분석한 구조화 결과 (Stage 5-H v3 스키마).

    설계 의도:
    - v2: 서술형 제거 → 구조화 신호 (집계·KPI cross-tab 자동화)
    - v3 (5-H): 각 신호에 근거(evidence)·실행안(action) 페어 강제 — QA 피드백
      ("enum 라벨만으로는 구체 강점 요소 확인 불가") 반영. 근거 강제 자체가
      무차별 부여(강점 92%) 변별 장치로 작동.
    - creator_intent: 제작 의도 복원 / one_line_insight: 처방형 (진단형 금지)
    """

    hooking_strategy: HookingStrategy = Field(
        ...,
        description=(
            "초반 0~15초 후킹 기믹 분류. 1개 선택: "
            "'실패/분노 유도', '캐릭터 외형 소구', '압도적 보상', "
            "'질문/선택 상황 제시', '비주얼 임팩트', '트렌드/인터넷 밈'."
        ),
    )
    core_usp: CoreUSP = Field(
        ...,
        description=(
            "가치 제안. 1개 선택: "
            "'혜택형(무료뽑기/보상)', '전략/경쟁형(상성/조합)', "
            "'감성 유대형(교감/서사)', '편의성형(방치/빠른성장)', "
            "'대세감(출시일/사전등록수)'."
        ),
    )
    visual_style: VisualStyle = Field(
        ...,
        description=(
            "아트 스타일. 1개 선택: '2D 일러스트', '3D 셀셰이딩', "
            "'2.5D 피규어 입체 화풍', '도트/픽셀 레트로', '시네마틱 실사 합성'."
        ),
    )
    # Stage 5-H v3 — 신호 + 근거 페어 (object-list, 1:1 정렬 구조 강제)
    strengths: list[StrengthItem] = Field(
        ...,
        min_length=1,
        max_length=3,
        description=(
            "핵심 강점 1-3개, 각각 시각적 근거(evidence) 필수 동반. "
            "구체적 근거를 댈 수 없는 강점은 선택하지 말 것. 우선순위 높은 순."
        ),
    )
    weaknesses: list[WeaknessItem] = Field(
        default_factory=list,
        max_length=3,
        description=(
            "우려되는 약점 0-3개, 각각 근거(evidence) 필수 동반. "
            "명백한 약점이 없다면 빈 리스트 []. 지나친 흠집내기 금지."
        ),
    )
    hypothesis: list[PerformanceHypothesis] = Field(
        default_factory=list,
        max_length=2,
        description=(
            "예상 성과 가설 0-2개. 강점·약점에서 논리적으로 도출 가능할 때만. "
            "확신할 근거가 없거나 신호가 평이하면 빈 리스트 []. "
            "안전한 default 선택 금지 (모든 소재에 같은 가설 부여 X). "
            "예: 강한 후킹 + CTA 약함 → HIGH_CTR_LIKELY + LOW_CONVERSION_RISK."
        ),
    )
    test_ideas: list[TestIdeaItem] = Field(
        default_factory=list,
        max_length=3,
        description=(
            "다음 제작 시 시험해볼 변주 0-3개, 각각 구체 실행안(action) 필수 동반. "
            "약점 보완 또는 강점 증폭 관점."
        ),
    )
    creator_intent: str = Field(
        ...,
        min_length=20,
        max_length=100,  # 목표 60자 (description) + LLM 초과 마진 (2026-06-11 validation 실패 1건 대응)
        description=(
            "제작자가 이 소재로 의도했을 바를 1문장 추론 (20-60자). "
            "평가가 아닌 의도 복원. "
            "예: '실제 플레이 연출로 코어 게이머에게 게임성을 직접 증명하려는 의도'."
        ),
    )
    one_line_insight: str = Field(
        ...,
        min_length=30,
        max_length=180,  # 목표 140자 (description) + LLM 초과 마진
        description=(
            "이 소재 1줄 (30-140자 한글). 구조 = [현재 평가 요약] — [구체 개선 방향]. "
            "반드시 실행 가능한 개선 제안으로 끝낼 것. "
            "진단형('~여지 있음') 금지, 처방형('~를 추가/교체/축약하여 ~개선')으로. "
            "예: '전투 연출로 코어층 후킹은 강하나 마무리 행동 유도가 비어 있음 — "
            "엔드카드에 보상 연계 CTA를 추가해 전환 직결 구조로 개선'."
        ),
    )
    # Stage 5-I: 시각 가설 vs 실제 KPI 정합성 해석 (KPI 컨텍스트가 주입됐을 때만).
    kpi_reality_check: Optional[str] = Field(
        None,
        max_length=200,  # 목표 40-150자 + LLM 마진
        description=(
            "[이 소재의 실제 성과]에 KPI 가 제공됐을 때만 작성 (40-150자 한글). "
            "시각적 기대(가설)와 실제 KPI 의 정합/모순 + 시사점. KPI 가 없으면 생략(null). "
            "어미는 해석 후 행동: '~이므로 ~필요/검증'. "
            "예: '캐릭터 매력으로 높은 CTR 기대했으나 실제 CTR 하위 25% — "
            "후킹이 클릭으로 이어지지 않아 첫 3초 강화 필요'."
        ),
    )


# ─────────────────────────────────────────────────────────────
# 3. 대시보드 호환 단일 행 (스키마 v1)
# ─────────────────────────────────────────────────────────────
class CreativeRecord(BaseModel):
    """대시보드 public/data/{title}.json 의 creatives[] 배열 1개 원소.

    기존 CSV 컬럼명을 그대로 사용해 step1_integrated.html의 정규화 로직과
    100% 호환된다 (data-source.js normalizeFromJson 참조).
    """

    # 식별자
    creative_id: str = Field(..., description="유니크 ID (보통 폴더명 또는 파일명 stem)")

    # 기본 메타 (CSV 호환)
    소재명: str
    파일명: str
    유형: str = Field(..., description="BNR | VID | TXT")
    일: Optional[str] = Field(None, description="YYYY-MM-DD (파일명에서 파싱)")
    캠페인: Optional[str] = None
    사이즈: Optional[str] = None
    언어: Optional[str] = None
    링크: Optional[str] = Field(None, description="대시보드 미리보기용 URL — Stage 5에서 image_asset.full_size.url 또는 youtube URL이 자동 주입됨")

    # Stage 5-D: 소재명(T) 단위 통합 분석을 위한 정규화 필드
    creative_concept: Optional[str] = Field(
        None,
        description=(
            "CSV T열 컨벤션 — 사이즈/언어 무관 콘셉트 코어. "
            "예: 251104_BNR_A-Character-Adventure01A-DA_L_1200x628_EN → A-Character-Adventure01A-DA. "
            "대시보드에서 같은 concept을 가진 L/S/V 변형을 통합 그룹핑 가능."
        ),
    )

    # 성과 지표 (Stage 2 MVP에서는 0으로 채움 — Stage 5의 매체 API가 추후 갱신)
    전환: int = 0
    비용: int = 0
    노출수: int = 0
    클릭수: int = 0
    Revenue: int = 0

    # 4-compact taxonomy 태그 (Gemini 산출)
    hooking_strategy: Optional[str] = None
    core_usp: Optional[str] = Field(None, alias="USP")  # 기존 CSV의 USP 컬럼명과 호환
    visual_style: Optional[str] = Field(None, alias="art_style")  # 기존 art_style 컬럼명과 호환

    # Stage 5-E: 구조화 신호 (분석·집계용). 기존 marketer_insight 대체.
    # Stage 5-H: parallel-list 평탄화 형태 유지 (signal_distribution/validators/대시보드 호환).
    strengths: list[str] = Field(default_factory=list, description="강점 신호 1-3개 (StrengthSignal enum 값)")
    weaknesses: list[str] = Field(default_factory=list, description="약점 신호 0-3개 (WeaknessSignal enum 값)")
    hypothesis: list[str] = Field(default_factory=list, description="성과 가설 1-2개 (PerformanceHypothesis enum 값)")
    test_ideas: list[str] = Field(default_factory=list, description="테스트 변주 0-3개 (TestRecommendation enum 값)")
    one_line_insight: Optional[str] = Field(None, description="응축된 1줄 (처방형, 30-140자)")

    # Stage 5-H v3: 신호별 근거/실행안 (strengths/weaknesses/test_ideas 와 index 1:1).
    # CreativeTag(object-list)를 main.py 가 평탄화 — 정렬은 Gemini 경계에서 구조적으로 보장됨.
    strength_evidence: list[str] = Field(
        default_factory=list, description="강점별 시각적 근거 (strengths 와 index 1:1)"
    )
    weakness_evidence: list[str] = Field(
        default_factory=list, description="약점별 근거 (weaknesses 와 index 1:1)"
    )
    improvement_actions: list[str] = Field(
        default_factory=list, description="변주별 구체 실행안 (test_ideas 와 index 1:1)"
    )
    creator_intent: Optional[str] = Field(
        None, description="제작 의도 추론 1문장 (20-60자) — 모달 상단 소재 정보 영역 표시"
    )
    # Stage 5-I: 시각 가설 vs 실제 KPI 정합성 해석 (KPI 있을 때만)
    kpi_reality_check: Optional[str] = Field(
        None, description="실제 KPI vs 시각 가설 정합/모순 해석 (모달 '📊 데이터 체크' 표시)"
    )
    # Stage 5-I: 풀 대비 백분위 (코드 산출 — AI 아님). 키: ctr/cvr/cpa, 값: '상위 N%' 표시용 0-100
    kpi_percentiles: Optional[dict] = Field(
        None, description="풀 대비 백분위 {ctr, cvr, cpa} — 코드 계산, 모달 배지용"
    )

    # Stage 6: 백엔드 산출 점수 (대시보드 calculateCreativeScores 와 동일 알고리즘 — pipeline/scoring.py).
    # 기본 가중치 25/25/25/25 + roas_mode=auto. 대시보드는 KPI 필드로 런타임 재계산하므로
    # 이 필드는 표시에 미사용 — 이메일·리포트·백엔드 분석용 참고 스냅샷 (충돌 없음, scripts/verify-scoring.py 로 JS 동일성 검증).
    scores: Optional[dict] = Field(
        None,
        description="기본 가중치 점수 스냅샷 {total, grade, rank, conv, cpa, ipm, roas} — 백엔드/이메일용 (대시보드 미사용)",
    )

    # 후방 호환: 기존 대시보드가 marketer_insight를 직접 참조하던 경우 깨지지 않도록.
    # one_line_insight 의 값이 자동으로 채워짐 (data-source.js 정규화 후).
    marketer_insight: Optional[str] = Field(
        None,
        description=(
            "deprecated — one_line_insight 로 대체. "
            "기존 대시보드 호환을 위해 동일 값이 자동 채워짐."
        ),
    )

    # 부가 메타 (Pydantic v2는 leading underscore 필드명을 금지하므로 일반 이름 사용)
    tagged_at: Optional[str] = None  # ISO 8601 (Gemini 태깅 시각)
    gemini_model: Optional[str] = None
    source_files: list[str] = Field(default_factory=list, description="태깅에 사용된 파일들의 경로(폴더 내 variants)")

    # ──────────────────────────────────────────────────────────
    # Stage 5: 매체 KPI 메타 (Google Ads 등 외부 소스에서 채움)
    # ──────────────────────────────────────────────────────────
    kpi_source: Optional[str] = Field(
        None, description="KPI 출처 식별자: 'google_ads', 'appsflyer', 'airbridge', None=태깅만 진행"
    )
    kpi_window_start: Optional[str] = Field(None, description="KPI 조회 시작일 YYYY-MM-DD")
    kpi_window_end: Optional[str] = Field(None, description="KPI 조회 종료일 YYYY-MM-DD")
    kpi_daily: list["CreativeKpiDaily"] = Field(
        default_factory=list, description="일별 분리 KPI (대시보드 sparkline용)"
    )

    # ──────────────────────────────────────────────────────────
    # Stage 7: MMP(Airbridge) 소재 품질 레이어 — 非Google 매체. 전부 Optional(graceful).
    # 산출은 코드(pipeline/mmp_metrics.py). 대시보드는 별도 "소재 품질" 레이어로 표시.
    # ──────────────────────────────────────────────────────────
    mmp_source: Optional[str] = Field(None, description="MMP 출처: 'airbridge' | None")
    mmp_channels: list[str] = Field(default_factory=list, description="이 소재가 노출된 비-Google 채널")
    mmp_d1_ipm: Optional[float] = Field(None, description="D1 잔존수/노출×1000 (높을수록 좋음)")
    mmp_d1_cpi: Optional[float] = Field(None, description="비용/D1 잔존수 (낮을수록 좋음, 잔존0→None)")
    mmp_d7_roas: Optional[float] = Field(None, description="D7 누적매출/비용 (높을수록 좋음, 비용0→None)")
    mmp_d1_retention: Optional[float] = Field(None, description="D1 잔존수/설치수 ×100 (0~100)")
    mmp_quality_score: Optional[dict] = Field(None, description="4지표 rank 종합 {total,grade,rank,...} (phase-2)")
    mmp_installs: Optional[int] = None
    mmp_conversions: Optional[int] = None   # 등록 기준 타이틀의 MMP 전환수(사전예약). 설치 기준이면 None.
    mmp_retained_d1: Optional[int] = None
    mmp_cost: Optional[int] = None      # 비용 (mmp_currency 기준 — 환율 변환 후)
    mmp_revenue: Optional[int] = None   # D7 누적매출 합 (mmp_currency 기준)
    mmp_currency: Optional[str] = Field(None, description="비용/매출/CPI 표시 통화: 'KRW'(환율변환) | 'USD'(원천)")
    mmp_fx_rate: Optional[float] = Field(None, description="적용 환율(USD→KRW). 1.0=변환 안 함")
    mmp_daily: list["CreativeMmpDaily"] = Field(default_factory=list, description="채널별·일별(sparkline)")

    model_config = ConfigDict(populate_by_name=True)  # alias와 원본 이름 둘 다 허용


# ─────────────────────────────────────────────────────────────
# 4. Stage 7: MMP(Airbridge) 일별 소재 데이터 모델
# ─────────────────────────────────────────────────────────────
class CreativeMmpDaily(BaseModel):
    """MMP(Airbridge) 일별·채널별 소재 데이터. kpi_daily(Google Ads)와 분리된 레이어.

    date = 코호트 기준 설치일(YYYY-MM-DD). 비용/노출은 해당일, 잔존/매출은 코호트 누적.
    """
    creative_name: str
    date: str
    channel: str                  # 비-Google 매체명 (Meta/TikTok/ASA 등)
    campaign_name: str = ""       # Airbridge campaign 필드 (groupBys에 "campaign" 추가 후 채워짐)
    impressions: int = 0
    clicks: int = 0
    cost: int = 0                 # 정수 화폐단위(KRW)
    installs: int = 0            # 코호트 설치수 (Retention interval-0)
    retained_d1: int = 0         # D1 잔존수 (Retention interval-1)
    revenue_d7: int = 0          # D0~D7 누적 인앱매출
    conversions: int = 0         # 전환수(등록 기준 타이틀: web complete_registration 이벤트수). 미설정 타이틀 0.


# ─────────────────────────────────────────────────────────────
# 5. Stage 5: 일별 KPI 모델
# ─────────────────────────────────────────────────────────────
class CreativeKpiDaily(BaseModel):
    """(creative_name, campaign, ad_group, date) 4-key당 1개 — 매체별 일별 성과 지표.

    Stage 5-D 변경: agg key를 (creative_name, date) 2-key → 4-key 다차원으로 확장.
    같은 소재가 N개 캠페인에서 운영되면 N행 분리 보존되어 대시보드가 캠페인별 필터·비교 가능.

    main.py가 fetch_window() 결과를 (creative_name) 키로 그룹핑한 뒤 CreativeRecord.kpi_daily에 주입.
    대시보드는 (1) sparkline·일별 트렌드 차트, (2) 캠페인별 성과 비교, (3) URL 미리보기에 활용.
    """

    creative_name: str
    date: str  # YYYY-MM-DD
    source: str = Field(..., description="'google_ads', 'appsflyer', 'airbridge'")
    customer_id: str = Field(..., description="매체별 계정/고객 ID")

    # Stage 5-D 신규: 캠페인 단위 차원 보존 (CSV 행 단위와 일치)
    campaign_name: str = Field("", description="캠페인 풀네임 (CSV C열)")
    ad_group_name: str = Field("", description="광고그룹 풀네임 (CSV D열)")

    # Stage 5-D 신규: 미리보기 URL (대시보드 모달 thumbnail/play)
    asset_url: Optional[str] = Field(
        None,
        description=(
            "IMAGE: googlesyndication 캐시 URL (image_asset.full_size.url). "
            "YOUTUBE_VIDEO: https://www.youtube.com/watch?v={video_id}. "
            "MEDIA_BUNDLE/기타: None."
        ),
    )
    asset_type: Optional[str] = Field(
        None, description="IMAGE | YOUTUBE_VIDEO | MEDIA_BUNDLE"
    )

    impressions: int = 0
    clicks: int = 0
    cost_micros: int = Field(0, description="Google Ads native 단위 (1,000,000 = 1 currency unit)")
    cost: float = Field(0.0, description="cost_micros / 1_000_000 — 사람이 읽는 단위")
    conversions: float = Field(0.0, description="Google Ads는 float (소수 가능)")
    conversions_value: float = 0.0

    model_config = ConfigDict(populate_by_name=True)


# Forward reference 해결 (CreativeRecord에서 CreativeKpiDaily를 참조하므로)
CreativeRecord.model_rebuild()


# ─────────────────────────────────────────────────────────────
# 5. KPI 합계 헬퍼 (main.py에서 사용)
# ─────────────────────────────────────────────────────────────
class CreativeKpiTotals(BaseModel):
    """일별 KPI 리스트의 합계 — CreativeRecord의 전환·비용 등 필드 채우는 데 사용."""

    impressions: int = 0
    clicks: int = 0
    cost: float = 0.0
    conversions: float = 0.0
    conversions_value: float = 0.0


def aggregate_kpi(daily: list[CreativeKpiDaily]) -> CreativeKpiTotals:
    """일별 KPI 리스트 → 합계 모델."""
    if not daily:
        return CreativeKpiTotals()
    return CreativeKpiTotals(
        impressions=sum(d.impressions for d in daily),
        clicks=sum(d.clicks for d in daily),
        cost=sum(d.cost for d in daily),
        conversions=sum(d.conversions for d in daily),
        conversions_value=sum(d.conversions_value for d in daily),
    )


# ─────────────────────────────────────────────────────────────
# 6. 산출 JSON 루트 (스키마 v1)
# ─────────────────────────────────────────────────────────────
class CreativeDataset(BaseModel):
    """public/data/{title}.json 의 루트 객체."""

    schema_version: str = "1.0"
    title_id: str
    generated_at: str  # ISO 8601 (e.g., "2026-05-29T15:00:00+09:00")
    pipeline_version: str = "stage2-mvp"
    gemini_model: str = "gemini-2.5-flash"
    creatives: list[CreativeRecord] = Field(default_factory=list)

    # 메트릭 (대시보드 신뢰도 배지 등에서 활용 가능)
    metrics: dict = Field(default_factory=dict)

    # Phase 2: 캠페인명 캐노니컬 필드 맵 (campaign_name → {ua_type,country,os,media,product})
    campaign_canonical: dict = Field(default_factory=dict, description="캠페인 유형 필터용")

    # 소재명 별칭 매핑: 집행O·미조인 자산 (concept,source,impressions,cost,asset_types)
    unmatched_assets: list = Field(default_factory=list, description="별칭 매핑 대상 미매칭 자산")

    # 1b: 팀 공유 게임/마케터 컨텍스트 (game_context/{title}.md 전문 — 보고서·사전평가가 읽음)
    game_context: str = Field(default="", description="game_context md 전문(팀 공유 배경)")
