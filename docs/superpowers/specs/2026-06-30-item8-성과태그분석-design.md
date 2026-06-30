# ⑧ 성과별 강·약점 태그 분석 설계

**작성일:** 2026-06-30
**대상:** `step1_integrated.html` — 전체 성과 요약 탭(`buildPerfRankingBlocks`/`renderCrossPerformanceCards`)
**요구(⑧):** 전체 성과 요약에서 **최우수/하위 소재의 강·약점 태그**를 분석해 표시. 분석·점수·집계 무변경(표시 전용).

## 결정 요약

「**2카드** — 🏆 최우수 소재 공통 강점 / ⚠️ 하위 소재 공통 약점」.
- 기존 'AI 태그' 패널(`renderSignalDistribution`, 2010)은 **전체 소재 빈도**만 → ⑧은 **성과 상·하위로 분리**해 "승자가 공유하는 강점 / 패자가 공유하는 약점"을 드러냄(Step 2 ⑩의 Step 1 요약판).
- 탈락: 2x2(정보량 과다) / lift 대비(Step 2 ⑩과 성격 중복).

## 현황(컨텍스트)

- 전체 성과 요약 = `Google Ads × MMP 교차 성과` + `성과 랭킹 (풀 상·하위)`(`buildPerfRankingBlocks`, 5978). 모두 `#crossPerformanceContainer`에 `renderCrossPerformanceCards`(6025)가 렌더.
- `container.innerHTML = crossHtml + perfHtml;`(6072) — 여기에 신규 블록 append.
- 데이터: 각 소재 `c.meta.strengths` / `c.meta.weaknesses` = Gemini 시각 분석 태그 배열.
- 점수: `c.TotalScore`(Google Ads 종합점수), Google Ads 데이터 보유 시만 유효(`c._ads && c._ads.imp > 0`).
- 재사용 CSS: `summary-block`/`summary-block-title`/`signal-perf-block`/`signal-perf-card`/`h4`/`ul`/`li`(전부 buildPerfRankingBlocks가 사용 중) → 인접 블록과 동일 스타일.

## 신규 함수 `buildPerfTagAnalysis(creatives)`

`buildPerfRankingBlocks`(5978-6023) 다음에 추가:
```js
    // ⑧ 성과별 강·약점 태그 — 최우수/하위 소재 그룹의 strengths/weaknesses 태그 집계 (표시 전용)
    function buildPerfTagAnalysis(creatives) {
      // Google Ads 점수(TotalScore) 유효 + 태그 보유 소재만
      const valid = (creatives || []).filter(c =>
        c && c._ads && c._ads.imp > 0 && typeof c.TotalScore === 'number' &&
        ((Array.isArray(c.meta?.strengths) && c.meta.strengths.length) ||
         (Array.isArray(c.meta?.weaknesses) && c.meta.weaknesses.length))
      );
      const n = valid.length;
      if (n < 4) return '';
      const sorted = valid.slice().sort((a, b) => b.TotalScore - a.TotalScore);
      const k = Math.min(3, Math.floor(n / 2));   // 상·하위 그룹 크기 (최소 2, 최대 3, 겹침 없음)
      const topG = sorted.slice(0, k);
      const botG = sorted.slice(n - k);
      const tally = (group, field) => {
        const m = new Map();
        group.forEach(c => {
          const list = (c.meta && c.meta[field]) || [];
          if (Array.isArray(list)) list.forEach(v => m.set(v, (m.get(v) || 0) + 1));
        });
        return [...m.entries()].sort((a, b) => b[1] - a[1]);
      };
      const topStr = tally(topG, 'strengths');
      const botWk  = tally(botG, 'weaknesses');
      if (!topStr.length && !botWk.length) return '';
      const li = (arr, denom) => arr.slice(0, 5).map(([label, cnt]) =>
        `<li><span>${escapeHtml(label)}</span><span style="color:#6b7280;font-size:12px;white-space:nowrap;">${cnt}건 (${Math.round((cnt / denom) * 100)}%)</span></li>`
      ).join('') || '<li style="color:#9ca3af;">(공통 태그 없음)</li>';
      return `
        <div class="summary-block">
          <div class="summary-block-title">성과별 강·약점 태그 <span style="font-weight:400;font-size:12px;color:var(--text-secondary,#6b7280);">(상위 ${k}개 · 하위 ${k}개 소재 기준 · Google Ads 종합점수)</span></div>
          <div class="signal-perf-block">
            <div class="signal-perf-card">
              <h4>🏆 최우수 소재 공통 강점</h4>
              <ul>${li(topStr, k)}</ul>
            </div>
            <div class="signal-perf-card">
              <h4>⚠️ 하위 소재 공통 약점</h4>
              <ul>${li(botWk, k)}</ul>
            </div>
          </div>
        </div>`;
    }
```

## 렌더 연결

`renderCrossPerformanceCards`(6072) `container.innerHTML = crossHtml + perfHtml;` 교체:
```js
      const perfTagHtml = buildPerfTagAnalysis(creatives || window.currentCreatives || []);
      container.innerHTML = crossHtml + perfHtml + perfTagHtml;
```

## 그룹 산정 규칙

- 유효 소재 n: Google Ads 점수 유효 + 태그(강점/약점 중 하나 이상) 보유.
- `k = min(3, floor(n/2))` — n=4·5 → k=2, n≥6 → k=3. 상·하위 겹침 없음.
- n<4 또는 양쪽 태그 집계 모두 빈 경우 빈 문자열 반환 → 블록 미표시(graceful).
- 지분% = 그룹 내 해당 태그 보유 소재 수 / 그룹 크기 k.

## 불변(반드시 유지)

- 점수·등급·집계·기존 'AI 태그' 패널(`renderSignalDistribution`)·성과 랭킹 전혀 변경 없음. 신규 표시 블록만 append.
- TotalScore = Google Ads 기준(②와 일관). 레이어 토글(ads/mmp)과 무관하게 동일 표기(점수 정렬 기준 불변).

## 엣지 케이스

- 태그 없는 소재(미태깅) → valid 필터에서 제외. 전부 미태깅이면 블록 숨김.
- Google Ads 데이터 없는 소재 → valid 제외(TotalScore 무의미).
- n<4(유효 소재 부족) → 숨김.
- 상위 그룹에 strengths가 하나도 없거나 하위 그룹에 weaknesses가 없으면 해당 카드에 "(공통 태그 없음)".

## 비목표(이번 제외)

- 태그 클릭 필터 연동 — 기존 'AI 태그' 패널이 담당.
- lift(상위−하위 출현율 차) 기반 대비 — Step 2 ⑩이 담당.
- MMP 점수 기준 그룹 분리 — TotalScore(Google Ads)로 고정.

## 검증 (preview)

`step1_integrated.html?_=<ts>` 로드 → gd 분석 후:
1. `buildPerfTagAnalysis(window.currentCreatives)` 가 비어있지 않은 HTML 반환(유효 n≥4 시). "성과별 강·약점 태그" 제목, 두 카드(🏆/⚠️) 포함.
2. 합성: n<4 입력 → `''` 반환(숨김). 태그 없는 입력 → `''` 반환.
3. 전체 성과 요약 탭 DOM(`#crossPerformanceContainer`)에 "성과별 강·약점 태그" 블록 존재.
4. 불변: 블록 추가 전후 점수 합계·기존 'AI 태그' 패널·성과 랭킹 동일.
5. 콘솔 error 0. 스크린샷으로 2카드 시각 확인.
