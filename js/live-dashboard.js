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
    LIVE.buildFilters();
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
