"""
KPI 데이터 소스 추상 클래스 — Stage 5.

향후 AppsFlyer/Airbridge 등 다른 매체를 추가해도 같은 인터페이스로 통합할 수 있도록
공통 ABC를 정의한다. main.py의 KPI fetch 블록은 KpiSource 타입에만 의존하므로
새 매체는 본 ABC 메서드 3개만 구현하면 즉시 통합 가능.

설계 원칙:
- fetch_window()는 batch 호출 (소재별 호출 X) — quota 효율
- 결과는 일별 분리된 CreativeKpiDaily 리스트 → 대시보드 sparkline 호환
- auth_check()는 cheap call (1 row LIMIT 등) — 야간 배치 시작 직전 healthcheck용
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Iterable, Optional, Sequence

from ..schemas import CreativeKpiDaily
from ..base_errors import AuthError, QuotaError  # re-export (기존 import 경로 호환)


class KpiSource(ABC):
    """모든 매체 KPI 소스의 공통 인터페이스."""

    @abstractmethod
    def source_name(self) -> str:
        """소스 식별자 (예: 'google_ads', 'appsflyer', 'airbridge').

        CreativeKpiDaily.source 필드 및 알림 메일에 표기됨.
        """
        raise NotImplementedError

    @abstractmethod
    def auth_check(self) -> bool:
        """인증 상태 검증.

        Returns:
            True: 인증 정상, 즉시 호출 가능
            False: 인증 실패 (token 만료, scope 부족 등)

        구현 시 가능한 한 cheap call을 사용 (예: LIMIT 1 쿼리).
        실패 사유는 raise 대신 stderr 로깅 후 False 반환 권장.
        """
        raise NotImplementedError

    @abstractmethod
    def fetch_window(
        self,
        customer_id: str,
        start: date,
        end: date,
        creative_names: Optional[Sequence[str]] = None,
        campaign_filter: Optional[Sequence[str]] = None,
    ) -> Iterable[CreativeKpiDaily]:
        """지정 기간의 일별 KPI를 일괄 조회.

        Args:
            customer_id: 매체별 고객/계정 ID (Google Ads의 customer_id 10자리 등).
            start, end: 조회 기간 (inclusive). YYYY-MM-DD.
            creative_names: 조회 대상 소재명 필터. None이면 전체.
                            구현체는 quota 절감을 위해 가능하면 WHERE 절에 활용.
            campaign_filter: 캠페인명 필터. None이면 전체 캠페인.

        Yields:
            CreativeKpiDaily — (creative_name, date) 페어당 1개.
            동일 (creative_name, date)가 여러 AdGroup에 걸쳐 있으면 구현체가 합산 또는 분리 결정.
            본 프로젝트는 합산 권장 (대시보드는 소재 단위 분석이 목적).

        Raises:
            AuthError: 인증 실패 (401/403) — 즉시 batch 전체 중단해야 함
            QuotaError: API quota 초과 — 다른 타이틀로 계속 진행 가능
            기타 Exception: graceful degradation 대상 (태깅은 계속)
        """
        raise NotImplementedError


