# Batch E — Step 2 군집화 개선 설계 (⑩·⑪)

**작성일:** 2026-06-29
**대상:** `step2_clustering.html` — `buildPatternInsights`/`buildPatternInsightsHtml`(승리공식·중단패턴), 인사이트 카드 생성부(최고/최저 소재)

## 현황

- `buildPatternInsights(clusters)`(2215): 소재를 점수순 정렬, 상·하위 25%(k) 추출. 각 후보 태그의 `lift = 상위비율 − 하위비율`. `winners=lift>0`, `losers=lift<0`, 각 상위 5개.
- `buildPatternInsightsHtml`(2241): 🏆 승리공식 / ⛔ 중단패턴 2컬럼.
- **문제(⑩)**: 양쪽 모두 흔한 태그(펩: 2D일러스트·혜택형, 상위 80%·하위 70% → lift +10%p)가 작은 양수 lift로 **승리공식에 섞여 변별력 흐림**.
- `최고 성과 소재` 인사이트(2331-2342, `topMat`)는 있으나 **최저 성과 소재 카드 없음(⑪)**.

## ⑩ 고/저성과 패턴 분리 — 공통 패턴 버킷

`buildPatternInsights`의 분류부를 교체. 임계값: 공통=양쪽 50%+, 약변별 컷=12%p.
```js
function buildPatternInsights(clusters) {
  const mats = (clusters || []).flatMap(c => c.materials || []);
  const n = mats.length;
  if (n < 4) return { winners: [], losers: [], shared: [], n, k: 0 };
  const sorted = [...mats].sort((a, b) => (b.score || 0) - (a.score || 0));
  let k = Math.max(2, Math.ceil(n * 0.25));
  if (k > Math.floor(n / 2)) k = Math.floor(n / 2);
  const winners = sorted.slice(0, k), losers = sorted.slice(n - k);
  const tagsOf = m => Array.isArray(m.tags) ? m.tags : [];
  const cand = new Set();
  winners.concat(losers).forEach(m => tagsOf(m).forEach(t => cand.add(t)));
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
      // else: 약변별·저빈도 → 미표시
    } else if (lift >= WEAK) win.push(row);
    else lose.push(row);
  });
  return {
    winners: win.sort((a, b) => b.lift - a.lift || b.topPct - a.topPct).slice(0, 5),
    losers:  lose.sort((a, b) => a.lift - b.lift || b.botPct - a.botPct).slice(0, 5),
    shared:  shared.sort((a, b) => (b.topPct + b.botPct) - (a.topPct + a.botPct)).slice(0, 5),
    n, k,
  };
}
```
- 강한 lift(예: 상위90%·하위50%, +40%p)는 공통이 아니라 승리공식에 남음(진짜 변별).
- 펩 80/70(lift +10%p, min 70%≥50%) → **공통 패턴**으로 분리(승리공식 미혼입).

`buildPatternInsightsHtml`에 **공통 패턴 컬럼** 추가(중단패턴 col 다음). 중립 스타일(±%p 색 없음, 상위%·하위%만):
```js
  const sharedRow = (r) => `<div style="display:flex;align-items:center;gap:8px;padding:5px 0;border-bottom:1px dashed var(--gray-line);">
      <span style="flex:1;font-size:12.5px;font-weight:600;color:var(--dark);">${escHtml(r.tag)}</span>
      <span style="font-size:10.5px;color:var(--gray-text);white-space:nowrap;">상위 ${r.topPct}% · 하위 ${r.botPct}%</span>
    </div>`;
  // ic-body 안, 중단패턴 col 다음:
  ${pat.shared && pat.shared.length ? `<div style="flex:1;min-width:220px;">
      <div style="font-size:12px;font-weight:700;color:var(--mid);margin-bottom:6px;">⚖️ 공통 패턴 <span style="font-weight:500;font-size:10.5px;color:var(--gray-text);">(고·저 공유 · 변별력 낮음)</span></div>
      ${pat.shared.map(sharedRow).join('')}
    </div>` : ''}
```

## ⑪ 최저 성과 소재 카드

`최고 소재`(topMat, 2332) 블록 다음에 `bottomMat` 카드 추가:
```js
  // 6b. 최저 소재 (최고와 대비)
  const bottomMat = allMats.length >= 2 ? allMats[allMats.length - 1] : null;  // allMats 는 위에서 점수 내림차순 정렬됨
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
- `allMats` 는 2332에서 `.sort((a,b)=>b.score-a.score)` 로 내림차순 정렬되므로 마지막이 최저. (정렬 변형 확인 — topMat 산출이 allMats 자체를 정렬.)
- `type:'alert'`(⚠️, 기존 스타일 재사용). 최고(win/⭐)와 시각 대비.

## 검증 (preview)

step2_clustering.html?_=<ts> → 데이터 로드·군집화 실행 후:
1. **⑩**: `buildPatternInsights(window.clusterResults.baseClusters or clusters)` 반환에 `shared` 배열 존재. 펩류 공통 태그가 winners 아닌 shared 에 분류(winners 의 tag 와 shared 의 tag 교집합 없음). HTML 에 "공통 패턴" 컬럼 노출.
2. **⑪**: 인사이트 그리드에 "최저 성과 소재" 카드 존재(`insightGrid.textContent` 포함). 최고와 별개.
3. 콘솔 error 0.

## 비목표
- 군집화 알고리즘(Union-Find·±1σ 분리)·점수 산식 변경 없음.
- 임계값(공통 50%·약변별 12%p)은 휴리스틱 — 추후 조정 가능.
- 데이터·파이프라인 무변경.
