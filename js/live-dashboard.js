/* 라이브 대시보드 — 노출 중 소재 그리드 + 통합 추이 그래프 */
(function () {
  'use strict';
  const LIVE = {
    state: { titleId: '', creatives: [], driveFolderUrl: '', hasKpi: false, manifest: [] },
    metric: 'impr',
    topN: 7,
    chart: null,
  };
  window.LIVE = LIVE;

  function el(id) { return document.getElementById(id); }

  async function init() {
    // 타이틀 매니페스트 → 셀렉터
    LIVE.state.manifest = await window.DataSource.loadTitleManifest();
    const sel = el('liveTitleSelect');
    LIVE.state.manifest
      .filter(t => t.json_url)            // 데이터 있는 타이틀만
      .forEach(t => {
        const o = document.createElement('option');
        o.value = t.id; o.textContent = t.name; sel.appendChild(o);
      });
    sel.addEventListener('change', () => LIVE.loadTitle(sel.value));
    // URL ?title= 또는 첫 항목 자동 로드
    const urlTitle = window.DataSource.readTitleFromUrl();
    const start = (urlTitle && LIVE.state.manifest.some(t => t.id === urlTitle)) ? urlTitle
                : (sel.options[0] && sel.options[0].value) || '';
    if (start) { sel.value = start; await LIVE.loadTitle(start); }
  }

  LIVE.loadTitle = async function (titleId) {
    if (!titleId) return;
    const meta = LIVE.state.manifest.find(t => t.id === titleId) || {};
    const res = await fetch(`public/data/${titleId}.json`, { cache: 'no-store' });
    const data = res.ok ? await res.json() : { creatives: [] };
    const creatives = data.creatives || [];
    LIVE.state.titleId = titleId;
    LIVE.state.creatives = creatives;
    LIVE.state.driveFolderUrl = meta.drive_folder_url || '';
    // KPI 미연동 감지 — step1과 동일 기준
    LIVE.state.hasKpi = creatives.some(c =>
      (c.kpi_daily && c.kpi_daily.length) || (c.mmp_daily && c.mmp_daily.length));
    LIVE.render();
  };

  LIVE.render = function () {
    // Task 2~4에서 확장. 현재: KPI 미연동 시 그래프 영역 안내.
    const chartArea = el('liveChartArea');
    if (!LIVE.state.hasKpi) {
      chartArea.innerHTML = '<div class="live-empty">이 타이틀은 운영(KPI) 데이터가 없어 추이를 표시할 수 없습니다. 아래 소재 목록과 분석은 확인할 수 있습니다.</div>';
    } else {
      chartArea.innerHTML = '<canvas id="liveChart"></canvas>';
    }
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
