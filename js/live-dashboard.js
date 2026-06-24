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

  // ── campaign_name 파서 ──────────────────────────────────────
  // 예: HQ_HQ_PH_US-EN_GA_NU_AD_ACA-PU_260429 / HQ_HQ_PH_CA-EN_FB_NU_iOS_INSTALL_260122
  LIVE.parseCountry = function (cn) {
    if (!cn) return '미상';
    const seg = String(cn).split('_').find(s => /^[A-Z]{2,4}-[A-Z]{2}$/.test(s));
    return seg ? seg.split('-')[0] : '미상';
  };
  const OS_TOKENS = { ios: 'iOS', aos: 'Android', android: 'Android', web: 'Web' };
  LIVE.parseOS = function (cn) {
    if (!cn) return '미상';
    for (const s of String(cn).split('_')) {
      const k = s.toLowerCase();
      if (OS_TOKENS[k]) return OS_TOKENS[k];
    }
    return '미상';
  };

  // ── 일별 통합 평탄화 + 필터 ─────────────────────────────────
  // Google Ads=conversions, MMP=installs → acq
  LIVE.allDailies = function () {
    const out = [];
    for (const c of LIVE.state.creatives) {
      for (const k of (c.kpi_daily || [])) {
        out.push({ creative: c, date: k.date, campaign_name: k.campaign_name,
          country: LIVE.parseCountry(k.campaign_name), os: LIVE.parseOS(k.campaign_name),
          src: 'GA', impr: +k.impressions || 0, acq: +k.conversions || 0, cost: +k.cost || 0 });
      }
      for (const m of (c.mmp_daily || [])) {
        out.push({ creative: c, date: m.date, campaign_name: m.campaign_name,
          country: LIVE.parseCountry(m.campaign_name), os: LIVE.parseOS(m.campaign_name),
          src: 'MMP', impr: +m.impressions || 0, acq: +m.installs || 0, cost: +m.cost || 0 });
      }
    }
    return out;
  };

  LIVE.applyFilters = function () {
    const f = LIVE.state.filters || { start:'', end:'', countries:new Set(), oses:new Set(), campaigns:new Set() };
    return LIVE.allDailies().filter(d => {
      if (f.start && d.date < f.start) return false;
      if (f.end && d.date > f.end) return false;
      if (f.countries.size && !f.countries.has(d.country)) return false;
      if (f.oses.size && !f.oses.has(d.os)) return false;
      if (f.campaigns.size && !f.campaigns.has(d.campaign_name)) return false;
      return true;
    });
  };

  // ── 필터 바 UI 주입 ─────────────────────────────────────────
  LIVE.buildFilters = function () {
    const ds = LIVE.allDailies();
    const countries = [...new Set(ds.map(d => d.country))].sort();
    const oses = [...new Set(ds.map(d => d.os))].sort();
    const camps = [...new Set(ds.map(d => d.campaign_name).filter(Boolean))].sort();
    const dates = ds.map(d => d.date).filter(Boolean).sort();
    LIVE.state._maxDate = dates[dates.length - 1] || '';
    LIVE.state.filters = { start:'', end:'', countries:new Set(), oses:new Set(), campaigns:new Set() };
    const host = el('liveFilterDynamic');
    if (!ds.length) { host.innerHTML = '<span style="font-size:12px;color:#9ca3af;">운영 데이터 없음 — 필터 비활성 (아래 소재 목록은 전체 표시)</span>'; return; }
    const presetBtns = [['전체',0],['최근 7일',7],['14일',14],['28일',28]]
      .map(([lbl,n]) => `<button class="live-metric-btn" data-days="${n}">${lbl}</button>`).join('');
    const checks = (name, arr) => arr.map(v =>
      `<label style="font-size:12px;display:inline-flex;gap:4px;align-items:center;margin-right:8px;"><input type="checkbox" data-filter="${name}" value="${v}">${v}</label>`).join('');
    host.innerHTML =
      `<div class="live-filter-group"><label>기간</label><div>${presetBtns}</div></div>` +
      `<div class="live-filter-group"><label>국가</label><div>${checks('countries', countries)}</div></div>` +
      `<div class="live-filter-group"><label>OS</label><div>${checks('oses', oses)}</div></div>` +
      `<div class="live-filter-group" style="max-width:340px;"><label>캠페인</label><div style="max-height:64px;overflow:auto;">${checks('campaigns', camps)}</div></div>`;
    host.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.addEventListener('change', () => {
      const set = LIVE.state.filters[cb.dataset.filter];
      cb.checked ? set.add(cb.value) : set.delete(cb.value);
      LIVE.render();
    }));
    host.querySelectorAll('button[data-days]').forEach(b => b.addEventListener('click', () => {
      host.querySelectorAll('button[data-days]').forEach(x => x.classList.remove('active'));
      b.classList.add('active');
      const n = +b.dataset.days;
      if (!n || !LIVE.state._maxDate) { LIVE.state.filters.start=''; LIVE.state.filters.end=''; }
      else { const end = LIVE.state._maxDate; const d = new Date(end); d.setDate(d.getDate()-(n-1));
        LIVE.state.filters.start = d.toISOString().slice(0,10); LIVE.state.filters.end = end; }
      LIVE.render();
    }));
  };

  // ── 통합 일별 집계 ──────────────────────────────────────────
  LIVE.aggregate = function (dailies) {
    const perCreative = new Map();   // creative → {impr,acq,cost, byDate:Map}
    const dateSet = new Set();
    for (const d of dailies) {
      dateSet.add(d.date);
      let e = perCreative.get(d.creative);
      if (!e) { e = { impr:0, acq:0, cost:0, byDate:new Map() }; perCreative.set(d.creative, e); }
      e.impr += d.impr; e.acq += d.acq; e.cost += d.cost;
      let bd = e.byDate.get(d.date);
      if (!bd) { bd = { impr:0, acq:0, cost:0 }; e.byDate.set(d.date, bd); }
      bd.impr += d.impr; bd.acq += d.acq; bd.cost += d.cost;
    }
    return { perCreative, dates: [...dateSet].sort() };
  };
  // 지표값 (CPI=cost/acq, 획득 0이면 null=gap)
  LIVE.metricVal = function (cell, metric) {
    if (!cell) return null;
    if (metric === 'impr') return cell.impr;
    if (metric === 'acq') return cell.acq;
    return cell.acq > 0 ? cell.cost / cell.acq : null;   // cpi
  };

  // ── Top N 추이 그래프 ───────────────────────────────────────
  const CHART_COLORS = ['#DC2828','#2563eb','#16a34a','#d97706','#7c3aed','#0891b2','#db2777','#65a30d','#ea580c','#4f46e5'];
  LIVE.renderChart = function () {
    const agg = LIVE.aggregate(LIVE.applyFilters());
    const area = el('liveChartArea');
    if (!agg.dates.length) { area.innerHTML = '<div class="live-empty">선택한 필터에 해당하는 추이 데이터가 없습니다.</div>'; LIVE.chart = null; return; }
    if (!area.querySelector('canvas')) area.innerHTML = '<canvas id="liveChart"></canvas>';
    // 획득 상위 Top N
    const top = [...agg.perCreative.entries()].sort((a,b) => b[1].acq - a[1].acq).slice(0, LIVE.topN);
    const datasets = top.map(([c, e], i) => ({
      label: c.소재명 || c.creative_id || ('소재'+i),
      data: agg.dates.map(dt => LIVE.metricVal(e.byDate.get(dt), LIVE.metric)),
      borderColor: CHART_COLORS[i % CHART_COLORS.length], backgroundColor: 'transparent',
      spanGaps: true, tension: 0.25, pointRadius: 2,
    }));
    if (LIVE.chart) LIVE.chart.destroy();
    LIVE.chart = new Chart(el('liveChart').getContext('2d'), {
      type: 'line',
      data: { labels: agg.dates, datasets },
      options: { responsive:true, maintainAspectRatio:false,
        plugins:{ legend:{ position:'bottom', labels:{ boxWidth:12, font:{ size:11 } } } },
        scales:{ y:{ beginAtZero:true } } },
    });
  };

  function wireToolbar() {
    document.querySelectorAll('.live-metric-btn[data-metric]').forEach(b => b.addEventListener('click', () => {
      document.querySelectorAll('.live-metric-btn[data-metric]').forEach(x => x.classList.remove('active'));
      b.classList.add('active'); LIVE.metric = b.dataset.metric; LIVE.renderChart();
    }));
    el('liveTopN').addEventListener('change', e => { LIVE.topN = +e.target.value; LIVE.renderChart(); });
  }

  // Task 4에서 구현 (현재 stub)
  LIVE.renderGrid = LIVE.renderGrid || function () {};

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
    wireToolbar();
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
    LIVE.buildFilters();
    LIVE.render();
  };

  LIVE.render = function () {
    if (!LIVE.state.hasKpi) {
      el('liveChartArea').innerHTML = '<div class="live-empty">이 타이틀은 운영(KPI) 데이터가 없어 추이를 표시할 수 없습니다. 아래 소재 목록과 분석은 확인할 수 있습니다.</div>';
    } else {
      LIVE.renderChart();
    }
    LIVE.renderGrid();
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
