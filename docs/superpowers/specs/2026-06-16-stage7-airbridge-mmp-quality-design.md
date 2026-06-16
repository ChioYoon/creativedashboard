# Stage 7 — Airbridge MMP 소재 품질 레이어 (설계 스펙)

작성: 2026-06-16 · 상태: 설계 확정 대기

## 1. 배경 · 목표

CLOOP 대시보드는 현재 Google Ads API로 **네트워크 지표**(노출·클릭·비용·전환·전환가치)를 소재 단위로 받아 분석한다(Stage 5~6). 그러나:

- Google Ads API는 **구글 캠페인만** 보인다 — Meta·TikTok·ASA 등 타 매체 소재 성과는 보이지 않는다.
- Google Ads의 전환가치는 UA에서 신뢰도가 낮다 — **실제 인앱 매출(LTV)·잔존·진짜 ROAS**를 못 본다.

Stage 7은 **Airbridge(MMP)**를 연동해 **Google Ads 外 매체**의 소재 성과를, **소재 품질 중심**의 4개 지표로 분석하는 **별도 "소재 품질(MMP)" 레이어**를 추가한다. 기존 Google Ads 기반 점수·지표는 **일절 변경하지 않는다**(additive).

**첫 대상**: `pepp-us` (Airbridge 사용). 이후 다른 타이틀·AppsFlyer는 동일 패턴으로 확장.

## 2. 확정된 설계 결정

| 항목 | 결정 | 근거 |
|---|---|---|
| MMP | AppsFlyer·Airbridge 둘 다 사용 → **Airbridge 먼저** | pepp가 Airbridge. KpiSource 추상화로 AppsFlyer는 차기 확장 |
| 접근 | **API 토큰 보유**(자동 연동) | Google Ads처럼 nightly 자동 fetch |
| 소재 granularity | 소재 단위 집계 + **이름 일치**(폴더/Google Ads 컨벤션과 동일) | 바로 join 가능. 단 Actuals만 `ad_creative` 확인됨 — Revenue/Retention은 7-A 검증 |
| 공존 방식 | **별도 "MMP 성과/품질" 레이어 추가** (option 2) | Google Ads는 기존 방식 유지, **Google Ads 外 매체만** Airbridge로 커버 |
| 매체 필터 | Airbridge fetch 시 **channel에서 Google Ads 제외** | 두 레이어 중복(double-count) 방지 |
| 지표 | **D1 IPM · D1 CPI · D7 ROAS · D1 Retention** | 소재 품질 중심 평가 |
| 종합점수 | **포함**(7-B phase-2) — 4지표 rank 종합 "소재 품질 점수" | "품질 중심 평가" 직결. 핵심은 4지표 raw, 점수는 그 위에 |
| 리스크1 degrade | **캠페인 단위 degrade 안 함** — 소재 단위 가용 지표만으로 분석 | 데이터 일관성. 소재 단위 안 되는 지표는 생략(null) |

## 3. 지표 정의 (⚠️ 업계 표준과 다름 — 정확히 준수)

분모가 **D1 잔존수**(raw 설치수 아님). 설치 후 즉시 이탈하는 "낚시성 소재"를 구조적으로 페널티하는 품질 철학.

| 지표 | 공식 | 방향 | 데이터 출처 |
|---|---|---|---|
| **D1 IPM** | (D1 잔존수 / 노출수) × 1000 | 높을수록 좋음 | Retention(잔존) + Actuals(노출) |
| **D1 CPI** | 비용 / D1 잔존수 | 낮을수록 좋음 | Actuals(비용) + Retention(잔존) |
| **D1 Retention** | D1 잔존수 / 설치수(코호트 base) | 높을수록 좋음 | Retention(잔존 + interval-0 코호트) |
| **D7 ROAS** | D0~D7 누적매출 / 비용 | 높을수록 좋음 | Revenue(`app_roas`, intervalsPeriodIndexes:[7], cumulative) |

- **D1 잔존수 = linchpin** (4지표 중 3개의 핵심값). Retention Report의 `ad_creative` 소재 단위 지원이 전체 성패를 좌우 → **7-A 최우선 검증**.
- D1 잔존수 = Retention interval-1(D1 복귀) 카운트. 설치수 base = Retention interval-0 카운트(코호트 일관성). Actuals `app_installs`는 교차검증용.
- 모든 산출은 **코드**에서 수행(AI 아님 — LLM 산술 금지 원칙, Stage 5-I와 동일).

## 4. 아키텍처 · 데이터 흐름

```
[Google Ads API] ── 네트워크 지표(기존, 불변) ──┐
                                                ├─→ CreativeRecord ─→ pepp-us.json ─→ 대시보드
[Airbridge 3 Reports] ── 非Google 품질 4지표 ──┘     (기존 KPI + 신규 mmp_* 레이어)
   Actuals(노출·클릭·비용·설치)
   Revenue(D7 ROAS)              ※ channel ≠ Google Ads 필터
   Retention(D1 잔존수)
```

`airbridge.py`(KpiSource 서브클래스)가 3개 비동기 리포트를 각각 생성→폴링→`ad_creative`별 병합 후, 코드로 4지표 산출. main.py가 기존 Google Ads join **이후** Airbridge fetch→소재명 join→`mmp_*` 주입.

## 5. Airbridge API 사양 (2026-06 확인)

공통: `Authorization: Bearer {token}`, **비동기**(POST→`taskId`→GET 폴링: PENDING/RUNNING/SUCCESS/FAILURE). 토큰은 대시보드 Settings>Tokens.

| 리포트 | 엔드포인트 | 윈도우 | 핵심 필드 |
|---|---|---|---|
| Actuals | `POST /reports/api/v7/apps/{app}/actuals/query` | 최대 400일 | groupBy `ad_creative`✅·`channel`·`event_date`; metrics `impressions`·`clicks`·`app_installs`·cost |
| Revenue | `POST /reports/api/v3/apps/{app}/revenue/query` | — | metric `app_roas`·`app_revenue`; `intervalsPeriodIndexes:[7]`·`aggregationType:cumulative`; `ad_creative` groupBy ⚠️미확인 |
| Retention | `POST /reports/api/v5/apps/{app}/retention/query` | **최대 92일** | `intervalsPeriod`(interval0=코호트, interval1=D1); 카운트 반환; `ad_creative` groupBy ⚠️미확인 |

**제약 대응**:
- **ad_creative 미확인(Revenue·Retention)**: 7-A에서 Get Metadata(GroupBy) API로 검증. 미지원 시 해당 지표만 생략(소재 단위 가용 지표로만 분석 — 캠페인 degrade 없음).
- **Retention 92일**: pepp historical(~150일)은 ≤92일 청크 분할 후 병합.
- **채널 필터**: Google Ads의 Airbridge channel 표기(예: "Google Ads"/"googleadwords") 7-A 확인 후 모든 리포트 filter에 제외 적용.
- **D7 코호트 성숙**: 설치 후 7일 미경과 코호트는 D7 데이터 없음 — historical은 무관, 최근 데이터는 7일 지연 표시.

## 6. 스키마 추가 (`pipeline/schemas.py`)

기존 KPI 필드(전환·비용·노출수·클릭수·Revenue·kpi_daily)는 **불변**.

```python
class CreativeMmpDaily(BaseModel):   # 신규 — MMP 일별(레이어 분리, kpi_daily와 별개)
    date: str
    channel: str                      # 비-Google 매체명
    impressions: int = 0
    installs: int = 0                  # 코호트 base
    retained_d1: int = 0              # D1 잔존수
    cost: int = 0
    revenue_d7: int = 0               # D0~D7 누적매출

# CreativeRecord 추가 필드 (전부 Optional — graceful degrade)
mmp_source: Optional[str]             # "airbridge"
mmp_channels: list[str]               # 이 소재가 노출된 비-Google 채널
mmp_d1_ipm: Optional[float]
mmp_d1_cpi: Optional[float]
mmp_d7_roas: Optional[float]
mmp_d1_retention: Optional[float]     # 0~100(%)
mmp_quality_score: Optional[dict]     # {total, grade, rank, ipm, cpi, roas, retention} (phase-2)
mmp_installs/mmp_retained_d1/mmp_cost/mmp_revenue: Optional[int]  # 원천 집계값
mmp_daily: list[CreativeMmpDaily]     # 채널별·일별 (sparkline)
```

지표가 소재 단위로 안 나오면 해당 `mmp_*` = None (대시보드 자동 degrade).

## 7. main.py 통합

기존 Google Ads KPI fetch+join 블록 **이후**:
1. 타이틀에 `_pipeline_airbridge_app_name` + 토큰 있으면 `AirbridgeKpiSource.fetch_window()` 호출(非Google 필터).
2. 소재명으로 mmp_index 구성 → 각 record에 `mmp_*` 주입.
3. 코드로 4지표 + (phase-2)종합점수 산출.
4. `AirbridgeCache`(KpiCache 패턴, 35일 TTL, 키=(title, report, window))로 비동기 리포트 결과 캐싱 — 호출 비용↓.

graceful degradation: Airbridge 실패해도 태깅·Google Ads는 진행. 401/403은 AuthError로 중단. metrics에 `mmp_status` 기록(메일 표시).

## 8. 대시보드 "소재 품질(MMP)" 레이어 (`step1_integrated.html`)

기존 광고 성과(Google Ads) 점수·표와 **분리된 신규 레이어**:
- 모달: "🎯 소재 품질(MMP)" 섹션 — D1 IPM·D1 CPI·D7 ROAS·D1 Retention 4지표 + (phase-2)품질점수, 채널 배지.
- 결과 표: 선택적 MMP 컬럼(show-mmp 토글, 데이터 있을 때만 — CSV/비연동 타이틀 자동 degrade).
- `js/data-source.js` 패스스루(신규 alias 불필요, mmp_* 그대로 통과).
- graceful: `mmp_*` 없으면 섹션/컬럼 숨김(기존 `Array.isArray` 가드 패턴).

## 9. 서브스테이지 분할

| Sub | 책임 | 산출 | DoD |
|---|---|---|---|
| **7-A** | 사용자+IT | Airbridge API 토큰·app_name, **ad_creative groupBy 검증**(Get Metadata), Google channel 표기 확인, pepp 非Google 데이터 존재 확인, healthcheck | `python -m pipeline.mmp --healthcheck` OK + 가용 지표 목록 확정 |
| **7-B** | Claude | `airbridge.py`(3리포트+폴링+병합+非Google필터+92일청크), `CreativeMmpDaily`+CreativeRecord 필드, main.py 병합, `AirbridgeCache`, titles.json `_pipeline_airbridge_*`, `mmp.py` CLI. **phase-2**: 품질 종합점수(scoring.py rank 헬퍼 재사용). mock fixture 선행 | mock 단위테스트 통과 + 실 fetch dry-run + 4지표 산출 검증 |
| **7-C** | Claude | 대시보드 "소재 품질" 레이어 UI | pepp 모달/표 4지표 표시 + 비연동 타이틀 degrade + 콘솔 에러 0 |
| **7-D** | 양측 | nightly 자동 통합 + Airbridge 대시보드 1:1 검증 + notify mmp_status | 소재 1개 4지표가 Airbridge UI와 일치 |

병렬: 7-A IT 대기 중 Claude가 7-B를 mock fixture로 선행 개발(Stage 5 패턴).

## 10. 핵심 아키텍처 결정

| 항목 | 채택 | 근거 |
|---|---|---|
| 소스 구조 | `sources/airbridge.py` (KpiSource 구현) | 기존 ABC 그대로, AppsFlyer 차기 동일 패턴 |
| 리포트 호출 | 3개 비동기(Actuals/Revenue/Retention) 개별 폴링 후 코드 병합 | 각 리포트 책임 분리, 부분 실패 시 가용 지표만 |
| 캐싱 | `AirbridgeCache` 별도(35일 TTL) | 비동기 리포트 무겁고 historical frozen — 적극 캐싱 |
| 지표 산출 | 코드(main.py/airbridge.py), AI 미개입 | LLM 산술 금지 원칙 |
| 레이어 분리 | mmp_* 신규 필드 + 별도 UI, 기존 KPI/점수 불변 | 사용자 결정(option 2). Google Ads는 기존 유지 |
| 매체 필터 | channel ≠ Google Ads | 중복 방지, 사용자 결정 |
| 종합점수 | scoring.py `_assign_rank_with_ties` 재사용한 별도 품질 스코어러 | 4지표·방향·0-rule이 KPI와 달라 compute_creative_scores 직접 재사용 부적합 |

## 11. 검증 전략

- **7-A**: Get Metadata로 `ad_creative` 가용성 확정 → 가용 지표 범위 확정. pepp 非Google 데이터 존재(설치>0) 확인.
- **7-B mock**: 3리포트 mock 응답 → 4지표 산출 정확성 단위테스트. 폴링 상태머신·92일 청크 병합 테스트.
- **7-B 실 fetch**: `python -m pipeline.mmp --title pepp-us --dry-run` — 실 API + 출력만.
- **7-D E2E**: pepp 소재 1개의 D1 잔존수·비용·매출을 Airbridge UI에서 사람이 직접 확인 → JSON 4지표와 1:1 대조(Stage 5-B 진단 패턴).

## 12. 리스크 · Open Items

- **R1 (최우선)**: Revenue·Retention `ad_creative` 미지원 가능성 → 7-A 검증. 미지원 지표는 생략(소재 단위 가용 지표로만 분석).
- **R2**: Retention 92일 윈도우 → 청크 분할 병합.
- **R3**: pepp가 사실상 Google Ads-only였다면 非Google MMP 레이어가 sparse → 7-A에서 데이터 존재 확인. sparse 시 다른 활성 타이틀로 첫 대상 재고.
- **R4**: Airbridge channel의 Google Ads 표기명 불확실 → 7-A 확인.
- 차기: AppsFlyer 소스, 다른 타이틀(도원암귀 등) 연동, 리텐션 D7/D30 확장.
