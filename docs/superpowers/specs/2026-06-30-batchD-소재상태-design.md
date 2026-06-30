# Batch D — ⑨ 소재 라이브/제외 상태 설계

**작성일:** 2026-06-30
**대상:** `step1_integrated.html` — 소재 목록 표(소재명 셀), 소재 상세 모달(`openPreviewModal`)
**요구(⑨):** 소재별 '라이브/제외' 상태를 기록·표시하되 **분석·점수·집계에는 영향을 주지 않는다**(표시 전용, 혼선 방지). 야간 재생성에도 유지.

## 결정 요약

「**자동 판정 기본 + 개인 수동 덮어쓰기(localStorage)**」.
- 자동: 클릭 0번에도 즉시 유용(최근 노출 유무로 라이브/중단).
- 수동: 의도적 제외 등 예외를 기록("체크 기록" 충족).
- 백엔드 불필요(정적 사이트), 야간 재생성에도 유지(소재 key 기준 클라이언트 저장).
- 탈락: 팀 공유 수동(커밋) = 매번 손이 많이 감 / 자동만 = 의도적 제외를 못 담음.

## 현황(컨텍스트)

- 소재는 `c.key`(=소재명)로 식별, 이미 표에 `data-rowkey="${escapeHtml(c.key)}"`(5197)로 존재 → 안정 식별자.
- 소재명 셀(5199-5204): `sigIconsHtml` + `<span>${c.key}</span>`.
- 활성 타이틀 id: `DataSource.getActiveTitleId()`(4199에서 사용).
- 일별 데이터: `creative.meta.kpi_daily` 엔트리 `{date, impressions, ...}`(Batch C에서 확인). date는 'YYYY-MM-DD' 정렬 가능 문자열.
- step1은 localStorage 미사용(Step2 핸드오프 sessionStorage만) → 개인 저장소 비어 있음.

## 상태 모델

소재별 **표시 상태**는 다음 우선순위로 결정:

1. **수동 오버라이드 존재** → 그 값 사용
   - `'live'` → 🟢 라이브(수동)
   - `'excluded'` → 🚫 제외(수동)
2. **오버라이드 없음 → 자동 판정**
   - 데이터 창 최신일(`globalMaxDate`) 기준 최근 `LIVE_LOOKBACK_DAYS`(2일) 내 **노출 > 0인 kpi_daily 엔트리 존재** → 🟢 라이브
   - 아니면(최근 노출 없음 / kpi_daily 없음) → ⚪ 중단

표시 상태는 3종: `🟢 라이브` / `⚪ 중단` / `🚫 제외`. (라이브는 자동·수동 공통으로 동일 표기, 제외는 수동만 가능.)

## 함수 설계 (전부 `step1_integrated.html` 인라인)

```js
// 상수
const LIVE_LOOKBACK_DAYS = 2;
const STATUS_STORE_PREFIX = 'r_team_status_';

// 오버라이드 저장소 (타이틀별 1개 객체)
function statusStoreKey() {
  const tid = (window.DataSource && DataSource.getActiveTitleId && DataSource.getActiveTitleId()) || '_';
  return STATUS_STORE_PREFIX + tid;
}
function loadStatusOverrides() {
  try { return JSON.parse(localStorage.getItem(statusStoreKey()) || '{}') || {}; }
  catch (_) { return {}; }
}
function saveStatusOverride(creativeKey, value /* 'live' | 'excluded' | null */) {
  const m = loadStatusOverrides();
  if (value === null) delete m[creativeKey]; else m[creativeKey] = value;   // null = 자동으로 복귀
  try { localStorage.setItem(statusStoreKey(), JSON.stringify(m)); } catch (_) {}
}

// 데이터 창 최신일 (전체 소재의 kpi_daily 중 최대 date). 없으면 null.
function computeGlobalMaxDate(creatives) {
  let max = null;
  (creatives || []).forEach(c => {
    const daily = (c.meta && c.meta.kpi_daily) || [];
    daily.forEach(d => { const s = String(d.date || ''); if (s && (max === null || s > max)) max = s; });
  });
  return max;  // 'YYYY-MM-DD' or null
}

// 자동 판정: 'live' | 'stopped'
function deriveAutoStatus(creative, globalMaxDate) {
  if (!globalMaxDate) return 'stopped';
  const daily = (creative.meta && creative.meta.kpi_daily) || [];
  const maxMs = new Date(globalMaxDate).getTime();
  const recent = daily.some(d => {
    const imp = Number(d.impressions || 0);
    if (imp <= 0) return false;
    const diff = (maxMs - new Date(String(d.date)).getTime()) / 86400000;
    return diff >= 0 && diff <= LIVE_LOOKBACK_DAYS;
  });
  return recent ? 'live' : 'stopped';
}

// 최종 표시 상태: 'live' | 'stopped' | 'excluded'
function resolveStatus(creative, globalMaxDate, overrides) {
  const ov = overrides[creative.key];
  if (ov === 'live' || ov === 'excluded') return ov;
  return deriveAutoStatus(creative, globalMaxDate);
}

// 표 배지 (소재명 셀 앞). 컴팩트 도트 + native tooltip.
function statusBadgeHtml(status) {
  const map = {
    live:     { dot: '#22c55e', label: '라이브' },
    stopped:  { dot: '#9ca3af', label: '중단(최근 노출 없음)' },
    excluded: { dot: '#ef4444', label: '제외(수동)' },
  };
  const s = map[status] || map.stopped;
  const mark = status === 'excluded' ? '🚫' : `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${s.dot};"></span>`;
  return `<span class="status-badge" title="${s.label}" style="display:inline-flex;align-items:center;flex:none;">${mark}</span>`;
}
```

### 렌더 연결

- `renderResultTableRows` 진입부에서 1회: `const _ovr = loadStatusOverrides(); const _gmax = computeGlobalMaxDate(creatives);`
- 각 행에서 `const _st = resolveStatus(c, _gmax, _ovr);`
- 소재명 셀(5200-5203)의 `${sigIconsHtml}` 앞에 `${statusBadgeHtml(_st)}` 삽입.

### 모달 세그먼트 컨트롤

`openPreviewModal(index)`의 content에 상태 컨트롤 블록 추가:
```
상태: [ 자동 ] [ 라이브 ] [ 제외 ]
```
- 현재 오버라이드 값에 따라 활성 버튼 강조(`자동` = 오버라이드 없음).
- 클릭 핸들러: `자동`→`saveStatusOverride(key, null)`, `라이브`→`saveStatusOverride(key, 'live')`, `제외`→`saveStatusOverride(key, 'excluded')`. 저장 후 표가 떠 있으면 `renderResultTableRows(window.currentCreatives)` 재호출로 배지 즉시 갱신(없으면 다음 렌더 시 반영). 함수 시그니처: `renderResultTableRows(creatives)`(5115), 전역 `window.currentCreatives`(5239 세팅), `openPreviewModal(index)`(6720)는 `currentCreatives[index]` 사용.
- 모달은 `data-rowkey`처럼 소재 key를 안전히 보관(escape)해 핸들러에 전달.

## 불변(반드시 유지)

- **분석·점수·등급·군집·요약·집계 전혀 변경 없음.** `resolveStatus`/배지는 어떤 집계 입력에도 들어가지 않음. '제외' 표식 소재도 모든 계산에 그대로 포함.
- 자동 판정은 Google Ads 노출(kpi_daily.impressions) 기준 — 레이어 토글(ads/mmp)과 무관하게 동일 표기.
- 오버라이드 저장소는 타이틀별 분리, 소재 key 기준 → 야간 재생성으로 데이터가 새로 와도 유지. 자동 판정은 매 렌더 시 새 데이터로 재계산되어 항상 최신.

## 엣지 케이스

- kpi_daily 없는 소재(미집행) → 자동 `stopped`(중단). 정상.
- `globalMaxDate` null(전체 일별 없음) → 전부 `stopped`. 정상.
- 삭제·개명된 소재의 잔여 오버라이드 키 → `resolveStatus`가 해당 소재를 못 만나면 그냥 미사용(무해, 정리 불필요).
- localStorage 차단/용량초과 → try/catch로 무시, 자동 판정으로 동작(기능 degrade, 오류 없음).
- XSS: 소재 key는 모달 핸들러 전달 시 기존 `escapeHtml`/`data-rowkey` 패턴 사용.

## 비목표(이번 제외)

- "라이브만 보기" 표시 전용 뷰 필터 — 추후.
- 팀 공유 동기화(상태 내보내기→커밋 워크플로) — 추후. 정적 사이트라 자동 불가.
- 상태에 따른 정렬/그룹 키 추가 — 없음(표시 전용 원칙).

## 검증 (preview)

`step1_integrated.html?_=<ts>` 로드 → gd 분석 후:
1. **자동 판정**: `computeGlobalMaxDate(currentCreatives)` 반환 날짜 확인. 임의 소재에 대해 `deriveAutoStatus` 가 최근 노출 유무와 일치('live'/'stopped').
2. **오버라이드 왕복**: `saveStatusOverride(key,'excluded')` → `resolveStatus` 가 'excluded' → `saveStatusOverride(key,null)` → 자동값 복귀. localStorage `r_team_status_<titleId>` 에 키 존재/삭제 확인.
3. **표 배지**: 렌더 후 소재명 셀에 `.status-badge` 존재(3종 상태가 표에 나타나는지 textContent/DOM).
4. **불변**: 오버라이드 전/후 표의 점수·등급·집계 합계 동일(상태가 계산에 영향 없음).
5. 콘솔 error 0.
