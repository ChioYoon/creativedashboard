# MMP 웹 사전예약 전환(complete_registration) 평가 설계

**작성일:** 2026-07-08

## Goal

ZEUS 같은 **웹 사전예약 타이틀**에서 MMP(Airbridge) 소재 평가를 가능하게 한다. 현재 MMP 전환이 `app_installs`(웹 사전예약은 ≈0)라 MMP 레이어가 비어 있는데, **`web_custom_complete_registration`(웹 사전예약 완료 이벤트)** 을 전환으로 사용해 UA 캠페인 소재를 등록수 기준으로 평가한다. ADS 레이어(이미 사전예약 전환 평가)와 동일한 UA 캠페인 기준으로 일관성 유지.

## 배경 / 현재

- **MMP 스코어링**(`pipeline/mmp_metrics.py`): 설치 중심 4지표 — 전환=`installs`(`app_installs`), D1 CPI=비용/D1잔존, D1 IPM=D1잔존/노출, D7 ROAS=매출/비용. `compute_mmp_quality_scores`가 소재별 종합점수(`mmp_quality_score`) 산출 → `public/data/{title}.json`에 주입 → 프런트 MMP 레이어가 표시.
- **ZEUS 실태**(2026-07 확인): 비Google 유료(Criteo·Meta·NAVER 등) 노출 6.7M·비용 ₩4.2M 집행되나 `app_installs`≈2 → **MMP 평가 공백**. ADS 레이어는 이미 Google Ads 사전예약 전환으로 평가 중.
- **전환 메트릭 확인**(Airbridge Actuals, app=`zeuskr`): `web_custom_complete_registration` 존재, 14일 15,121건. 메트릭 매핑은 오버라이드 가능(`AirbridgeMmpSource.DEFAULT_METRICS` + `revenue_d7` 앱별 custom 오버라이드 패턴).
- **캠페인 유형 분류**(기존): `pipeline/campaign_canonical.py`의 `campaign_ua_type()` + `_KNOWN_UA_TYPES = ("NU-Pre", "RT", "Boosting", "NU")`. Google Ads 소스·대시보드 캐노니컬 필터가 이걸로 UA를 판정. BR(브랜딩)·검색(Pre_Search)·브랜드키워드는 `ua_type=''`(非UA·미상 버킷).
- **소재명 매칭**(기존): `resolve_concept()`(main.py, "KPI·MMP 조인 공용")가 `{6자리}_{VID|BNR}_{concept}_..._ALL_Mixed_...` 등 패턴을 concept(소재 코어)로 정규화 → 이미 `_ALL_Mixed_` 처리. 즉 UA 소재(`260701_VID_P-Slogan-PreregPV15s-01-PV_ALL_Mixed_KR` → `P-Slogan-PreregPV15s-01-PV`)는 **이미 매칭**되고 있었고(installs만 0), BR 웹 소재(`Premium_MO` 등)는 concept 추출 실패 → 자연 미조인.

**데이터 검증(캠페인 유형별 등록수, 14일):** BR(브랜딩) 13,826(86%, `Premium_MO`·`KV1_Feed` 등 웹 전용) / UA(NU-Pre/RT/Boosting) 2,205(`P-Slogan-*` = 우리 소재 매칭) / 기타(검색·키워드) 923. → **미매칭 = 전부 브랜딩. UA 캠페인만 쓰면 미매칭 문제 해소.**

## 결정 (브레인스토밍 확정)

- **전환 메트릭**: `web_custom_complete_registration`(**이벤트수**). 타이틀별 설정(앱 타이틀은 기존 installs 유지).
- **소재 귀속 범위**: **UA 캠페인만**(`campaign_ua_type(campaign) != ''`) — BR·검색 제외. **기존 UA 기준(`_KNOWN_UA_TYPES`) 재사용**(새 목록 X). ADS 레이어와 동일 기준.
- **소재명 매칭**: 신규 없음 — 기존 `resolve_concept()` 재사용(`_ALL_Mixed_` 이미 처리).
- **스코어링**: 등록 기준 타이틀은 MMP 종합점수를 **사전예약 지표세트**(전환·CPA·IPM; ROAS·D1잔존 제외)로. ADS 사전예약(obj-prereg) 관점과 동일.
- **일관성 규칙**: 등록 기준 타이틀은 **MMP 집계 전체를 UA 캠페인으로 스코프**(전환·노출·비용 모두 UA 기준) → CPA/IPM 정합. 설치 기준 타이틀은 무변경.

## Architecture

파이프라인(수집·집계) → 스코어링(등록 기준 지표세트) → 프런트(표시) 3단. 기존 함수 최대 재사용.

### ① Airbridge 소스 — 전환 메트릭 수집 (`pipeline/sources/airbridge.py`)

- `DEFAULT_METRICS`에 `conversions` 키 추가(기본 `''` = 미사용). **타이틀별 오버라이드**: `_pipeline_airbridge_conversion_metric`(titles.json) 또는 env — ZEUS = `web_custom_complete_registration`. (기존 `revenue_d7` 오버라이드와 동형.)
- `CreativeMmpDaily`(schemas.py)에 `conversions: int = 0` 필드 추가.
- `parse_actuals_rows`: `conversions` 파싱. **UA 스코프** — 등록 기준 활성 시 `campaign_ua_type(campaign_name)`이 빈 값이면 그 행 스킵(전환·노출·비용 모두 UA 캠페인 행만 집계). `_query_metrics`에 conversions 메트릭 포함.
- 타이틀 설정 전달: `make_mmp_source`/`from_env` 확장으로 conversion_metric 주입. **단일 스위치** — conversion_metric 설정 유무가 basis(`registration`/`install`)와 UA 스코프를 함께 결정(설정 시 registration+UA스코프 ON, 미설정 시 기존 install 동작). 별도 플래그 없음.

### ② 스코어링 — 사전예약 MMP 지표세트 (`pipeline/mmp_metrics.py`)

- `aggregate_rows_total`/`aggregate_creative_mmp`에 `conversions` 합산 추가.
- `compute_mmp_quality`: `conversion_basis`('install'|'registration') 인자. registration이면:
  - 전환 = `conversions`(등록), **CPA = 비용/등록**(D1 CPI 대신), **IPM = 등록/노출×1000**(D1잔존 대신), ROAS·D1잔존 = None(축 제외).
- `compute_mmp_quality_scores`: registration 기준이면 **3축(전환·CPA·IPM) 균등**(ROAS 제외). install 기준이면 기존 4축 유지.
- main.py 주입: 타이틀 conversion_basis에 따라 산출. `mmp_quality_score`에 basis 표기(`convBasis: '사전예약'|'설치'`) + `mmp_conversions` 저장.

### ③ 프런트 — MMP 레이어 표시 (`step1_integrated.html` / `js/layer-metrics.js`)

- `creativeLayerView(c)`의 MMP 분기: 전환 = `meta.mmp_conversions`(등록) — 등록 기준 타이틀. 전환 기준 라벨 '사전예약'.
- MMP 종합점수·등급 = `meta.mmp_quality_score`(사전예약 지표세트 산출) 그대로 표시.
- KPI 없는 소재 게이트·유형별 집계 등 기존 로직은 전환 필드만 바뀌므로 대체로 무변경.

## Data Flow

1. main.py 타이틀 처리: cfg에 conversion_metric(`web_custom_complete_registration`)·conversion_basis('registration')·ua_scope(True) 세팅(titles.json).
2. Airbridge fetch(UA 스코프) → `CreativeMmpDaily{…, conversions}` → `resolve_concept()`로 소재 concept 조인(기존).
3. `compute_mmp_quality(basis='registration')` → 전환(등록)·CPA·IPM → `compute_mmp_quality_scores`(3축) → `mmp_quality_score` + `mmp_conversions` 주입.
4. 프런트 MMP 레이어: 전환=등록, 점수·등급=사전예약 기준. ADS↔MMP 동일 UA 기준.

## Error Handling / Edge Cases

- conversion_metric 미설정 타이틀 → 기존 installs 4축 그대로(무변경·하위호환).
- 등록 메트릭이 Actuals에 없음 → 0 처리(기존 `parse_actuals_rows` gv 패턴) → 전환 0(경고 로그).
- UA 캠페인 0건(전부 BR) → 소재 등록 0 → MMP 점수 '데이터 없음' 게이트(기존).
- 소재 concept 미해결(BR 웹 소재) → 조인 안 됨(기존 동작) → soje 미영향.
- 등록 기준인데 노출/비용 0 → CPA/IPM None → 해당 축 0점(기존 rank_score None 처리).
- 검색·브랜드키워드(비주얼 소재 없음) → concept 미해결 + 非UA → 이중 제외.

## Testing / Verification

- **파이프라인 단위**: `parse_actuals_rows`가 UA 캠페인 conversions만 집계(BR 행 스킵) — 픽스처 테스트. `compute_mmp_quality(basis='registration')` 산식(등록·CPA·IPM, ROAS None) 단위 테스트. `compute_mmp_quality_scores` 3축 균등 테스트. 기존 install 경로 무회귀.
- **통합**: ZEUS 실 fetch(또는 픽스처)로 `public/data/zeus.json`에 `mmp_conversions`·`mmp_quality_score`(사전예약) 주입 확인.
- **프런트**(preview, zeus): MMP 레이어 전환=등록수, 점수·등급 표시, 전환 기준 '사전예약' 라벨. install 타이틀 무회귀.
- pytest 전체 통과(신규 테스트 포함).

## 단계화 (구현 계획용)

- **Phase 1 — 파이프라인 수집**: conversion 메트릭 오버라이드 + `CreativeMmpDaily.conversions` + UA 스코프 파싱 + main.py 주입(`mmp_conversions`). 산출물: zeus.json에 등록수.
- **Phase 2 — 스코어링**: `mmp_metrics` 사전예약 지표세트(등록·CPA·IPM, 3축) + basis 배선. 산출물: `mmp_quality_score`(사전예약).
- **Phase 3 — 프런트**: MMP 레이어 전환=등록 표시·라벨. 산출물: 대시보드 MMP 평가 동작.

각 Phase 독립 검증 가능. Phase 1→2→3 순서 의존(데이터→점수→표시).

## Out of Scope (YAGNI)

- 브랜딩(BR)·검색 소재 평가 — 의도적 제외(소재 미매칭/비주얼 없음). 미매칭 웹 소재 별도 표시(향후 별건).
- 대시보드 캠페인 유형 토글로 MMP를 재슬라이스(Approach B) — 파이프라인 UA 스코프 사전 필터로 대체(v1). MMP 캠페인 차원 보존은 향후.
- 순사용자수(users) 전환 기준 — 이벤트수 확정.
- 설치+등록 동시 평가·혼합 타이틀 — 타이틀당 단일 conversion_basis.
- AppsFlyer 등 타 MMP의 registration — Airbridge(ZEUS) 우선.
- `_KNOWN_UA_TYPES`에 없는 캠페인 유형 신규 분류.
