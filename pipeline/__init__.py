"""
Com2uS R팀 CLOOP 백엔드 파이프라인.

Stage 2 MVP — 로컬 GDrive sync 폴더에서 소재 → Gemini 자동 태깅 → JSON 산출.

모듈 구조:
- schemas: Pydantic 모델 (4-compact taxonomy, 산출 JSON 스키마 v1)
- scanner: 로컬 폴더 스캔 + 파일명 정규식 파싱
- cache: SHA-256 기반 결과 캐싱 (재호출 방지)
- tagger: Gemini Files API 호출 + structured output
- main: CLI 진입점
"""

__version__ = "0.1.0"  # Stage 2 MVP
