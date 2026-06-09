"""분포 sanity check validator (Stage 5-G.4).

목적: AI 태깅 결과의 무차별 부여(`HIGH_CTR_LIKELY 100%` 등) 자동 감지.

설계 원칙:
- raise X, log only (자동화 흐름에 부작용 0)
- schemas.signal_distribution() 재사용 — SoT 단일화
- threshold 외부 주입 가능 (기본 0.8 = 80%)
- 호출: scripts/check-pipeline-output.py 만 (main.py 비영향)

사용 예:
    from pipeline.validators import check_signal_diversity
    warnings = check_signal_diversity(creatives, top_share_threshold=0.8)
    for w in warnings:
        print(f"[분포 경고] {w}")
"""

from __future__ import annotations

from .schemas import SIGNAL_FIELDS, signal_distribution


# 필드별 한글 라벨 (출력 메시지용)
_FIELD_LABELS: dict[str, str] = {
    "strengths":  "강점",
    "weaknesses": "약점",
    "hypothesis": "가설",
    "test_ideas": "변주 추천",
}


def check_signal_diversity(
    creatives: list[dict],
    top_share_threshold: float = 0.8,
) -> list[str]:
    """signal 필드별 top-1 enum 값의 점유율을 검사.

    threshold(기본 80%) 초과 시 경고 메시지 생성.

    Args:
        creatives: public/data/{title}.json 의 creatives 배열
        top_share_threshold: 0.0~1.0. 이 비율을 넘는 단일 enum 부여 시 경고

    Returns:
        list[str]: 경고 메시지 리스트 (정상 시 빈 리스트)
    """
    if not creatives:
        return []
    total = len(creatives)
    if total == 0:
        return []

    warnings: list[str] = []
    distribution = signal_distribution(creatives)

    for field in SIGNAL_FIELDS:
        counter = distribution.get(field)
        if not counter:
            continue  # 모든 record 에 해당 필드가 비어있으면 skip

        top_label, top_count = counter.most_common(1)[0]
        share = top_count / total
        if share >= top_share_threshold:
            label = _FIELD_LABELS.get(field, field)
            warnings.append(
                f"{label} '{top_label}' 가 {top_count}/{total} "
                f"({share*100:.0f}%) 부여됨 — 무차별 부여 의심. "
                f"프롬프트 보강 또는 enum 라벨 재검토 필요."
            )

    return warnings
