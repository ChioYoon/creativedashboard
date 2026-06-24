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
  const MINI_BTN = 'cursor:pointer;font-size:11px;font-weight:600;padding:2px 8px;border:1px solid #e5e7eb;border-radius:6px;background:#fff;margin-left:4px;';
  const DATE_INP = 'font-size:12px;padding:3px 6px;border:1px solid #e5e7eb;border-radius:6px;';
  LIVE.buildFilters = function () {
    const ds = LIVE.allDailies();
    const countries = [...new Set(ds.map(d => d.country))].sort();
    const oses = [...new Set(ds.map(d => d.os))].sort();
    const camps = [...new Set(ds.map(d => d.campaign_name).filter(Boolean))].sort();
    const dates = ds.map(d => d.date).filter(Boolean).sort();
    LIVE.state._maxDate = dates[dates.length - 1] || '';
    LIVE.state._minDate = dates[0] || '';
    LIVE.state.filters = { start:'', end:'', countries:new Set(), oses:new Set(), campaigns:new Set() };
    const host = el('liveFilterDynamic');
    if (!ds.length) { host.innerHTML = '<span style="font-size:12px;color:#9ca3af;">운영 데이터 없음 — 필터 비활성 (아래 소재 목록은 전체 표시)</span>'; return; }
    const presetBtns = [['전체',0],['최근 7일',7],['14일',14],['28일',28]]
      .map(([lbl,n]) => `<button class="live-metric-btn" data-days="${n}">${lbl}</button>`).join('');
    const checks = (name, arr) => arr.map(v =>
      `<label style="font-size:12px;display:inline-flex;gap:4px;align-items:center;margin-right:8px;"><input type="checkbox" data-filter="${name}" value="${v}">${v}</label>`).join('');
    host.innerHTML =
      `<div class="live-filter-group"><label>기간</label><div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;">${presetBtns}` +
        `<span style="margin-left:6px;"><input type="date" id="liveDateStart" style="${DATE_INP}"> ~ <input type="date" id="liveDateEnd" style="${DATE_INP}"></span></div></div>` +
      `<div class="live-filter-group"><label>국가</label><div>${checks('countries', countries)}</div></div>` +
      `<div class="live-filter-group"><label>OS</label><div>${checks('oses', oses)}</div></div>` +
      `<div class="live-filter-group" style="max-width:360px;"><label>캠페인` +
        `<input type="text" id="liveCampSearch" placeholder="검색…" style="font-size:11px;padding:2px 6px;border:1px solid #e5e7eb;border-radius:6px;margin-left:6px;width:90px;">` +
        `<button type="button" data-camp-all="1" style="${MINI_BTN}">전체선택</button><button type="button" data-camp-all="0" style="${MINI_BTN}">해제</button></label>` +
        `<div id="liveCampList" style="max-height:80px;overflow:auto;">${checks('campaigns', camps)}</div></div>`;

    // 체크박스
    host.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.addEventListener('change', () => {
      const set = LIVE.state.filters[cb.dataset.filter];
      cb.checked ? set.add(cb.value) : set.delete(cb.value);
      LIVE.render();
    }));
    // 기간 프리셋
    const clearPreset = () => host.querySelectorAll('button[data-days]').forEach(x => x.classList.remove('active'));
    host.querySelectorAll('button[data-days]').forEach(b => b.addEventListener('click', () => {
      clearPreset(); b.classList.add('active');
      const n = +b.dataset.days;
      if (!n || !LIVE.state._maxDate) { LIVE.state.filters.start=''; LIVE.state.filters.end=''; }
      else { const end = LIVE.state._maxDate; const d = new Date(end); d.setDate(d.getDate()-(n-1));
        LIVE.state.filters.start = d.toISOString().slice(0,10); LIVE.state.filters.end = end; }
      el('liveDateStart').value = LIVE.state.filters.start;
      el('liveDateEnd').value = LIVE.state.filters.end;
      LIVE.render();
    }));
    // 기간 직접 입력
    el('liveDateStart').addEventListener('change', e => { clearPreset(); LIVE.state.filters.start = e.target.value; LIVE.render(); });
    el('liveDateEnd').addEventListener('change', e => { clearPreset(); LIVE.state.filters.end = e.target.value; LIVE.render(); });
    // 캠페인 검색
    el('liveCampSearch').addEventListener('input', e => {
      const q = e.target.value.toLowerCase();
      el('liveCampList').querySelectorAll('label').forEach(lbl => { lbl.style.display = lbl.textContent.toLowerCase().includes(q) ? '' : 'none'; });
    });
    // 캠페인 전체선택/해제 (검색으로 보이는 항목만)
    host.querySelectorAll('button[data-camp-all]').forEach(b => b.addEventListener('click', () => {
      const select = b.dataset.campAll === '1';
      el('liveCampList').querySelectorAll('label').forEach(lbl => {
        if (lbl.style.display === 'none') return;
        const cb = lbl.querySelector('input'); cb.checked = select;
        select ? LIVE.state.filters.campaigns.add(cb.value) : LIVE.state.filters.campaigns.delete(cb.value);
      });
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
    const stacked = LIVE.metric !== 'cpi';   // 노출·획득은 누적, CPI(비율)는 중첩만
    const datasets = top.map(([c, e], i) => {
      const col = CHART_COLORS[i % CHART_COLORS.length];
      return {
        label: c.소재명 || c.creative_id || ('소재'+i),
        data: agg.dates.map(dt => {
          const v = LIVE.metricVal(e.byDate.get(dt), LIVE.metric);
          return (stacked && v == null) ? 0 : v;   // 누적은 결측=0
        }),
        borderColor: col, backgroundColor: col + '55',
        fill: true, tension: 0.25, pointRadius: 1, spanGaps: !stacked,
      };
    });
    if (LIVE.chart) LIVE.chart.destroy();
    LIVE.chart = new Chart(el('liveChart').getContext('2d'), {
      type: 'line',
      data: { labels: agg.dates, datasets },
      options: { responsive:true, maintainAspectRatio:false,
        plugins:{ legend:{ position:'bottom', labels:{ boxWidth:12, font:{ size:11 } } },
          tooltip:{ mode:'index', intersect:false } },
        scales:{ y:{ beginAtZero:true, stacked }, x:{ stacked } } },
    });
  };

  function wireToolbar() {
    document.querySelectorAll('.live-metric-btn[data-metric]').forEach(b => b.addEventListener('click', () => {
      document.querySelectorAll('.live-metric-btn[data-metric]').forEach(x => x.classList.remove('active'));
      b.classList.add('active'); LIVE.metric = b.dataset.metric; LIVE.renderChart();
    }));
    el('liveTopN').addEventListener('change', e => { LIVE.topN = +e.target.value; LIVE.renderChart(); });
  }

  // ── 분석 모달 순수 헬퍼 (step1 미변경 — 복제) ───────────────
  function escapeHtml(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m])); }

  function buildInsightBlocksHtml(creative) {
    const meta = (creative && creative.meta) || {};
    const insight = ((meta.one_line_insight || meta.marketer_insight) || '').trim();
    const reality = (meta.kpi_reality_check || '').trim();
    if (!insight && !reality) return '';
    const lead = insight ? `<div style="font-weight:600;margin:4px 0;">${escapeHtml(insight)}</div>` : '';
    const body = reality ? `<div style="color:#555;font-size:13px;">${escapeHtml(reality)}</div>` : '';
    return `<div style="border-left:3px solid var(--brand-primary,#DC2828);padding:8px 12px;background:#FAF9F7;border-radius:6px;margin:10px 0;"><span style="font-size:11px;font-weight:700;color:var(--brand-primary,#DC2828);">인사이트</span>${lead}${body}</div>`;
  }

  function buildSignalChipsHtml(creative) {
    const meta = (creative && creative.meta) || {};
    const groups = [
      { label:'강점', items:meta.strengths,  ev:meta.strength_evidence, color:'#16a34a' },
      { label:'약점', items:meta.weaknesses, ev:meta.weakness_evidence, color:'#d97706' },
      { label:'가설', items:meta.hypothesis, ev:null,                   color:'#2563eb' },
      { label:'차주 변주', items:meta.test_ideas, ev:meta.improvement_actions, color:'#6b7280', pfx:'→ ' },
    ];
    return groups.filter(g => Array.isArray(g.items) && g.items.length).map(g => {
      const cards = g.items.map((it, i) => {
        const e = ((g.ev && g.ev[i]) || '').trim();
        const eh = e ? `<div style="font-size:12px;color:#555;margin-top:2px;">${escapeHtml((g.pfx||'')+e)}</div>` : '';
        return `<div style="border-left:3px solid ${g.color};padding:6px 10px;margin:4px 0;background:#fff;"><div style="font-size:12.5px;font-weight:600;">${escapeHtml(it)}</div>${eh}</div>`;
      }).join('');
      return `<div style="margin:8px 0;"><div style="font-size:11px;font-weight:700;color:#6b7280;margin-bottom:2px;">${g.label}</div>${cards}</div>`;
    }).join('');
  }

  // ── YouTube 헬퍼 (step1과 동일 — 복제) ──────────────────────
  function extractYouTubeId(url) {
    if (!url) return null;
    const patterns = [
      /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)/,
      /^([a-zA-Z0-9_-]{11})$/,
    ];
    for (const p of patterns) { const m = url.match(p); if (m && m[1]) return m[1]; }
    return null;
  }
  function buildYouTubeEmbedHtml(videoId) {
    if (!videoId) return '<p style="color:#ef4444;font-weight:600;">⚠️ 유효하지 않은 YouTube URL입니다.</p>';
    const watchUrl = `https://www.youtube.com/watch?v=${videoId}`;
    const origin = encodeURIComponent(location.origin || 'https://chioyoon.github.io');
    const embedUrl = `https://www.youtube-nocookie.com/embed/${videoId}?autoplay=1&rel=0&modestbranding=1&playsinline=1&fs=1&origin=${origin}`;
    return `<div style="position:relative;width:100%;max-width:640px;margin:0 auto;">
      <iframe width="640" height="360" src="${embedUrl}" title="YouTube 영상 미리보기" frameborder="0"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; fullscreen; web-share"
        referrerpolicy="strict-origin-when-cross-origin" style="border-radius:12px;display:block;width:100%;height:auto;aspect-ratio:16/9;"></iframe>
      <div style="margin-top:8px;text-align:right;"><a href="${watchUrl}" target="_blank" rel="noopener" style="font-size:12px;color:#FF0000;font-weight:700;text-decoration:none;">▶ YouTube에서 열기</a></div>
    </div>`;
  }

  // ── 미리보기 셀 ─────────────────────────────────────────────
  // 우선순위: 이미지 링크 → 유튜브 영상(썸네일+재생) → (둘 다 없을 때만) Drive
  function livePreviewHtml(c) {
    const url = c['링크'] || c.이미지링크 || '';
    const isVideo = (c.유형 || '').toUpperCase() === 'VID';
    const hasUrl = url && url.startsWith('http');
    if (hasUrl && !isVideo) return `<img src="${url}" alt="" style="width:100%;height:100%;object-fit:cover;">`;
    if (hasUrl && isVideo) {
      const yid = extractYouTubeId(url);
      if (yid) {
        return `<div style="position:relative;width:100%;height:100%;"><img src="https://img.youtube.com/vi/${yid}/hqdefault.jpg" alt="" style="width:100%;height:100%;object-fit:cover;"><div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;"><div style="width:38px;height:38px;background:rgba(0,0,0,.6);border-radius:50%;display:flex;align-items:center;justify-content:center;"><span style="color:#fff;font-size:16px;margin-left:3px;">▶</span></div></div></div>`;
      }
      return `<span style="color:#9ca3af;font-size:22px;">▶</span>`;   // 영상 링크 있으나 임베드 불가 — 클릭 시 모달서 열기
    }
    // 유튜브·이미지 링크 모두 없을 때만 Drive
    if (LIVE.state.driveFolderUrl) {
      const safe = LIVE.state.driveFolderUrl.replace(/'/g, "\\'");
      return `<button type="button" onclick="event.stopPropagation();window.open('${safe}','_blank','noopener')" title="공유 드라이브 폴더에서 소재 찾기" style="cursor:pointer;font-size:11px;font-weight:600;color:#666;background:#F4F2EF;border:1px solid #e5e0d8;border-radius:6px;padding:6px 8px;">📁 Drive</button>`;
    }
    return `<span style="color:#9ca3af;font-size:22px;">${isVideo ? '▶' : '📷'}</span>`;
  }

  // ── 소재 그리드 (전체 소재, 노출 무관) ─────────────────────
  LIVE.renderGrid = function () {
    const agg = LIVE.aggregate(LIVE.applyFilters());   // 필터 기간 획득 배지
    const acqOf = c => (agg.perCreative.get(c) || { acq:0 }).acq;
    const list = [...LIVE.state.creatives].sort((a, b) => acqOf(b) - acqOf(a));
    const grid = el('liveGrid');
    if (!list.length) { grid.innerHTML = '<div class="live-empty">이 타이틀에 소재가 없습니다.</div>'; return; }
    grid.innerHTML = list.map((c, i) => {
      const acq = acqOf(c);
      const badge = LIVE.state.hasKpi ? `<div class="live-card-badge">획득 ${acq.toLocaleString()}</div>` : '';
      return `<div class="live-card" data-idx="${i}"><div class="live-card-preview">${livePreviewHtml(c)}</div><div class="live-card-body"><div class="live-card-name">${escapeHtml(c.소재명 || c.creative_id || '')}</div>${badge}</div></div>`;
    }).join('');
    LIVE._gridList = list;
    grid.querySelectorAll('.live-card').forEach(card => card.addEventListener('click', () => {
      LIVE.openModal(LIVE._gridList[+card.dataset.idx]);
    }));
  };

  // ── 분석 모달 ───────────────────────────────────────────────
  LIVE.openModal = function (c) {
    if (!c) return;
    const url = c['링크'] || c.이미지링크 || '';
    const hasUrl = url && url.startsWith('http');
    const isVideo = (c.유형 || '').toUpperCase() === 'VID';
    let preview;
    if (hasUrl && !isVideo) preview = `<img src="${url}" style="max-width:100%;border-radius:10px;" alt="">`;
    else if (hasUrl && isVideo) {
      const yid = extractYouTubeId(url);
      preview = yid ? buildYouTubeEmbedHtml(yid)
        : `<div style="text-align:center;"><a href="${url}" target="_blank" rel="noopener" style="display:inline-block;padding:12px 20px;background:#111;color:#fff;border-radius:8px;font-weight:700;text-decoration:none;">▶ 영상 열기</a></div>`;
    }
    else {
      // 유튜브·이미지 링크 모두 없을 때만 Drive
      const drive = LIVE.state.driveFolderUrl
        ? `<div style="margin-top:16px;"><button type="button" onclick="window.open('${LIVE.state.driveFolderUrl.replace(/'/g,"\\'")}','_blank','noopener')" style="cursor:pointer;padding:10px 18px;background:#E84855;color:#fff;border:none;border-radius:8px;font-size:13px;font-weight:700;">📁 Google Drive 폴더에서 소재 찾기</button></div>` : '';
      preview = `<div style="padding:28px;background:#f9fafb;border:1.5px dashed #d1d5db;border-radius:12px;text-align:center;color:#6b7280;"><div style="font-size:40px;">📂</div><div style="font-size:13px;font-weight:600;color:#374151;margin-top:8px;">미리보기 링크 없음</div><div style="font-size:11px;font-family:monospace;color:#9ca3af;margin-top:6px;">${escapeHtml(c.파일명 || '-')}</div>${drive}</div>`;
    }
    const w = { meta: c };   // 복제 헬퍼는 creative.meta.* 를 읽음
    const intent = (c.creator_intent || '').trim();
    const intentHtml = intent ? `<div style="font-style:italic;color:#666;margin:8px 0;">${escapeHtml(intent)}</div>` : '';
    el('liveModalBody').innerHTML =
      preview +
      `<h3 style="margin:16px 0 6px;font-size:16px;">${escapeHtml(c.소재명 || '')} <span style="font-size:12px;color:#9ca3af;">(${escapeHtml(c.유형 || '')})</span></h3>` +
      intentHtml + buildInsightBlocksHtml(w) + buildSignalChipsHtml(w);
    el('liveModal').classList.add('active');
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
    wireToolbar();
    el('liveModalClose').addEventListener('click', () => el('liveModal').classList.remove('active'));
    el('liveModal').addEventListener('click', e => { if (e.target.id === 'liveModal') el('liveModal').classList.remove('active'); });
    // 필터 접기/펼치기
    el('liveFilterToggle').addEventListener('click', () => {
      const body = el('liveFilterDynamic');
      const hidden = body.style.display === 'none';
      body.style.display = hidden ? 'flex' : 'none';
      el('liveFilterToggle').textContent = hidden ? '필터 접기 ▲' : '필터 펼치기 ▼';
    });
    // 추이 그래프 접기/펼치기
    el('liveChartToggle').addEventListener('click', () => {
      const area = el('liveChartArea'), ctrls = el('liveChartControls');
      const hidden = area.style.display === 'none';
      area.style.display = hidden ? '' : 'none';
      ctrls.style.display = hidden ? 'inline-flex' : 'none';
      el('liveChartToggle').textContent = hidden ? '접기 ▲' : '펼치기 ▼';
    });
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
