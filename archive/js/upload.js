/**
 * Pepp Heroes – Upload & Data Management Module
 * CSV 업로드, 수동 추가, 내보내기, 초기화
 */

/* ── CSV 파싱 (간단 구현 – 큰따옴표 처리 포함) */
function parseCSV(text) {
  const lines = text.trim().split(/\r?\n/);
  if (lines.length < 2) return null;

  const headers = parseCSVLine(lines[0]);
  const rows = [];
  for (let i = 1; i < lines.length; i++) {
    if (!lines[i].trim()) continue;
    const vals = parseCSVLine(lines[i]);
    const obj = {};
    headers.forEach((h, idx) => { obj[h.trim()] = (vals[idx] || '').trim(); });
    rows.push(obj);
  }
  return { headers, rows };
}

function parseCSVLine(line) {
  const result = [];
  let cur = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i+1] === '"') { cur += '"'; i++; }
      else inQuotes = !inQuotes;
    } else if (ch === ',' && !inQuotes) {
      result.push(cur);
      cur = '';
    } else {
      cur += ch;
    }
  }
  result.push(cur);
  return result;
}

/* ── CSV → 소재 객체 변환 */
function csvRowToCreative(row) {
  // tags_display 파싱 – ['태그1', '태그2', ...] 또는 태그1,태그2 형식
  let tags = [];
  const rawTags = row['tags_display'] || row['tags'] || '';
  if (rawTags) {
    const cleaned = rawTags.replace(/^\[|\]$/g, '').replace(/'/g, '').replace(/"/g, '');
    tags = cleaned.split(',').map(t => t.trim()).filter(Boolean);
  }

  const scoreVal = parseFloat(row['Total Score'] || row['total_score'] || row['score'] || 0);
  const rankVal  = parseInt(row['rank'] || row['Rank'] || 99, 10);

  // 등급 자동 계산 (CSV에 없으면 score 기준)
  let grade = row['성과 등급'] || row['grade'] || '';
  if (!grade) {
    if (scoreVal >= 50) grade = '최우수';
    else if (scoreVal >= 35) grade = '우수';
    else if (scoreVal >= 20) grade = '보통';
    else grade = '미흡';
  }

  return {
    name:      row['소재명'] || row['name'] || '',
    type:      (row['유형'] || row['type'] || 'BNR').toUpperCase(),
    score:     isNaN(scoreVal) ? 0 : scoreVal,
    rank:      isNaN(rankVal)  ? 99 : rankVal,
    grade,
    cluster:   row['생성된 군집명'] || row['cluster'] || '캐릭터 수집 매력형',
    fileCount: parseInt(row['파일수'] || row['file_count'] || 1, 10),
    tags,
    link:      row['링크'] || row['link'] || ''
  };
}

/* ── 상태 메시지 표시 */
function showUploadStatus(msg, type = 'success') {
  const el = document.getElementById('uploadStatus');
  if (!el) return;
  el.textContent = msg;
  el.className = `upload-status ${type}`;
  setTimeout(() => { el.className = 'upload-status'; }, 5000);
}

/* ── 데이터 요약 렌더 */
function renderDataSummary() {
  const data = window.AppData.creatives;
  const stats = calcStats(data);
  const grades = ['최우수','우수','보통','미흡'];
  const gradeCounts = grades.map(g => data.filter(c=>c.grade===g).length);
  const clusters = [...new Set(data.map(c=>c.cluster))];

  const el = document.getElementById('dataSummary');
  if (!el) return;
  el.innerHTML = [
    { val: stats.total,      label: '전체 소재' },
    { val: stats.vidCount,   label: 'VID 소재' },
    { val: stats.bnrCount,   label: 'BNR 소재' },
    { val: gradeCounts[0],   label: '최우수' },
    { val: gradeCounts[1],   label: '우수' },
    { val: gradeCounts[2],   label: '보통' },
    { val: gradeCounts[3],   label: '미흡' },
    { val: clusters.length,  label: '군집 수' }
  ].map(item => `
    <div class="data-summary-item">
      <div class="data-summary-value">${item.val}</div>
      <div class="data-summary-label">${item.label}</div>
    </div>
  `).join('');
}

/* ── 전체 대시보드 새로고침 */
function refreshDashboard() {
  const data = window.AppData.creatives;
  renderAllCharts(data);
  renderTable(data);
  renderPreviewGrid(data);
  renderClusterGrid();
  renderDataSummary();
  renderTagImpactChart();
}

/* ── CSV 처리 */
function handleCSV(file) {
  if (!file || !file.name.endsWith('.csv')) {
    showUploadStatus('CSV 파일만 업로드 가능합니다.', 'error');
    return;
  }
  const reader = new FileReader();
  reader.onload = (e) => {
    try {
      const parsed = parseCSV(e.target.result);
      if (!parsed) { showUploadStatus('CSV 파싱 실패: 내용이 없습니다.', 'error'); return; }

      // 필수 컬럼 확인
      const required = ['소재명', 'Total Score', 'rank'];
      const missing = required.filter(r => !parsed.headers.includes(r));
      if (missing.length) {
        // 영문 컬럼명도 허용
        const missingEn = missing.filter(r => !parsed.headers.includes(r.toLowerCase()));
        if (missingEn.length) {
          showUploadStatus(`누락된 컬럼: ${missingEn.join(', ')}`, 'error');
          return;
        }
      }

      const newCreatives = parsed.rows
        .map(csvRowToCreative)
        .filter(c => c.name);

      if (!newCreatives.length) {
        showUploadStatus('유효한 소재 데이터가 없습니다.', 'error');
        return;
      }

      // 링크 컬럼이 있는 경우 CREATIVE_URLS에 반영 (소재명 기준 그룹핑)
      const linkMap = {};
      parsed.rows.forEach(row => {
        const name = (row['소재명'] || '').trim();
        const link = (row['링크'] || row['link'] || '').trim();
        if (name && link) {
          if (!linkMap[name]) linkMap[name] = [];
          if (!linkMap[name].includes(link)) linkMap[name].push(link);
        }
      });
      Object.assign(CREATIVE_URLS, linkMap);

      window.AppData.creatives = newCreatives;
      window.AppData.save();
      refreshDashboard();
      showUploadStatus(`✅ ${newCreatives.length}개 소재 데이터를 성공적으로 불러왔습니다.`, 'success');
    } catch(err) {
      showUploadStatus(`오류: ${err.message}`, 'error');
    }
  };
  reader.readAsText(file, 'utf-8');
}

/* ── CSV 내보내기 */
function exportCSV() {
  const data = window.AppData.creatives;
  const headers = ['소재명', '유형', 'Total Score', 'rank', '성과 등급', '생성된 군집명', 'tags_display'];
  const rows = data.map(c => [
    c.name, c.type, c.score, c.rank, c.grade, c.cluster,
    `"[${c.tags.map(t => `'${t}'`).join(', ')}]"`
  ]);
  const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = `pepph_heroes_analysis_${Date.now()}.csv`;
  a.click(); URL.revokeObjectURL(url);
}

/* ── 군집 내 주요 소재 리스트 HTML 생성 */
function buildClusterCreativeList(creatives) {
  const topCreatives = [...creatives].sort((a, b) => b.score - a.score).slice(0, 5);
  if (!topCreatives.length) return '<p style="color:var(--text-muted); font-size:13px;">소재 없음</p>';

  return topCreatives.map(c => {
    const urls   = CREATIVE_URLS[c.name] || [];
    const imgUrl = urls[0] || '';
    const isVid  = c.type === 'VID';
    const typeCls = isVid ? 'vid' : 'bnr';
    const tags   = c.tags.slice(0, 3).map(t => {
      const cls = tagClass(t);
      return `<span class="tag-pill ${cls}" style="font-size:10px;">${t}</span>`;
    }).join('');

    const thumbHtml = imgUrl
      ? `<div class="ccl-thumb-wrap">
           <img src="${imgUrl}" alt="${c.name}"
             onerror="this.parentNode.innerHTML='<div class=\\'ccl-thumb-placeholder\\'><i class=\\'fas fa-${isVid ? 'film' : 'image'}\\'></i></div>'" />
           ${isVid ? '<span class="ccl-play-icon"><i class="fas fa-play"></i></span>' : ''}
         </div>`
      : `<div class="ccl-thumb-wrap">
           <div class="ccl-thumb-placeholder"><i class="fas fa-${isVid ? 'film' : 'image'}"></i></div>
           ${isVid ? '<span class="ccl-play-icon"><i class="fas fa-play"></i></span>' : ''}
         </div>`;

    return `
      <div class="cluster-creative-item" onclick="openPreviewModal('${c.name}')" title="${c.name} 상세 보기">
        ${thumbHtml}
        <div class="ccl-info">
          <div class="ccl-name">${c.name}</div>
          <div class="ccl-meta">
            <span class="type-badge ${typeCls}" style="font-size:10px;">${c.type}</span>
            <span class="grade-badge grade-${c.grade}" style="font-size:10px;">${c.grade}</span>
            <span class="ccl-score">${c.score}점</span>
          </div>
          <div class="ccl-tags">${tags}</div>
        </div>
      </div>`;
  }).join('');
}

/* ── 군집 카드 렌더 */
function renderClusterGrid() {
  const el = document.getElementById('clusterGrid');
  if (!el) return;
  const data = window.AppData.creatives;

  const insights = Object.values(CLUSTER_INSIGHTS);
  if (!insights.length) {
    el.innerHTML = `
      <div style="grid-column:1/-1;text-align:center;padding:48px 24px;background:#fff;border-radius:16px;box-shadow:0 2px 8px rgba(0,0,0,.06);">
        <i class="fas fa-sitemap" style="font-size:40px;color:var(--primary);opacity:.4;margin-bottom:16px;display:block;"></i>
        <h3 style="margin:0 0 8px;color:var(--text-primary);">파이프라인 군집 데이터 없음</h3>
        <p style="margin:0;color:var(--text-muted);font-size:14px;">
          <a href="pipeline.html" style="color:var(--primary);font-weight:700;">파이프라인</a>에서 군집화 분석을 완료하고 차수를 저장하면<br>여기에 자동으로 반영됩니다.
        </p>
      </div>`;
    return;
  }

  // 군집 색상 팔레트
  const COLORS = ['#5c6ef8','#ff7043','#26c281','#ffd234','#29b6f6','#ab47bc','#78909c'];

  el.innerHTML = insights.map((insight, idx) => {
    const isOther = insight.name === '기타 / 단독 소재';
    const color   = isOther ? '#9e9e9e' : COLORS[idx % COLORS.length];
    const creatives = data.filter(c => c.cluster === insight.name);
    const avgScore  = creatives.length
      ? (creatives.reduce((s,c) => s+c.score, 0) / creatives.length).toFixed(1)
      : (insight.avgScore || 0);
    const vidCount = creatives.filter(c => c.type === 'VID').length;
    const bnrCount = creatives.filter(c => c.type === 'BNR').length;
    const best  = creatives.length ? creatives.reduce((a, b) => a.score > b.score ? a : b) : null;
    const worst = creatives.length ? creatives.reduce((a, b) => a.score < b.score ? a : b) : null;

    const posTagHtml = (insight.topTags || []).map(t =>
      `<span class="cluster-tag-pill">${t}</span>`
    ).join('');
    const negTagHtml = (insight.weakTags || []).map(t =>
      `<span class="cluster-tag-pill neg">${t}</span>`
    ).join('');

    // 파이프라인 우승 공식 / 엑시트 패턴 (round에 저장된 경우)
    const round = (() => {
      try {
        const raw = localStorage.getItem('ph_pipeline_rounds_v2');
        if (!raw) return null;
        const rounds = JSON.parse(raw);
        return rounds.length ? rounds[rounds.length - 1] : null;
      } catch { return null; }
    })();
    const winFormula = (round && idx === 0) ? (round.winningFormula || '') : '';
    const exitPat    = (round && idx === 0) ? (round.exitPattern    || '') : '';

    return `
    <div class="cluster-card" style="border-top:4px solid ${color};">
      <div class="cluster-card-header">
        <h3 style="color:${color};">${insight.name}</h3>
        <div class="cluster-meta">
          <div class="cluster-meta-item"><strong>${creatives.length || insight.count || 0}</strong> 소재</div>
          <div class="cluster-meta-item">평균 Score <strong>${avgScore}</strong></div>
          <div class="cluster-meta-item">VID <strong>${vidCount}</strong> / BNR <strong>${bnrCount}</strong></div>
        </div>
      </div>
      <div class="cluster-card-body">
        ${insight.description ? `
        <div class="insight-section">
          <div class="insight-label">군집 특성</div>
          <div class="insight-text">${insight.description}</div>
        </div>` : ''}
        ${insight.successCause ? `
        <div class="insight-section">
          <div class="insight-label">✅ 성공 원인</div>
          <div class="insight-text">${insight.successCause}</div>
        </div>` : ''}
        ${insight.failCause ? `
        <div class="insight-section">
          <div class="insight-label">⚠️ 실패 원인</div>
          <div class="insight-text">${insight.failCause}</div>
        </div>` : ''}
        ${insight.improvement ? `
        <div class="insight-section">
          <div class="insight-label">💡 개선 방향</div>
          <div class="insight-text">${insight.improvement}</div>
        </div>` : ''}
        ${winFormula ? `
        <div class="insight-section">
          <div class="insight-label">🏆 우승 공식</div>
          <div class="insight-text" style="color:var(--primary);font-weight:600;">${winFormula}</div>
        </div>` : ''}
        ${exitPat ? `
        <div class="insight-section">
          <div class="insight-label">🚪 엑시트 패턴</div>
          <div class="insight-text" style="color:var(--danger);">${exitPat}</div>
        </div>` : ''}
        ${posTagHtml ? `
        <div class="insight-section">
          <div class="insight-label">핵심 태그</div>
          <div class="tag-list">${posTagHtml}</div>
        </div>` : ''}
        ${negTagHtml ? `
        <div class="insight-section">
          <div class="insight-label">약점 태그</div>
          <div class="tag-list">${negTagHtml}</div>
        </div>` : ''}
        <div class="insight-section" style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:12px;">
          <div style="background:#f0fff8; border-radius:8px; padding:10px;">
            <div style="font-size:11px; color:var(--text-muted); margin-bottom:4px;">🏆 최우수 소재</div>
            <div style="font-size:12px; font-weight:700;">${best?.name || insight.bestCreative || '-'}</div>
            <div style="font-size:18px; font-weight:800; color:var(--success);">${best?.score ?? '-'}</div>
          </div>
          <div style="background:#fff5f5; border-radius:8px; padding:10px;">
            <div style="font-size:11px; color:var(--text-muted); margin-bottom:4px;">⬇️ 최저 소재</div>
            <div style="font-size:12px; font-weight:700;">${worst?.name || insight.worstCreative || '-'}</div>
            <div style="font-size:18px; font-weight:800; color:var(--danger);">${worst?.score ?? '-'}</div>
          </div>
        </div>
        ${creatives.length ? `
        <div class="insight-section" style="margin-top:16px;">
          <div class="insight-label">📌 군집 내 주요 소재 (Score 상위 5개)</div>
          <div class="cluster-creative-list">
            ${buildClusterCreativeList(creatives)}
          </div>
        </div>` : ''}
      </div>
    </div>`;
  }).join('');
}

/* ── 이벤트 바인딩 */
function initUpload() {
  // 드래그 앤 드롭
  const dropZone = document.getElementById('dropZone');
  if (dropZone) {
    dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    dropZone.addEventListener('drop', e => {
      e.preventDefault();
      dropZone.classList.remove('dragover');
      const file = e.dataTransfer.files[0];
      if (file) handleCSV(file);
    });
  }

  // 파일 선택 버튼
  const btnSelect = document.getElementById('btnSelectFile');
  const fileInput = document.getElementById('fileInput');
  if (btnSelect && fileInput) {
    btnSelect.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', e => {
      if (e.target.files[0]) handleCSV(e.target.files[0]);
    });
  }

  // 헤더 업로드 버튼 → 업로드 탭 이동
  const btnUploadTrigger = document.getElementById('btnUploadTrigger');
  if (btnUploadTrigger) {
    btnUploadTrigger.addEventListener('click', () => {
      switchTab('upload');
      const fileInput2 = document.getElementById('fileInput');
      if (fileInput2) fileInput2.click();
    });
  }

  // 수동 추가 폼
  const manualForm = document.getElementById('manualAddForm');
  if (manualForm) {
    manualForm.addEventListener('submit', e => {
      e.preventDefault();
      const name  = document.getElementById('f_name').value.trim();
      const type  = document.getElementById('f_type').value;
      const score = parseFloat(document.getElementById('f_score').value);
      const rank  = parseInt(document.getElementById('f_rank').value, 10);
      const grade = document.getElementById('f_grade').value;
      const cluster = document.getElementById('f_cluster').value;
      const tags  = document.getElementById('f_tags').value.split(',').map(t=>t.trim()).filter(Boolean);
      const link  = document.getElementById('f_link').value.trim();

      if (!name || isNaN(score) || isNaN(rank)) {
        alert('필수 항목(소재명, Total Score, Rank)을 입력해주세요.'); return;
      }

      // 중복 확인
      const exists = window.AppData.creatives.findIndex(c => c.name === name);
      const newEntry = { name, type, score, rank, grade, cluster, fileCount: 1, tags, link };

      if (exists >= 0) {
        if (confirm(`'${name}' 소재가 이미 존재합니다. 업데이트하시겠습니까?`)) {
          window.AppData.creatives[exists] = newEntry;
        } else return;
      } else {
        window.AppData.creatives.push(newEntry);
        window.AppData.creatives.sort((a,b) => a.rank - b.rank);
      }

      // URL 추가
      if (link) CREATIVE_URLS[name] = [link];

      window.AppData.save();
      refreshDashboard();
      manualForm.reset();
      alert(`✅ '${name}' 소재가 추가되었습니다.`);
    });
  }

  // 내보내기
  const btnExport = document.getElementById('btnExportCSV');
  if (btnExport) btnExport.addEventListener('click', exportCSV);

  // 초기화
  const btnReset = document.getElementById('btnResetData');
  if (btnReset) {
    btnReset.addEventListener('click', () => {
      if (confirm('모든 데이터를 기본값으로 초기화하시겠습니까?')) {
        window.AppData.reset();
        refreshDashboard();
        showUploadStatus('✅ 데이터가 초기화되었습니다.', 'success');
      }
    });
  }

  // 초기 데이터 요약
  renderDataSummary();
}
