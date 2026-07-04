# Level 2 — 캠페인 목표별 지표 세트 (컬럼 dim) 설계

**작성일:** 2026-07-04
**선행:** 2026-07-03 Level 1(제우스 ADS 라벨 전환기준 동적화, `detectConversionBasis`) 완료. 본 문서는 그 후속 "Level 2".

## Goal

캠페인 목표(사전예약/일반)에 따라 결과표에서 목표와 무관한 지표 컬럼(매출·ROAS)을 **흐리게(dim)** 처리해, 마케터가 목표에 맞는 핵심 지표에 집중하도록 한다. 목표는 캠페인 유형(ua_type)에서 자동감지하고, 사용자가 수동으로 오버라이드할 수 있다.

## Architecture

기존 결과표의 **CSS 상태클래스 기반 컬럼 토글 패턴**(`#resultTable:not(.show-mmp) .col-mmp { display:none }`)을 그대로 확장한다. 컬럼에 시맨틱 클래스를 부여하고, `#resultTable`에 목표 상태클래스를 토글하면 CSS가 dim한다. `renderResultTableRows` 로직·정렬·점수 계산은 변경하지 않는다(셀에 클래스만 추가). 접근법 후보 중 이 방식(A)을 채택 — 기존 인프라와 동일 계층, JS 최소, 렌더 핫루프 불변.

**핵심 개념 분리:**
- **전환 기준 라벨**(전환(사전예약)/전환(설치)) = "전환 이벤트가 무엇인가"라는 **데이터 사실** → 기존 `detectConversionBasis()`가 계속 담당. 본 기능은 이 라벨을 **변경하지 않는다.**
- **목표(objective)** = "어떤 컬럼을 흐리게 볼까"라는 **표시 렌즈** → 신규. 컬럼 dim만 제어.

## 목표 정의 및 컬럼 매핑

목표는 2종: `사전예약`, `일반`.

| 목표 | 흐리게(dim) 컬럼 | 정상 유지 | 근거 |
|---|---|---|---|
| **사전예약** | 매출, ROAS | 나머지 전 컬럼 | 사전예약 단계엔 설치·매출 이벤트가 없어 매출·ROAS 항상 —(빈값) |
| **일반** (설치·매출 통합) | (없음) | 전 컬럼 | 설치·매출 캠페인은 매출·ROAS가 다운스트림 품질 신호로 유효 |

- dim을 실제로 발생시키는 목표는 `사전예약` 하나. `일반`은 전 컬럼 정상 표시.
- dim 대상 = **매출, ROAS 2개 컬럼만.** 보조 지표(비용·노출수·클릭수·CTR)와 종합점수(총점·등급·성과·MMP점수)는 목표 무관 항상 정상.
- `MMP 점수` 컬럼은 이미 데이터 게이트(`show-mmp`)로 사전예약 시 자동 숨김되므로 dim 대상에서 제외.

## Components

### 1. 감지·상태 (JS, `step1_integrated.html`)

- `detectObjective()` — `detectConversionBasis() === '사전예약'`이면 `'사전예약'`, 아니면 `'일반'`을 반환. 기존 `detectConversionBasis`(2337행 부근)를 단일 소스로 재사용.
- `window.__objectiveOverride` — 수동 오버라이드 상태. `null`(자동) \| `'사전예약'` \| `'일반'`. 초기값 `null`.
- `effectiveObjective()` — `window.__objectiveOverride`가 non-null이면 그 값, 아니면 `detectObjective()`.
- `applyObjectiveClass()` — `#resultTable`에 `obj-prereg` 클래스를 `effectiveObjective() === '사전예약'`일 때 토글(add/remove).

### 2. 컬럼 태깅 (HTML, `step1_integrated.html`)

헤더 2곳 + 셀 2곳에 시맨틱 클래스 추가(값·정렬·스타일 불변, 클래스만 추가):

- ROAS 헤더 — 1629행 `<th id="thM4" class="has-tooltip" ...>` → `class="has-tooltip col-roas"`
- 매출 헤더 — 1630행 `<th class="num has-tooltip" data-sortkey="매출" ...>` → `class="num has-tooltip col-revenue"`
- ROAS 셀 — 5137행 `<td style="text-align: right; font-weight: 600; color: #1f2937;">${m4}</td>` → `<td class="col-roas" style="...">${m4}</td>`
- 매출 셀 — 5138행 `<td style="text-align: right;">${mRev}</td>` → `<td class="col-revenue" style="...">${mRev}</td>`

### 3. CSS dim (`step1_integrated.html` `<style>`, `col-mmp` 규칙 인접)

```css
#resultTable.obj-prereg .col-revenue,
#resultTable.obj-prereg .col-roas { opacity: 0.4; }
```

기존 `#resultTable:not(.show-mmp) .col-mmp { display:none }`(819행 부근) 규칙과 같은 블록에 둔다.

### 4. 셀렉터 UI (HTML + JS)

- 레이어 토글 버튼(`layerBtnAds`/`layerBtnMmp`) 인접 위치에 작은 `<select id="objectiveSelect">` 추가. 옵션: `자동감지`(value=`auto`) / `사전예약`(value=`사전예약`) / `일반`(value=`일반`). 기본 선택 `자동감지`.
- `change` 리스너: value가 `auto`면 `window.__objectiveOverride = null`, 아니면 해당 값. 이후 `applyObjectiveClass()` 호출.
- (정확한 삽입 마크업 위치는 구현 계획에서 확정 — 레이어 토글 컨테이너 내.)

## Data Flow

1. 데이터 로드 → `window.__campaignCanonical` 채워짐 → `detectConversionBasis()`/`detectObjective()` 판정 가능.
2. `switchAnalysisLayer(layer)` 호출 시(레이어 전환·최초 렌더) 말미에 `applyObjectiveClass()` 호출 → `#resultTable.obj-prereg` 갱신.
3. 결과표 재렌더(`renderResultTableRows`) 후에도 `#resultTable`의 클래스는 유지되므로 dim 상태 보존(테이블 요소 자체는 재생성 안 됨, tbody 행만 교체).
4. 사용자가 `objectiveSelect` 변경 → override 세팅 → `applyObjectiveClass()` → dim 즉시 갱신.
5. dim은 레이어(ADS/MMP)와 무관하게 `obj-prereg` 클래스만으로 적용.

## Error Handling / Edge Cases

- `window.__campaignCanonical`가 비어있음(맵 없음) → `detectConversionBasis()`가 `'설치'` 반환 → `detectObjective()` = `'일반'` → dim 없음(안전 기본).
- 오버라이드가 `null`인데 데이터 로드 전 호출 → `detectObjective()`가 `'일반'` 반환(안전), 로드 후 `switchAnalysisLayer` 재호출 시점에 재판정.
- 사전예약 소재를 수동으로 `일반` 전환 → 매출·ROAS 컬럼 드러나지만 값은 —(빈값). 의도된 동작(사용자가 명시적으로 표시 요청).
- `전환(사전예약)` 라벨은 오버라이드와 무관하게 `detectConversionBasis` 기준 유지 — 목표 렌즈와 데이터 사실 라벨을 분리.

## Testing / Verification

정적 HTML/JS 사이트이므로 preview(브라우저) 기반 검증:

1. **zeus(사전예약, 전 캠페인 NU-Pre)**: 최초 로드 시 매출·ROAS 컬럼 dim(opacity 0.4), 셀렉터 `자동감지` 상태.
2. **셀렉터 `일반` 선택** → 매출·ROAS dim 해제(opacity 1). **`사전예약` 재선택** → 다시 dim. **`자동감지`** → 다시 dim(NU-Pre 자동판정).
3. **펩(일반/비 NU-Pre)**: 최초 로드 시 dim 없음.
4. **레이어 전환**(ADS↔MMP)해도 dim 상태 유지.
5. **Node 단위 확인**: `detectObjective()`가 NU-Pre 맵→`'사전예약'`, 혼합/빈맵→`'일반'`; `effectiveObjective()`가 override 우선.

기존 pytest(파이프라인) 무회귀도 확인(HTML만 변경이라 영향 없음 예상).

## Out of Scope (YAGNI)

- 목표별 **정렬·점수 재계산** — 기존 총점(Google Ads 기준) 유지.
- 세 번째 `매출` 목표 — `일반`으로 통합(설치·매출 컬럼 처리 동일).
- 컬럼 **숨김(hide)** — dim(흐리게)만.
- 목표별 헤더 라벨 변경 — `setLayerHeaders`/`전환(사전예약)` 라벨 불변.
- 목표 상태의 영속(localStorage) — 세션 내 상태만.
