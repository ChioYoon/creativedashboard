# -*- coding: utf-8 -*-
"""매체 소스 공통 예외 (google_ads / airbridge 공용)."""


class AuthError(RuntimeError):
    """OAuth/토큰 인증 실패 (401/403/invalid_grant). batch 전체 중단 대상."""


class QuotaError(RuntimeError):
    """API quota/rate limit 초과. 해당 타이틀만 실패, 다른 타이틀 진행."""
