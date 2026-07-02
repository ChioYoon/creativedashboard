/* 라이브 대시보드 — 노출 중 소재 그리드 + 통합 추이 그래프 */
(function () {
  'use strict';
  const LIVE = {
    state: { titleId: '', creatives: [], driveFolderUrl: '', hasKpi: false, manifest: [] },
    canon: {},
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
  // Google Ads=conversions, MMP=installs → acq (서로 다른 이벤트를 '획득'으로 합산).
  // ⚠️ 비중복 가정(QA P2-L): GA·MMP 캠페인이 같은 기간 중복 집행되면 동일 유저가 양쪽
  //    집계될 수 있음. 현 타이틀은 집행 시기 비중복이라 무발현 — 듀얼소스 동시집행 등록 시 재검토.
  LIVE.allDailies = function () {
    const out = [];
    const canon = LIVE.canon || {};
    // country/os: 캐노니컬 값 있으면 사용, 비었거나 항목 없으면 조회 단위로 JS 파서 폴백
    const cf = (cn, field, jsFn) => { const v = canon[cn] && canon[cn][field]; return v ? v : jsFn(cn); };
    // ua_type/media/product: 캐노니컬 전용 (맵 없으면 '미상' — 필터도 미표시)
    const cv = (cn, field) => (canon[cn] && canon[cn][field]) || '미상';
    for (const c of LIVE.state.creatives) {
      for (const k of (c.kpi_daily || [])) {
        out.push({ creative: c, date: k.date, campaign_name: k.campaign_name,
          country: cf(k.campaign_name, 'country', LIVE.parseCountry), os: cf(k.campaign_name, 'os', LIVE.parseOS),
          ua_type: cv(k.campaign_name, 'ua_type'), media: cv(k.campaign_name, 'media'), product: cv(k.campaign_name, 'product'),
          src: 'GA', impr: +k.impressions || 0, acq: +k.conversions || 0, cost: +k.cost || 0 });
      }
      for (const m of (c.mmp_daily || [])) {
        out.push({ creative: c, date: m.date, campaign_name: m.campaign_name,
          country: cf(m.campaign_name, 'country', LIVE.parseCountry), os: cf(m.campaign_name, 'os', LIVE.parseOS),
          ua_type: cv(m.campaign_name, 'ua_type'), media: cv(m.campaign_name, 'media'), product: cv(m.campaign_name, 'product'),
          src: 'MMP', impr: +m.impressions || 0, acq: +m.installs || 0, cost: +m.cost || 0 });
      }
    }
    return out;
  };

  LIVE.applyFilters = function () {
    const f = LIVE.state.filters || { start:'', end:'', countries:new Set(), oses:new Set(), campaigns:new Set(), ua_types:new Set(), medias:new Set(), products:new Set() };
    return LIVE.allDailies().filter(d => {
      if (f.start && d.date < f.start) return false;
      if (f.end && d.date > f.end) return false;
      if (f.countries.size && !f.countries.has(d.country)) return false;
      if (f.oses.size && !f.oses.has(d.os)) return false;
      if (f.ua_types && f.ua_types.size && !f.ua_types.has(d.ua_type)) return false;
      if (f.medias && f.medias.size && !f.medias.has(d.media)) return false;
      if (f.products && f.products.size && !f.products.has(d.product)) return false;
      if (f.campaigns.size && !f.campaigns.has(d.campaign_name)) return false;
      return true;
    });
  };

  // ── 필터 바 UI 주입 ─────────────────────────────────────────
  const DATE_INP = 'font-size:12px;padding:3px 6px;border:1px solid #e5e7eb;border-radius:6px;';
  LIVE.buildFilters = function () {
    const ds = LIVE.allDailies();
    const countries = [...new Set(ds.map(d => d.country))].sort();
    const oses = [...new Set(ds.map(d => d.os))].sort();
    const camps = [...new Set(ds.map(d => d.campaign_name).filter(Boolean))].sort();
    const hasCanon = LIVE.canon && Object.keys(LIVE.canon).length > 0;
    const uaTypes  = hasCanon ? [...new Set(ds.map(d => d.ua_type))].sort() : [];
    const medias   = hasCanon ? [...new Set(ds.map(d => d.media))].sort()   : [];
    const products = hasCanon ? [...new Set(ds.map(d => d.product))].sort() : [];
    const dates = ds.map(d => d.date).filter(Boolean).sort();
    LIVE.state._maxDate = dates[dates.length - 1] || '';
    LIVE.state._minDate = dates[0] || '';
    LIVE.state.filters = { start:'', end:'', countries:new Set(), oses:new Set(), campaigns:new Set(), ua_types:new Set(), medias:new Set(), products:new Set() };
    const host = el('liveFilterDynamic');
    if (!ds.length) { host.innerHTML = '<span style="font-size:12px;color:#9ca3af;">운영 데이터 없음 — 필터 비활성 (아래 소재 목록은 전체 표시)</span>'; return; }
    const presetBtns = [['전체',0],['최근 7일',7],['14일',14],['28일',28]]
      .map(([lbl,n]) => `<button class="live-metric-btn" data-days="${n}">${lbl}</button>`).join('');

    // ── 드롭다운 멀티셀렉트 그룹 (검색 + 전체선택/해제 + 스크롤) ──
    const ddGroup = (name, label, arr) => `
      <div class="live-filter-group live-dd" data-dd-name="${name}">
        <label>${label}</label>
        <button type="button" class="live-dd-btn" data-dd-trigger="${name}">전체 ▾</button>
        <div class="live-dd-panel" data-dd-panel="${name}">
          <input type="text" class="live-dd-search" data-dd-search="${name}" placeholder="검색…">
          <div class="live-dd-actions">
            <button type="button" data-dd-all="${name}" data-dd-select="1">전체선택</button>
            <button type="button" data-dd-all="${name}" data-dd-select="0">해제</button>
          </div>
          <div class="live-dd-list" data-dd-list="${name}">
            ${arr.length ? arr.map(v => `<label><input type="checkbox" data-filter="${name}" value="${escapeHtml(v)}">${escapeHtml(v)}</label>`).join('')
              : '<span style="font-size:12px;color:#9ca3af;">항목 없음</span>'}
          </div>
        </div>
      </div>`;

    host.innerHTML =
      `<div class="live-filter-group"><label>기간</label><div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;">${presetBtns}` +
        `<span style="margin-left:6px;"><input type="date" id="liveDateStart" style="${DATE_INP}"> ~ <input type="date" id="liveDateEnd" style="${DATE_INP}"></span></div></div>` +
      ddGroup('countries', '국가', countries) +
      ddGroup('oses', 'OS', oses) +
      (hasCanon ? ddGroup('ua_types', '유형', uaTypes) + ddGroup('medias', '매체', medias) + ddGroup('products', '상품', products) : '') +
      ddGroup('campaigns', '캠페인', camps);

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

    // ── 드롭다운 와이어링 ──
    const updateTriggerLabel = (name) => {
      const btn = host.querySelector(`[data-dd-trigger="${name}"]`);
      if (!btn) return;
      const n = LIVE.state.filters[name].size;
      btn.textContent = (n ? `${n}개 선택` : '전체') + ' ▾';
      btn.classList.toggle('active-filter', n > 0);
    };
    const closeAllPanels = () => host.querySelectorAll('.live-dd-panel.open').forEach(p => p.classList.remove('open'));
    host.querySelectorAll('[data-dd-trigger]').forEach(btn => btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const name = btn.dataset.ddTrigger;
      const panel = host.querySelector(`[data-dd-panel="${name}"]`);
      const willOpen = !panel.classList.contains('open');
      closeAllPanels();
      if (willOpen) panel.classList.add('open');
    }));
    host.querySelectorAll('input[type="checkbox"][data-filter]').forEach(cb => cb.addEventListener('change', () => {
      const name = cb.dataset.filter;
      const set = LIVE.state.filters[name];
      cb.checked ? set.add(cb.value) : set.delete(cb.value);
      updateTriggerLabel(name);
      LIVE.render();
    }));
    host.querySelectorAll('[data-dd-search]').forEach(inp => inp.addEventListener('input', (e) => {
      const name = inp.dataset.ddSearch;
      const q = e.target.value.toLowerCase();
      host.querySelector(`[data-dd-list="${name}"]`).querySelectorAll('label').forEach(lbl => {
        lbl.style.display = lbl.textContent.toLowerCase().includes(q) ? '' : 'none';
      });
    }));
    host.querySelectorAll('[data-dd-all]').forEach(b => b.addEventListener('click', () => {
      const name = b.dataset.ddAll;
      const select = b.dataset.ddSelect === '1';
      host.querySelector(`[data-dd-list="${name}"]`).querySelectorAll('label').forEach(lbl => {
        if (lbl.style.display === 'none') return;
        const cb = lbl.querySelector('input'); if (!cb) return;
        cb.checked = select;
        select ? LIVE.state.filters[name].add(cb.value) : LIVE.state.filters[name].delete(cb.value);
      });
      updateTriggerLabel(name);
      LIVE.render();
    }));
    if (!LIVE._ddOutsideWired) {
      document.addEventListener('click', (e) => {
        if (e.target.closest('.live-dd')) return;
        document.querySelectorAll('.live-dd-panel.open').forEach(p => p.classList.remove('open'));
      });
      LIVE._ddOutsideWired = true;
    }
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
  LIVE.renderChart = function (agg) {
    agg = agg || LIVE._agg || LIVE.aggregate(LIVE.applyFilters());
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
        fill: stacked, tension: 0.25, pointRadius: 1, spanGaps: !stacked,
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
      b.classList.add('active'); LIVE.metric = b.dataset.metric; LIVE.renderChart(LIVE._agg);
    }));
    el('liveTopN').addEventListener('change', e => { LIVE.topN = +e.target.value; LIVE.renderChart(LIVE._agg); });
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
  LIVE.renderGrid = function (agg) {
    agg = agg || LIVE._agg || LIVE.aggregate(LIVE.applyFilters());   // 필터 기간 획득 배지
    const cellOf = c => agg.perCreative.get(c) || { acq:0, impr:0 };
    const acqOf = c => cellOf(c).acq;
    const list = [...LIVE.state.creatives].sort((a, b) => acqOf(b) - acqOf(a));
    const grid = el('liveGrid');
    if (!list.length) { grid.innerHTML = '<div class="live-empty">이 타이틀에 소재가 없습니다.</div>'; return; }
    grid.innerHTML = list.map((c, i) => {
      const cell = cellOf(c);
      const idle = LIVE.state.hasKpi && cell.impr === 0 && cell.acq === 0;   // 선택 기간 미집행
      const badge = !LIVE.state.hasKpi ? ''
        : idle ? `<div class="live-card-badge" style="background:#6b7280;">미집행</div>`
        : `<div class="live-card-badge">획득 ${cell.acq.toLocaleString()}</div>`;
      const dim = idle ? 'style="opacity:.5;"' : '';
      return `<div class="live-card" ${dim} data-idx="${i}"><div class="live-card-preview">${livePreviewHtml(c)}</div><div class="live-card-body"><div class="live-card-name">${escapeHtml(c.소재명 || c.creative_id || '')}</div>${badge}</div></div>`;
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
        ? `<div style="margin-top:16px;"><button type="button" onclick="window.open('${LIVE.state.driveFolderUrl.replace(/'/g,"\\'")}','_blank','noopener')" style="cursor:pointer;padding:10px 18px;background:#DC2828;color:#fff;border:none;border-radius:8px;font-size:13px;font-weight:700;">📁 Google Drive 폴더에서 소재 찾기</button></div>` : '';
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
    LIVE.canon = (data.campaign_canonical && typeof data.campaign_canonical === 'object') ? data.campaign_canonical : {};
    LIVE.state.titleId = titleId;
    LIVE.state.creatives = creatives;
    LIVE.state.driveFolderUrl = meta.drive_folder_url || '';
    // KPI 미연동 감지 — step1과 동일 기준
    LIVE.state.hasKpi = creatives.some(c =>
      (c.kpi_daily && c.kpi_daily.length) || (c.mmp_daily && c.mmp_daily.length));
    LIVE.buildFilters();
    LIVE.render();
  };

  LIVE.renderDataBasis = function (agg) {
    const box = document.getElementById('liveDataBasis'); if (!box) return;
    if (!LIVE.state.hasKpi) { box.style.display = 'none'; return; }
    box.style.display = '';
    const f = LIVE.state.filters || {};
    let period;
    if (f.start && f.end) period = `${f.start} ~ ${f.end}`;
    else {
      const dates = agg.dates;
      period = dates.length ? `${dates[0]} ~ ${dates[dates.length - 1]} (전체)` : '전체';
    }
    box.innerHTML = `📊 <strong>데이터 기준</strong> — 획득 = <strong>Google Ads 전환 + MMP 설치</strong> 합산 · 노출/CPI는 각 매체 원값 · 기간 <strong>${period}</strong> `
      + `<span title="Google Ads와 MMP를 같은 기간 동시 집행하면 동일 유저가 양쪽에 잡혀 중복 집계될 수 있습니다. 현재 타이틀은 집행 시기가 겹치지 않아 무관합니다." style="cursor:help;border-bottom:1px dotted #1e40af;">ⓘ 합산 주의</span>`;
  };

  LIVE.render = function () {
    const agg = LIVE.aggregate(LIVE.applyFilters());
    LIVE._agg = agg;
    LIVE.renderDataBasis(agg);
    if (!LIVE.state.hasKpi) {
      el('liveChartArea').innerHTML = '<div class="live-empty">이 타이틀은 운영(KPI) 데이터가 없어 추이를 표시할 수 없습니다. 아래 소재 목록과 분석은 확인할 수 있습니다.</div>';
    } else {
      LIVE.renderChart(agg);
    }
    LIVE.renderGrid(agg);
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
