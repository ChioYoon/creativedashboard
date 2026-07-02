/**
 * Pepp Heroes – Table Module
 * 소재 비교표 렌더링 및 정렬/필터
 */

let currentSortCol  = 'rank';
let currentSortDir  = 'asc';
let currentFilters  = { search: '', cluster: '', type: '', grade: '' };

/* ── 테이블 행 HTML 생성 */
function buildTableRow(creative) {
  const urls    = CREATIVE_URLS[creative.name] || [];
  const imgUrl  = urls[0] || '';
  const isVid   = creative.type === 'VID';
  const rankClass = creative.rank <= 3 ? 'top3' : (creative.rank <= 10 ? 'top10' : '');
  const barClass  = scoreClass(creative.score);
  const typeCls   = isVid ? 'vid' : 'bnr';
  const clsCls    = creative.cluster.includes('2') ? 'c2' : '';
  const pct       = ((creative.score / 65) * 100).toFixed(0);

  const tagHtml = creative.tags.slice(0, 5).map(t => {
    const cls = tagClass(t);
    return `<span class="tag-pill ${cls}">${t}</span>`;
  }).join('') + (creative.tags.length > 5 ? `<span class="tag-pill">+${creative.tags.length - 5}</span>` : '');

  /* ── 미리보기 셀: VID는 재생 오버레이 + 모달 링크, BNR은 이미지 썸네일 */
  let thumbHtml;
  if (isVid) {
    // VID: 썸네일 이미지(있으면) 위에 재생 아이콘 오버레이 표시
    thumbHtml = `
      <div class="thumb-wrap" onclick="openPreviewModal('${creative.name}')" title="${creative.name} 상세 보기">
        ${imgUrl
          ? `<img src="${imgUrl}" class="preview-thumb vid-thumb" alt="${creative.name}"
               onerror="this.src=''; this.style.display='none'; this.nextElementSibling.style.display='flex';" />
             <span class="no-preview vid-placeholder" style="display:none;"><i class="fas fa-film"></i></span>`
          : `<span class="no-preview vid-placeholder"><i class="fas fa-film"></i></span>`
        }
        <span class="play-overlay"><i class="fas fa-play"></i></span>
      </div>`;
    // 외부 링크가 있으면 링크 버튼도 추가
    if (creative.link) {
      thumbHtml += `<a href="${creative.link}" target="_blank" rel="noopener" class="vid-link-btn" title="원본 영상 보기">
        <i class="fas fa-external-link-alt"></i>
      </a>`;
    }
  } else {
    // BNR: 이미지 썸네일
    thumbHtml = imgUrl
      ? `<img src="${imgUrl}" class="preview-thumb" alt="${creative.name}"
           onerror="this.outerHTML='<span class=\\'no-preview\\'><i class=\\'fas fa-image\\'></i></span>'"
           onclick="openPreviewModal('${creative.name}')" />`
      : `<span class="no-preview"><i class="fas fa-image"></i></span>`;
  }

  return `<tr data-name="${creative.name}">
    <td><span class="rank-badge ${rankClass}">${creative.rank}</span></td>
    <td><strong>${creative.name}</strong></td>
    <td><span class="type-badge ${typeCls}">${creative.type}</span></td>
    <td>
      <div class="score-bar-cell">
        <div class="score-bar-bg">
          <div class="score-bar-fill ${barClass}" style="width:${pct}%"></div>
        </div>
        <span class="score-num">${creative.score}</span>
      </div>
    </td>
    <td><span class="grade-badge grade-${creative.grade}">${creative.grade}</span></td>
    <td><span class="cluster-tag ${clsCls}">${creative.cluster}</span></td>
    <td class="tags-cell">${tagHtml}</td>
    <td class="thumb-cell">${thumbHtml}</td>
  </tr>`;
}

/* ── 필터링 */
function applyFilters(data) {
  return data.filter(c => {
    if (currentFilters.search) {
      const q = currentFilters.search.toLowerCase();
      if (!c.name.toLowerCase().includes(q) && !c.tags.join(' ').toLowerCase().includes(q)) return false;
    }
    if (currentFilters.cluster && c.cluster !== currentFilters.cluster) return false;
    if (currentFilters.type    && c.type    !== currentFilters.type)    return false;
    if (currentFilters.grade   && c.grade   !== currentFilters.grade)   return false;
    return true;
  });
}

/* ── 정렬 */
function sortData(data) {
  const dir = currentSortDir === 'asc' ? 1 : -1;
  return [...data].sort((a, b) => {
    let va = a[currentSortCol], vb = b[currentSortCol];
    if (typeof va === 'string') va = va.toLowerCase();
    if (typeof vb === 'string') vb = vb.toLowerCase();
    return va < vb ? -dir : va > vb ? dir : 0;
  });
}

/* ── 테이블 렌더링 */
function renderTable(data) {
  const filtered = applyFilters(data);
  const sorted   = sortData(filtered);
  const tbody = document.getElementById('mainTableBody');
  const count = document.getElementById('tableCount');
  if (!tbody) return;
  tbody.innerHTML = sorted.map(buildTableRow).join('');
  if (count) count.textContent = `${sorted.length}개 소재`;
}

/* ── 정렬 컬럼 매핑 */
const COL_MAP = {
  rank: 'rank', name: 'name', type: 'type', score: 'score', grade: 'grade', cluster: 'cluster'
};

/* ── 이벤트 바인딩 */
function initTable() {
  // 검색
  const searchEl = document.getElementById('tableSearch');
  if (searchEl) {
    searchEl.addEventListener('input', e => {
      currentFilters.search = e.target.value;
      renderTable(window.AppData.creatives);
    });
  }

  // 필터 셀렉트
  ['filterCluster', 'filterType', 'filterGrade'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('change', e => {
      const key = id.replace('filter','').toLowerCase();
      currentFilters[key] = e.target.value;
      renderTable(window.AppData.creatives);
    });
  });

  // 컬럼 정렬
  document.querySelectorAll('.data-table th.sortable').forEach(th => {
    th.addEventListener('click', () => {
      const col = COL_MAP[th.dataset.col];
      if (!col) return;
      if (currentSortCol === col) {
        currentSortDir = currentSortDir === 'asc' ? 'desc' : 'asc';
      } else {
        currentSortCol = col;
        currentSortDir = col === 'rank' ? 'asc' : 'desc';
      }
      // 아이콘 업데이트
      document.querySelectorAll('.data-table th.sortable i').forEach(i => {
        i.className = 'fas fa-sort';
      });
      th.querySelector('i').className = `fas fa-sort-${currentSortDir === 'asc' ? 'up' : 'down'}`;
      renderTable(window.AppData.creatives);
    });
  });

  // 초기 렌더
  renderTable(window.AppData.creatives);
}
