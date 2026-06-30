# Batch C — 모달 일별 추이 차트 설계 (③)

**작성일:** 2026-06-29
**대상:** `step1_integrated.html` — 소재 상세 모달(`#modalBody`, 렌더 ~6838) + 신규 `renderModalTrend`

## 목표

소재 상세 모달에 **일별 추이 차트**(Chart.js 라인 + 전환/노출/CPA 토글)를 추가한다. 데이터는 소재의 `kpi_daily`(Google Ads 일별). 기존 표의 전환-only 스파크라인은 빠른 글랜스용으로 유지하고, 모달 차트가 선택형 상세 추이를 보강한다.

## 현황

- 모달 렌더 함수(`creative = window.currentCreatives[index]`, ~6724)가 `content` 문자열 조립 후 `modalBody.innerHTML = content;`(6838) → `modal.classList.add('active')`(6839).
- `kpi_daily` 엔트리 = `{ date, conversions, impressions, cost, clicks?, revenue?, campaign_name }`(영문 키).
- Chart.js 4.4.0 로드됨(line 21).
- 표 '추이' 컬럼: 전환 스파크라인, `dailyData.length>=2`일 때만 표시(2일 미만이면 공백 — 사용자가 본 "안 보임").

## 설계

### (a) 모달에 추이 섹션 추가

`content` 조립의 `signalsBlock` 근처에 `trendBlock` 삽입(인라인 스타일, 추출본 아님이라 클래스 가능):
```js
      const _hasDaily = creative.meta && Array.isArray(creative.meta.kpi_daily) && creative.meta.kpi_daily.length >= 1;
      const trendBlock = `
        <div class="modal-block-title" style="margin-top:16px;">일별 추이 (Google Ads)</div>
        ${_hasDaily ? `
        <div style="display:flex;gap:6px;margin-bottom:8px;">
          <button type="button" class="trend-metric-btn active" data-metric="전환">전환</button>
          <button type="button" class="trend-metric-btn" data-metric="노출">노출</button>
          <button type="button" class="trend-metric-btn" data-metric="CPA">CPA</button>
        </div>
        <div style="position:relative;height:200px;"><canvas id="modalTrendChart"></canvas></div>`
        : `<div style="padding:14px;background:#f9fafb;border-radius:8px;color:#6b7280;font-size:13px;">일별 데이터가 없습니다(미집행 또는 단일일). 캠페인 집행·누적 후 추이가 표시됩니다.</div>`}`;
```
`trendBlock`을 `content`의 적절한 위치(예: `signalsBlock` 다음)에 포함.

`.trend-metric-btn` 최소 스타일(인라인 `<style>` 블록 또는 기존 버튼 클래스 재사용). active 강조.

### (b) 차트 렌더 — 신규 `renderModalTrend(creative)`

`modalBody.innerHTML = content;`(6838) **직후**, `modal.classList.add('active')` 앞에 호출:
```js
      modalBody.innerHTML = content;
      renderModalTrend(creative);
      modal.classList.add('active');
```

```js
    function renderModalTrend(creative) {
      const cv = document.getElementById('modalTrendChart');
      if (!cv) return;  // 데이터 없으면 canvas 미존재
      const daily = (creative.meta.kpi_daily || []).slice().sort((a,b) => String(a.date).localeCompare(String(b.date)));
      const labels = daily.map(d => String(d.date).slice(5));  // MM-DD
      const series = {
        '전환': daily.map(d => Number(d.conversions || 0)),
        '노출': daily.map(d => Number(d.impressions || 0)),
        'CPA':  daily.map(d => (Number(d.conversions) > 0 ? Math.round(Number(d.cost || 0) / d.conversions) : null)),
      };
      if (window._modalTrendChart) { try { window._modalTrendChart.destroy(); } catch(_){} }
      const draw = (metric) => {
        if (window._modalTrendChart) { try { window._modalTrendChart.destroy(); } catch(_){} }
        window._modalTrendChart = new Chart(cv.getContext('2d'), {
          type: 'line',
          data: { labels, datasets: [{ label: metric, data: series[metric], borderColor: '#E84855', backgroundColor: 'rgba(232,72,85,.08)', tension: .25, spanGaps: true, pointRadius: 2 }] },
          options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
        });
      };
      draw('전환');
      document.querySelectorAll('.trend-metric-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          document.querySelectorAll('.trend-metric-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          draw(btn.dataset.metric);
        });
      });
    }
```

- `window._modalTrendChart` 로 이전 인스턴스 destroy(모달 재오픈 시 canvas 재사용 오류 방지).
- CPA는 전환 0인 날 `null`(spanGaps로 선 연결).

### (c) 기존 표 스파크라인

유지(변경 없음). 모달 차트가 상세·선택형 보강.

## 검증 (preview)

`?_=<ts>` → gd 로드·분석 → 첫 소재 모달(`showModal`/상세 모달 트리거):
1. `#modalTrendChart` 존재 + `window._modalTrendChart` Chart 인스턴스 생성(기본 전환).
2. 토글 '노출'·'CPA' 클릭 → 데이터셋 라벨/값 교체(`_modalTrendChart.data.datasets[0].label` 변경).
3. kpi_daily 없는 소재(zeus형) → 차트 대신 "일별 데이터 없음" 안내, canvas 미존재.
4. 모달 닫고 다른 소재 재오픈 → 차트 정상 재생성(destroy 동작), 콘솔 error 0.

## 비목표
- MMP 일별(mmp_daily) 추이 — 추후(이번은 Google Ads 노출/전환/CPA).
- 표 스파크라인 로직 변경 없음.
- 데이터·파이프라인 무변경.
