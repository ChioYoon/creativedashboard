# Batch E — Step 2 군집화 개선 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Step 2 승리공식/중단패턴에서 고·저 공유 태그를 '공통 패턴'으로 분리하고(⑩), 최고 성과 소재 옆에 최저 성과 소재 카드를 추가한다(⑪).

**Architecture:** `buildPatternInsights`(분류부) + `buildPatternInsightsHtml`(공통 컬럼) + `renderInsights`(최저 카드). 전부 `step2_clustering.html` 인라인. 군집 알고리즘·점수 무변경.

**Tech Stack:** 바닐라 JS. preview 서버 + `preview_eval`(캐시 우회 `?_=<ts>`, 함수 단위 합성 단언).

## Global Constraints

- 분류·표시만 변경 — 군집화(Union-Find·±1σ)·점수·데이터 무변경.
- ⑩ 임계값: 공통 = 양쪽 비율 ≥ 50% AND |lift| < 12%p. 강한 lift(|lift|≥12%p)는 승리/중단 유지.
- ⑪ `type:'alert'`(⚠️) 재사용. 최저는 단일 소재일 때(topMat===bottomMat) 미표시.

---

### Task 1: ⑩ 공통 패턴 분리 + ⑪ 최저 소재 카드

**Files:** Modify `step2_clustering.html` — `buildPatternInsights`(2215-2239), `buildPatternInsightsHtml`(2241-2261), `renderInsights`(topMat 블록 2342 뒤).

- [ ] **Step 1: buildPatternInsights — shared 버킷**

`buildPatternInsights`의 `const rows = []; cand.forEach(...) ... return {...}` 부분(2226-2238)을 교체:
```js
  const WEAK = 0.12, BOTH = 0.5;
  const win = [], lose = [], shared = [];
  cand.forEach(t => {
    const topN = winners.filter(m => tagsOf(m).includes(t)).length;
    const botN = losers.filter(m => tagsOf(m).includes(t)).length;
    if (topN < 2 && botN < 2) return;
    const topR = topN / k, botR = botN / k, lift = topR - botR;
    const row = { tag: t, lift, topPct: Math.round(topR * 100), botPct: Math.round(botR * 100), topN, botN };
    if (Math.abs(lift) < WEAK) {
      if (Math.min(topR, botR) >= BOTH) shared.push(row);   // 양쪽 흔하고 변별력 낮음 → 공통
    } else if (lift >= WEAK) win.push(row);
    else lose.push(row);
  });
  return {
    winners: win.sort((a, b) => b.lift - a.lift || b.topPct - a.topPct).slice(0, 5),
    losers:  lose.sort((a, b) => a.lift - b.lift || b.botPct - a.botPct).slice(0, 5),
    shared:  shared.sort((a, b) => (b.topPct + b.botPct) - (a.topPct + a.botPct)).slice(0, 5),
    n, k,
  };
```
또한 함수 초입 `if (n < 4) return { winners: [], losers: [], n, k: 0 };` 에 `shared: []` 추가:
```js
  if (n < 4) return { winners: [], losers: [], shared: [], n, k: 0 };
```

- [ ] **Step 2: buildPatternInsightsHtml — 공통 패턴 컬럼**

`liftRow`/`col` 정의 다음, return 직전에 `sharedRow` 추가. 그리고 ic-body 의 중단패턴 col(2258) 다음에 공통 컬럼 삽입.

`col(...)` 정의(2250-2253) 다음에 추가:
```js
  const sharedRow = (r) => `<div style="display:flex;align-items:center;gap:8px;padding:5px 0;border-bottom:1px dashed var(--gray-line);">
      <span style="flex:1;font-size:12.5px;font-weight:600;color:var(--dark);">${escHtml(r.tag)}</span>
      <span style="font-size:10.5px;color:var(--gray-text);white-space:nowrap;">상위 ${r.topPct}% · 하위 ${r.botPct}%</span>
    </div>`;
```
2258(중단패턴 col) 다음 줄에 추가:
```js
        ${col('⛔ 중단패턴 (하위에서 더 흔한 태그)', pat.losers, false, '뚜렷한 저성과 태그 없음')}
        ${(pat.shared && pat.shared.length) ? `<div style="flex:1;min-width:220px;">
          <div style="font-size:12px;font-weight:700;color:var(--mid);margin-bottom:6px;">⚖️ 공통 패턴 <span style="font-weight:500;font-size:10.5px;color:var(--gray-text);">(고·저 공유 · 변별력 낮음)</span></div>
          ${pat.shared.map(sharedRow).join('')}
        </div>` : ''}
```

- [ ] **Step 3: renderInsights — 최저 소재 카드**

`renderInsights` 의 최고 소재 블록(topMat, `if (topMat) { ... insights.push({...}); }` 끝, 2342) 다음에 추가:
```js
  // 6b. 최저 소재 (최고와 대비)
  const bottomMat = allMats.length >= 2 ? allMats[allMats.length - 1] : null;  // allMats 는 topMat 산출에서 점수 내림차순 정렬됨
  if (bottomMat && topMat && bottomMat.idx !== topMat.idx) {
    const botCl = clusters.find(c => c.materials.some(m => m.idx === bottomMat.idx));
    insights.push({
      type: 'alert',
      icon: '⚠️',
      title: '최저 성과 소재',
      body: `<strong>${escHtml(bottomMat.name)}</strong>(${bottomMat.score}점)이 가장 낮은 성과를 보입니다.${botCl ? ` [${escHtml(botCl.name)}] 군집 소속.` : ''} 최고 성과 소재와 태그 조합을 비교해 보완·교체를 검토하세요.`,
      tags: (bottomMat.topTags || []).slice(0, 4)
    });
  }
```

- [ ] **Step 4: preview 검증 — ⑩ 패턴 분리 (함수 단위)**

`step2_clustering.html?_=<ts>` 로드 후 `preview_eval`(합성 클러스터):
```js
(function(){
  var mk = (score, tags) => ({ idx: Math.random(), name: 's'+score, score: score, tags: tags, topTags: tags });
  // 8소재: 공통=전체, 승리=상위2, 저효율=하위2
  var mats = [
    mk(9,['공통','승리']), mk(8,['공통','승리']),  // 상위 25%(k=2)
    mk(7,['공통']), mk(6,['공통']), mk(5,['공통']), mk(4,['공통']),
    mk(2,['공통','저효율']), mk(1,['공통','저효율'])  // 하위 25%
  ];
  var pat = buildPatternInsights([{ materials: mats }]);
  var tagsIn = arr => arr.map(r=>r.tag);
  return {
    winners: tagsIn(pat.winners), losers: tagsIn(pat.losers), shared: tagsIn(pat.shared),
    공통_not_in_winners: !tagsIn(pat.winners).includes('공통'),
    공통_in_shared: tagsIn(pat.shared).includes('공통'),
    승리_in_winners: tagsIn(pat.winners).includes('승리'),
    저효율_in_losers: tagsIn(pat.losers).includes('저효율')
  };
})()
```
Expected: `공통_not_in_winners:true`, `공통_in_shared:true`, `승리_in_winners:true`, `저효율_in_losers:true`. 이어서 `buildPatternInsightsHtml([{materials:mats}]).indexOf('공통 패턴') !== -1` 확인.

- [ ] **Step 5: preview 검증 — ⑪ 최저 카드 (렌더)**

```js
(function(){
  var mk = (i, score, tags) => ({ idx: i, name: '소재'+i, score: score, tags: tags, topTags: tags });
  var mats = [mk(0,90,['A']), mk(1,70,['A','B']), mk(2,50,['B']), mk(3,30,['C']), mk(4,10,['C'])];
  var clusters = [{ id: 1, name: '테스트군집', materials: mats, avgScore: 50 }];
  try { renderInsights(clusters, { clusters: clusters }); } catch(e){ return { renderErr: String(e) }; }
  var grid = document.getElementById('insightGrid').textContent;
  return { hasTop: grid.indexOf('최고 성과 소재') !== -1, hasBottom: grid.indexOf('최저 성과 소재') !== -1 };
})()
```
Expected: `hasTop:true`, `hasBottom:true`. (renderErr 나오면 합성 클러스터에 누락 필드 보강 후 재시도.) `preview_console_logs`(error) → 없음.

- [ ] **Step 6: Commit**
```bash
git add step2_clustering.html
git commit -m "feat(step2): ⑩ 승리/중단 공통패턴 분리 + ⑪ 최저 성과 소재 카드"
```

---

## 실행 메모
- 인라인 변경 → pytest 무관. 검증은 preview `?_=<ts>` 로드 후 buildPatternInsights/renderInsights 합성 호출.
- `renderInsights(clusters, data)` 합성 호출이 누락 필드로 throw 시, 실제 Step2 데이터 로드(또는 필드 보강)로 대체.
