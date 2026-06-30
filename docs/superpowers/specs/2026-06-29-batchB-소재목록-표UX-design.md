# Batch B — 소재 목록 표 UX 설계

**작성일:** 2026-06-29
**대상:** `step1_integrated.html` (소재 목록 표 `#resultTable` · `renderResultTableRows` · `attachHeaderSort` · 관련 CSS)
**범위:** backlog 묶음 B — ② 지표 통일화 · ⑤ 컬럼 정렬 확장 · ⑥ 특정 소재 선택 필터

## 현황 (탐색 결과)

- 표는 단일 `#resultTable`(17컬럼). 레이어 토글(`switchAnalysisLayer`)이 `총점`/`등급` 의미를 ads↔mmp 로 바꾸고, CSS(912-915)로 `col-pctile`(성과)·`col-mmp`(MMP)를 레이어별로 dim/숨김.
- 행 렌더 `renderResultTableRows`(~5130-5189): mmp 레이어 분기에서 `scoreCell/gradeCell`을 MMP 값으로, ads 분기에서 Google Ads 값으로 계산.
- **컬럼 클릭 정렬은 이미 존재**: `sortByColumn(field,type)`(2508)·`updateSortIndicators`(2542)·`attachHeaderSort`(2551). 단 `attachHeaderSort` MAP(2554-2558)이 전환·CPA·IPM·ROAS·각 점수·총점·등급만 바인딩.

## ② 지표 통일화 — Google Ads 총점·MMP 점수·성과 상시 동시 표시

- **`총점`/`등급` 컬럼 = 항상 Google Ads 기준 고정**(레이어 무관). `renderResultTableRows` 의 if/else 직후 override:
  ```js
  const hasAdsScore = c._ads && c._ads.imp > 0;
  scoreCell = hasAdsScore ? c.TotalScore.toFixed(1) : dash;
  gradeCell = hasAdsScore ? `<span class="badge grade-${c.등급}">${c.등급}</span>` : dash;
  ```
  (mmp 레이어 분기의 scoreCell/gradeCell MMP 계산은 위 override로 대체됨.)
- **`MMP` 컬럼(col-mmp) = 항상 MMP 품질점수 표시**, **`성과` 컬럼(col-pctile) = 항상 Google Ads 백분위 표시** — 레이어별 숨김/dim CSS 제거.
  - CSS 912-913(`.layer-ads-primary .col-mmp` opacity) 및 914-915(`.layer-mmp-primary .col-pctile, .col-mmp` display:none) **삭제**.
  - **데이터 게이트는 유지**: 877(`:not(.show-pctile) .col-pctile`)·901(`:not(.show-mmp) .col-mmp`) — 해당 데이터 보유 소재가 하나도 없으면 컬럼 숨김(빈 컬럼 방지).
- 헤더 명확화: `총점` data-tip 에 "(Google Ads 기준)" 명시, `MMP` 헤더 라벨을 `MMP 점수`로.
- **m1-m4(전환·CPA·IPM·ROAS)·매출·비용·노출·클릭·CTR 는 현행 유지**(레이어 컨텍스트 값) — 이번 통일 대상은 점수/백분위 컬럼(사용자 예시: 총점·성과).
- 레이어 토글: 유지하되 컬럼 숨김 역할 제거 → **스코어카드 집계 + 기본 정렬 기준**만 전환.

## ⑤ 컬럼 정렬 확장

기존 `attachHeaderSort` MAP(2554-2558)에 미바인딩 컬럼 추가:
```js
const MAP = {
  '소재명': ['key', 'str'], '유형': ['유형', 'str'],
  '전환': ['전환', 'num'], 'CPA': ['CPA', 'num'], 'IPM': ['IPM', 'num'], 'ROAS': ['ROAS', 'num'],
  '매출': ['매출', 'num'], '비용': ['비용', 'num'], '노출수': ['노출수', 'num'], '클릭수': ['클릭수', 'num'], 'CTR': ['CTR', 'num'],
  '전환수점수': ['전환수점수', 'num'], 'CPA점수': ['CPA점수', 'num'], 'IPM점수': ['IPM점수', 'num'], 'ROAS점수': ['ROAS점수', 'num'],
  '총점': ['TotalScore', 'num'], '등급': ['TotalScore', 'num'],
  'MMP': ['__mmpscore', 'num'],
};
```
- 신규 직접 필드(매출·비용·노출수·클릭수·CTR·소재명·유형)는 `sortByColumn` 의 `rawVal` 이 `c[field]` 로 이미 처리(소재명은 `c.key`).
- `MMP` 정렬: `rawVal` 에 특수 케이스 추가 — `field === '__mmpscore'` 면 `(c.meta?.mmp_quality_score?.total) ?? null` 반환.
- `성과`(백분위)는 CTR/CVR/CPA 복합이라 단일 컬럼 정렬 비대상(기존 드롭다운 ctr/cvr/cpa 유지) — 헤더 정렬 MAP 제외.
- `미리보기`·`추이` 비정렬.

## ⑥ 특정 소재 선택 필터 (표 보기만)

- **체크박스 컬럼 추가**: 표 맨 앞에 행별 체크박스 + 헤더 전체선택 체크박스. (colspan 17→18 갱신.)
- 선택 상태: `window._selectedKeys = new Set()` (creative `key` 기준).
- 상단 액션 영역에 **"선택 N개만 보기"** 토글(`#selectedOnlyToggle`). ON + 선택 1개 이상이면 `renderResultTableRows` 가 선택 소재만 렌더.
- **상단 통계카드·전체 성과 요약·점수 산식은 전체 기준 고정** — 선택은 순수 표 뷰 필터(집계 불변). (사용자 결정.)
- 정렬(⑤)·레이어와 독립 공존: 선택 필터는 렌더 시 행 필터로만 작용.

## 검증 (preview)

`step1_integrated.html?_=<ts>` + 합성/실데이터(gd 등 MMP·Google Ads 보유) 로드, 분석 실행 후:
1. **②**: ads·mmp 레이어 양쪽에서 `총점`(Google Ads)·`MMP 점수`·`성과` 컬럼 모두 표시(`getComputedStyle(.col-mmp).display !== 'none'` 양 레이어). 총점 값이 레이어 전환에도 Google Ads 고정.
2. **⑤**: `매출`·`MMP`·`소재명` 헤더 클릭 → 해당 기준 정렬·▲/▼ 표시(`_headerSort.field` 확인). MMP 클릭 시 mmp_quality_score 순.
3. **⑥**: 행 2개 체크 + "선택만 보기" ON → tbody 행 2개, 통계카드(statTotal 등) 불변. OFF → 전체 복귀.
4. 콘솔 error 0.

## 비목표
- m1-m4·매출·비용·노출·클릭·CTR 의 레이어 컨텍스트 값 변경 없음.
- 성과(백분위) 단일 헤더 정렬 없음(복합 지표 — 드롭다운 유지).
- 선택에 따른 통계·요약 재집계 없음(표 뷰 필터만).
- 데이터·파이프라인 무변경.
