"""
Pydantic 모델 — Stage 2 MVP 4-compact taxonomy.

제안서 검토 결과 채택한 콤팩트 분류 체계 (마케터 검수 과부하 60%+ 절감):
  1. 후킹 전략 (Hooking Strategy) — 6개 enum
  2. 핵심 메시지 소구 (Core USP) — 5개 enum
  3. 비주얼/아트 스타일 (Visual/Art Style) — 5개 enum
  4. 제작 기획 해석 (Marketer Insight) — 자유 서술 (3단 구조)

산출 JSON 스키마 v1 — js/data-source.js의 normalizeFromJson() 과 호환.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


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
# 2. 단일 소재 태깅 결과 (Gemini structured output)
# ─────────────────────────────────────────────────────────────
class CreativeTag(BaseModel):
    """Gemini가 4-compact taxonomy에 따라 1개 소재를 분류한 결과."""

    hooking_strategy: HookingStrategy = Field(
        ...,
        description=(
            "초반 0~15초 후킹 기믹 분류. 다음 중 하나만 기재: "
            "'실패/분노 유도', '캐릭터 외형 소구', '압도적 보상', "
            "'질문/선택 상황 제시', '비주얼 임팩트', '트렌드/인터넷 밈'."
        ),
    )
    core_usp: CoreUSP = Field(
        ...,
        description=(
            "소재가 시청자에게 약속하는 가치. 다음 중 하나: "
            "'혜택형(무료뽑기/보상)', '전략/경쟁형(상성/조합)', "
            "'감성 유대형(교감/서사)', '편의성형(방치/빠른성장)', "
            "'대세감(출시일/사전등록수)'."
        ),
    )
    visual_style: VisualStyle = Field(
        ...,
        description=(
            "아트 표현 기법. 다음 중 하나: '2D 일러스트', '3D 셀셰이딩', "
            "'2.5D 피규어 입체 화풍', '도트/픽셀 레트로', '시네마틱 실사 합성'."
        ),
    )
    marketer_insight: str = Field(
        ...,
        min_length=80,
        max_length=1500,  # v1.0.1: Gemini가 자연스럽게 700~1000자를 생성하는 도메인 특성 반영
        description=(
            "[전략적 의도], [타겟 심리], [성과 예측 및 변주] 3단 구조의 한글 "
            "마케팅 해석 평구. 단순한 사이즈/지면 사설은 금지하고 실제 기획 "
            "의도와 타겟 심리 분석에 집중할 것. 각 단락은 [태그]로 시작."
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
    링크: Optional[str] = Field(None, description="대시보드 미리보기용 URL (GDrive 미리보기 등)")

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
    marketer_insight: Optional[str] = None

    # 부가 메타 (Pydantic v2는 leading underscore 필드명을 금지하므로 일반 이름 사용)
    tagged_at: Optional[str] = None  # ISO 8601 (Gemini 태깅 시각)
    gemini_model: Optional[str] = None
    source_files: list[str] = Field(default_factory=list, description="태깅에 사용된 파일들의 경로(폴더 내 variants)")

    class Config:
        populate_by_name = True  # alias와 원본 이름 둘 다 허용


# ─────────────────────────────────────────────────────────────
# 4. 산출 JSON 루트 (스키마 v1)
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
