# 게임 성격 맥락 주입 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AI 인사이트·성과 보고서 프롬프트에 게임 성격(장르·루프·톤·소구) 맥락을 brand_briefs 압축본에서 주입해 분석 품질을 높인다.

**Architecture:** gemini-api.js에 순수 함수 `GeminiPrompts.buildGameCharacterContext(bb, oneLine)` 1개 추가. step1의 두 호출부(인사이트 ~8780, 보고서 generateSummaryReport)에서 `window._brandBriefs[tid]`로 맥락을 만들어 각 프롬프트 빌더에 인자로 전달. brand_briefs.json에 선택 필드(genre·core_loop·core_appeals) 실출처 소싱 추가.

**Tech Stack:** Vanilla JS (step1_integrated.html 인라인 + js/gemini-api.js 외부). JS 단위 러너 없음 → 검증은 브라우저 preview + javascript_tool assert(이 세션 기존 패턴).

## Global Constraints

- 모든 답변·주석 한국어(코드/식별자 예외). CLAUDE.md.
- gemini-api.js 프롬프트 빌더는 순수 유지 — window 접근 금지, 맥락은 인자 수령(기존 `sharedContext` 패턴).
- 순수 가산·graceful: bb/필드 없으면 빈 문자열 → 기존 동작 불변. 점수·등급·피로도·제외추천(KPI 기반) 무영향.
- 프롬프트 문자열만 변경 — 슬롯 파싱 스키마(parseScoringSlots 등) 불변.
- 데이터 날조 금지 — genre/core_appeals는 실출처(brief·game_context md) 있는 타이틀만.
- step1_integrated.html 로직은 HTML 내 인라인 블록 직접 수정(외부 원본 반영 안 됨). gemini-api.js는 외부 파일 그대로 수정.
- 커밋 attribution: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

### Task 1: `buildGameCharacterContext` 순수 함수

**Files:**
- Modify: `js/gemini-api.js` (GeminiPrompts 객체에 메서드 추가, `scoringInsight` 정의 근처)

**Interfaces:**
- Produces: `GeminiPrompts.buildGameCharacterContext(bb, oneLine=false) → string`
  - bb: brand_briefs 엔트리 객체 또는 falsy.
  - oneLine=true: 한 줄(값만 ` · ` 결합, 접두 `게임 성격: `, ≤300자) — 인사이트 인라인용.
  - oneLine=false: 헤더+불릿 블록(≤500자) — 보고서용.
  - 유효 필드 없으면 `''`.

- [ ] **Step 1: 검증 스니펫 작성(실패 확인용)**

브라우저 preview 로드 후 javascript_tool 로 실행할 assert:

```js
const F = GeminiPrompts.buildGameCharacterContext;
const bb = { genre:'경쟁형 MMORPG', core_loop:'전투 성장·아티산 경제', tone:'웅장·그리스신화', cta_tone:'신화적 압도 / 지양 린나류', characters:'나이트 / 버서커 / NPC 판도라', core_appeals:'경쟁 > 수집·육성' };
const one = F(bb, true);
const block = F(bb, false);
({
  emptyOnNull: F(null) === '' && F(undefined) === '',
  oneLineHasPrefix: one.startsWith('게임 성격:'),
  oneLineNoNewline: !one.includes('\n'),
  oneLineCap: one.length <= 300,
  blockHasHeader: block.includes('[게임 성격'),
  blockHasGenre: block.includes('경쟁형 MMORPG'),
  blockCap: block.length <= 500,
  emptyFields: F({}) === ''
})
```

- [ ] **Step 2: 실행해 실패 확인**

preview_start(name: "cloop-worktree") → navigate step1_integrated.html → javascript_tool 로 위 스니펫.
Expected: `GeminiPrompts.buildGameCharacterContext is not a function` (미정의).

- [ ] **Step 3: 최소 구현**

`js/gemini-api.js` GeminiPrompts 객체 내 `scoringInsight(...)` 메서드 앞에 추가:

```js
  // 게임 성격 맥락 — brand_briefs 압축본을 분석 배경으로. oneLine=인사이트 인라인 / false=보고서 블록.
  // 순수 함수(window 접근 없음). 로어 아님 — brand_briefs 가 이미 distillation.
  buildGameCharacterContext(bb, oneLine = false) {
    if (!bb || typeof bb !== 'object') return '';
    const parts = [];
    const genreLoop = [bb.genre, bb.core_loop].filter(Boolean).join(' · ');
    if (genreLoop) parts.push(['장르/핵심 루프', genreLoop]);
    if (bb.tone) parts.push(['브랜드 톤', bb.tone]);
    if (bb.core_appeals) parts.push(['핵심 소구', bb.core_appeals]);
    if (bb.cta_tone) parts.push(['CTA 톤', bb.cta_tone]);
    if (bb.characters) parts.push(['등장 캐릭터', String(bb.characters).slice(0, 80)]);
    if (!parts.length) return '';
    if (oneLine) {
      const s = '게임 성격: ' + parts.map(p => p[1]).join(' · ');
      return s.length > 300 ? s.slice(0, 300) : s;
    }
    const body = '[게임 성격 — 분석 배경. 소재가 무엇을 소구하는지 해석에만 사용, 데이터 판단이 우선]\n'
      + parts.map(p => `- ${p[0]}: ${p[1]}`).join('\n');
    return body.length > 500 ? body.slice(0, 500) : body;
  },
```

- [ ] **Step 4: 실행해 통과 확인**

javascript_tool 로 Step 1 스니펫 재실행(preview 재로드 후).
Expected: 모든 키 `true`.

- [ ] **Step 5: 커밋**

```bash
git add js/gemini-api.js
git commit -m "feat(gemini): buildGameCharacterContext — 게임 성격 맥락 빌더(순수)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: brand_briefs.json 선택 필드 소싱 (zeus·tougenanki)

**Files:**
- Modify: `js/brand_briefs.json` (zeus·tougenanki 엔트리)

**Interfaces:**
- Consumes: Task 1 빌더가 읽는 `genre`·`core_loop`·`core_appeals` 필드.
- Produces: 두 타이틀 엔트리에 실출처 소싱된 선택 필드.

출처: zeus=`pipeline/game_context/zeus.md` §1-2, tougenanki=`brief_tougenanki.json`(fact.genre / usp[]).

- [ ] **Step 1: zeus 엔트리에 필드 추가**

`js/brand_briefs.json` 의 `"zeus"` 객체에 `"characters"` 앞(또는 `_source` 뒤)에 추가:

```json
    "genre": "경쟁형 오픈필드 MMORPG (대규모 PvP/RvR)",
    "core_loop": "전투 위주 성장 · 아티산 경제 클래스(제작·거래) · AI 자동성장 모드 · 아카디아 제전 RvR 엔드콘텐츠",
```

- [ ] **Step 2: tougenanki 엔트리에 필드 추가**

`js/brand_briefs.json` 의 `"tougenanki"` 객체에 추가:

```json
    "genre": "일본 IP 다크판타지 턴제 RPG (수집형)",
    "core_appeals": "IP·캐릭터 > 전투 쾌감 > 스토리·세계관 > 그래픽·비주얼",
```

- [ ] **Step 3: JSON 유효성 + 빌더 실동작 확인**

```bash
python -c "import json;d=json.load(open('js/brand_briefs.json',encoding='utf-8'));print(d['zeus']['genre']);print(d['tougenanki']['core_appeals'])"
```
Expected: 두 값 출력, 예외 없음.

이어 preview 재로드 후 javascript_tool:
```js
const d = await fetch('js/brand_briefs.json').then(r=>r.json());
const b = GeminiPrompts.buildGameCharacterContext(d.tougenanki, false);
({ hasGenre: b.includes('턴제'), hasAppeals: b.includes('IP·캐릭터 >'), zeusOneLine: GeminiPrompts.buildGameCharacterContext(d.zeus, true).includes('MMORPG') })
```
Expected: 모두 `true`.

- [ ] **Step 4: 커밋**

```bash
git add js/brand_briefs.json
git commit -m "data(brand_briefs): zeus·tougenanki genre·core_loop·core_appeals 소싱

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: AI 인사이트 호출부 맥락 주입

**Files:**
- Modify: `step1_integrated.html` (~8780, `runScoringAIInsight` 내 `scoringInsight` 호출)

**Interfaces:**
- Consumes: `GeminiPrompts.buildGameCharacterContext(bb, true)` (Task 1), `window._brandBriefs` (기존 로드).
- Produces: 인사이트 프롬프트 header 에 `[게임 성격: …]` 인라인 삽입(gemini-api.js:551 기존 `context` 경로 활용).

- [ ] **Step 1: 검증 스니펫(실패 확인용)**

javascript_tool 로 프롬프트에 게임 성격이 들어가는지 확인:
```js
const d = await fetch('js/brand_briefs.json').then(r=>r.json());
window._brandBriefs = d;
const one = GeminiPrompts.buildGameCharacterContext(d.zeus, true);
const p = GeminiPrompts.scoringInsight([{소재명:'a',IPM:5,CPA:100,유형:'BNR'}],[{소재명:'b',IPM:1,CPA:900,유형:'BNR'}],{ tagCols:[], isPaid:false, context: one });
JSON.stringify(p).includes('게임 성격') // 구현 전엔 호출부 미전달이라 실서비스 프롬프트엔 없음 — 이 스니펫은 함수 자체 검증
```
호출부 미수정 상태 확인: `step1_integrated.html` ~8780 라인이 `{ tagCols, isPaid }` 만 전달(게임 성격 없음).

- [ ] **Step 2: 실패 확인**

`step1_integrated.html` ~8780 현재:
```js
        const prompts = GeminiPrompts.scoringInsight(highPerf, lowPerf, { tagCols, isPaid });
```
`context` 미전달 = 게임 맥락 없음(실패 상태).

- [ ] **Step 3: 호출부 수정**

~8780 블록을 다음으로 교체(직전에 tid·bb·gameCtx 생성):

```js
        const _giTid = (window.DataSource && DataSource.getActiveTitleId && DataSource.getActiveTitleId()) || '';
        const _giBB = (window._brandBriefs && window._brandBriefs[_giTid]) || null;
        const _giGameCtx = GeminiPrompts.buildGameCharacterContext(_giBB, true);  // 인사이트=인라인 1줄
        const prompts = GeminiPrompts.scoringInsight(highPerf, lowPerf, { tagCols, isPaid, context: _giGameCtx });
```

- [ ] **Step 4: 통과 확인**

preview 재로드 → 타이틀 zeus 선택 상태에서 javascript_tool:
```js
const tid = DataSource.getActiveTitleId();
const bb = window._brandBriefs[tid];
const one = GeminiPrompts.buildGameCharacterContext(bb, true);
const p = GeminiPrompts.scoringInsight([{소재명:'a',IPM:5,CPA:100,유형:'BNR'}],[{소재명:'b',IPM:1,CPA:900,유형:'BNR'}],{tagCols:[],isPaid:false,context:one});
({ ctxBuilt: one.length>0, inPrompt: JSON.stringify(p).includes('게임 성격') })
```
Expected: 게임 성격 있는 타이틀서 둘 다 `true`. 콘솔 에러 0.

- [ ] **Step 5: 커밋**

```bash
git add step1_integrated.html
git commit -m "feat(insight): 게임 성격 맥락 주입 — scoringInsight context 전달

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: 성과 보고서 맥락 주입

**Files:**
- Modify: `step1_integrated.html` (`buildReportNarrativePrompt` ~6049, `generateSummaryReport` ~5988)

**Interfaces:**
- Consumes: `GeminiPrompts.buildGameCharacterContext(bb, false)` (Task 1), `window._brandBriefs`.
- Produces: 보고서 프롬프트에 기존 `[게임/UA 컨텍스트]` 앞에 `[게임 성격]` 블록 삽입.

- [ ] **Step 1: 빌더 시그니처 확장(실패 확인용)**

`buildReportNarrativePrompt(data, tags, note = '', sharedContext = '')` → `gameChar = ''` 파라미터 추가 예정. 현재 미존재 = 보고서에 게임 성격 없음(실패 상태).

- [ ] **Step 2: 실패 확인**

`buildReportNarrativePrompt` 현재 시그니처에 `gameChar` 없음. `generateSummaryReport`도 전달 안 함.

- [ ] **Step 3: 빌더 + 호출부 수정**

(a) `buildReportNarrativePrompt` 시그니처(~6049):
```js
    function buildReportNarrativePrompt(data, tags, note = '', sharedContext = '', gameChar = '') {
```

(b) 같은 함수 내 `if (sharedContext) {` 블록(~6072) **바로 앞**에 삽입:
```js
      if (gameChar) {
        L.push('');
        L.push(gameChar);  // [게임 성격 …] 블록 — 분석 배경(무엇을 소구하는 게임인지)
      }
```

(c) 래퍼 `buildReportNarrative` 시그니처(~6151)에 `gameChar` 추가:
```js
    async function buildReportNarrative(comparison, creatives, note = '', sharedContext = '', gameChar = '') {
```

(d) 그 함수 내 `buildReportNarrativePrompt` 호출(~6157)에 gameChar 전달:
```js
          const prompt = buildReportNarrativePrompt(data, tags, note, sharedContext, gameChar);
```

(e) `generateSummaryReport`(~5988) — 기존 `sharedContext` 생성부(~6001)와 `buildReportNarrative` 호출부(~6002)를 다음으로 교체:
```js
        const sharedContext = _extractUaContext(window.__gameContext || '');
        const _rTid = (window.DataSource && DataSource.getActiveTitleId && DataSource.getActiveTitleId()) || '';
        const _rBB = (window._brandBriefs && window._brandBriefs[_rTid]) || null;
        const _rGameChar = GeminiPrompts.buildGameCharacterContext(_rBB, false);  // 보고서=블록
        try { const r = await buildReportNarrative(cmp, window.currentCreatives, note, sharedContext, _rGameChar); narrative = r.text; narrativeIsRule = r.isRule; }
        finally { hideLoadingIndicator(); }
```
(기존 6001~6003 세 줄 대체 — `sharedContext` 선언 중복 주의: 기존 줄을 위 블록으로 통째 교체.)

- [ ] **Step 4: 통과 확인**

preview 재로드 → zeus 선택 → javascript_tool:
```js
const d = await fetch('js/brand_briefs.json').then(r=>r.json()); window._brandBriefs=d;
const gc = GeminiPrompts.buildGameCharacterContext(d.zeus, false);
const prompt = buildReportNarrativePrompt({kpis:{},comparison:{hasPrev:false}}, null, '', '', gc);
({ hasGameChar: prompt.includes('[게임 성격'), hasGenre: prompt.includes('MMORPG') })
```
Expected: 둘 다 `true`. 콘솔 에러 0.

- [ ] **Step 5: 커밋**

```bash
git add step1_integrated.html
git commit -m "feat(report): 게임 성격 맥락 주입 — buildReportNarrativePrompt gameChar

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: 통합 회귀 확인 + 캐시버스터

**Files:**
- Modify: `step1_integrated.html` (`gemini-api.js?v=` 캐시버스터 — pre-commit 훅 자동, 수동 불요 시 생략)

- [ ] **Step 1: 전체 pytest(파이프라인 무영향 재확인)**

```bash
python -m pytest -q
```
Expected: 188 passed (JS 변경이라 Python 스위트 불변).

- [ ] **Step 2: step1 콘솔 0 + 핵심 페이지 로드**

preview_start → navigate step1_integrated.html → read_console_messages.
Expected: "✅ Step 1 통합 페이지 로드 완료", 에러 0.

- [ ] **Step 3: 무 브리프 타이틀 graceful 확인**

javascript_tool:
```js
({ noBB: GeminiPrompts.buildGameCharacterContext(null, true) === '' && GeminiPrompts.buildGameCharacterContext(null, false) === '',
   gdMinimal: GeminiPrompts.buildGameCharacterContext((await fetch('js/brand_briefs.json').then(r=>r.json())).gd, false).length > 0 })
```
Expected: `noBB:true`(빈 브리프 안전), `gdMinimal:true`(genre 없어도 tone/characters로 블록 생성).

- [ ] **Step 4: 최종 커밋(있으면)**

```bash
git add -A
git commit -m "chore: 게임 성격 맥락 주입 통합 검증

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>" || echo "변경 없음"
```

---

## 검증 요약

- Task 1: 빌더 순수·graceful·oneLine/block·상한.
- Task 2: 실출처 데이터, JSON 유효.
- Task 3: 인사이트 프롬프트에 게임 성격 인라인 유입(무료·전 타이틀).
- Task 4: 보고서 프롬프트에 게임 성격 블록 유입.
- Task 5: pytest 188·콘솔 0·graceful.
