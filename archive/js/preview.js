/**
 * Pepp Heroes – Preview Module
 * 소재 미리보기 카드 & 모달
 */

let currentPreviewFilter = { grade: 'all', type: 'all' };

/* ── 미리보기 카드 HTML */
function buildPreviewCard(creative) {
  const imgUrls = CREATIVE_URLS[creative.name] || [];
  const imgUrl  = imgUrls[0] || '';
  const isVid   = creative.type === 'VID';

  const imgHtml = imgUrl
    ? `<img src="${imgUrl}" alt="${creative.name}"
         style="${isVid ? 'filter:brightness(0.82);' : ''}"
         onerror="this.parentNode.innerHTML='<div class=\\'preview-img-placeholder\\'><i class=\\'fas fa-${isVid ? 'film' : 'image'}\\'></i><span>${isVid ? 'VID 소재' : '미리보기 없음'}</span></div>'"
       />`
    : `<div class="preview-img-placeholder" style="${isVid ? 'background:#1a1f3c; color:#7a8bff;' : ''}">
         <i class="fas fa-${isVid ? 'film' : 'image'}"></i>
         <span>${isVid ? 'VID 소재' : '미리보기 없음'}</span>
       </div>`;

  // VID: 재생 아이콘 오버레이 추가
  const playOverlay = isVid
    ? `<div style="position:absolute; inset:0; display:flex; align-items:center; justify-content:center; pointer-events:none;">
         <div style="width:40px; height:40px; background:rgba(92,110,248,0.85); border-radius:50%; display:flex; align-items:center; justify-content:center; color:#fff; font-size:15px;">
           <i class="fas fa-play" style="margin-left:3px;"></i>
         </div>
       </div>`
    : '';

  const tags = creative.tags.slice(0, 4).map(t => {
    const cls = tagClass(t);
    return `<span class="tag-pill ${cls}">${t}</span>`;
  }).join('');

  const typeCls = isVid ? 'vid' : 'bnr';

  return `<div class="preview-card" data-name="${creative.name}" data-grade="${creative.grade}" data-type="${creative.type}" onclick="openPreviewModal('${creative.name}')">
    <div class="preview-img-wrap">
      ${imgHtml}
      ${playOverlay}
      <div class="preview-rank-overlay">#${creative.rank}</div>
    </div>
    <div class="preview-card-body">
      <div class="preview-card-name" title="${creative.name}">${creative.name}</div>
      <div class="preview-card-meta">
        <span class="preview-score">${creative.score}</span>
        <span class="type-badge ${typeCls}">${creative.type}</span>
        <span class="grade-badge grade-${creative.grade}">${creative.grade}</span>
      </div>
      <div class="preview-card-tags">${tags}</div>
    </div>
  </div>`;
}

/* ── 미리보기 그리드 렌더링 */
function renderPreviewGrid(data) {
  const filtered = data.filter(c => {
    const gradeOk = currentPreviewFilter.grade === 'all' || c.grade === currentPreviewFilter.grade;
    const typeOk  = currentPreviewFilter.type  === 'all' || c.type  === currentPreviewFilter.type;
    return gradeOk && typeOk;
  });
  const sorted = [...filtered].sort((a, b) => a.rank - b.rank);

  const gridEl = document.getElementById('previewGrid');
  if (!gridEl) return;
  gridEl.innerHTML = sorted.length
    ? sorted.map(buildPreviewCard).join('')
    : `<div style="grid-column:1/-1; text-align:center; padding:48px; color:var(--text-muted);">
         <i class="fas fa-search" style="font-size:32px; margin-bottom:12px; display:block;"></i>
         해당 조건의 소재가 없습니다.
       </div>`;
}

/* ── 모달 열기 */
function openPreviewModal(creativeName) {
  const creative = window.AppData.creatives.find(c => c.name === creativeName);
  if (!creative) return;

  const imgUrls = CREATIVE_URLS[creative.name] || [];
  const typeCls = creative.type === 'VID' ? 'vid' : 'bnr';
  const clsCls  = creative.cluster.includes('2') ? 'c2' : '';

  const isVid = creative.type === 'VID';
  const imagesHtml = imgUrls.length
    ? `<div style="display:flex; gap:12px; flex-wrap:wrap; margin-bottom:20px;">
        ${imgUrls.map((url, i) => `
          <div style="flex:1; min-width:200px; position:relative;">
            <div style="font-size:11px; color:var(--text-muted); margin-bottom:4px; display:flex; align-items:center; gap:6px;">
              ${isVid ? '<i class="fas fa-film" style="color:var(--primary);"></i>' : '<i class="fas fa-image" style="color:var(--secondary);"></i>'}
              파일 ${i+1}
              <a href="${url}" target="_blank" rel="noopener"
                 style="margin-left:auto; font-size:10px; color:var(--primary); text-decoration:none; display:flex; align-items:center; gap:3px;">
                <i class="fas fa-external-link-alt"></i> 원본 보기
              </a>
            </div>
            <div style="position:relative; display:inline-block; width:100%;">
              <img src="${url}" alt="소재 ${i+1}"
                style="width:100%; border-radius:8px; border:1px solid var(--border); display:block; ${isVid ? 'filter:brightness(0.88);' : ''}"
                onerror="this.parentNode.innerHTML='<div style=\\'height:140px; background:#1a1f3c; border-radius:8px; display:flex; flex-direction:column; align-items:center; justify-content:center; color:#7a8bff; gap:8px;\\'><i class=\\'fas fa-film\\'></i><span style=\\'font-size:11px;\\'>썸네일 미제공</span></div>'" />
              ${isVid ? `<div style="position:absolute; inset:0; display:flex; align-items:center; justify-content:center; pointer-events:none;">
                <a href="${url}" target="_blank" rel="noopener"
                   style="width:48px; height:48px; background:rgba(92,110,248,0.9); border-radius:50%; display:flex; align-items:center; justify-content:center; color:#fff; font-size:18px; pointer-events:all; text-decoration:none;">
                  <i class="fas fa-play" style="margin-left:3px;"></i>
                </a>
              </div>` : ''}
            </div>
          </div>`).join('')}
      </div>`
    : `<div style="height:140px; background:${isVid ? '#1a1f3c' : 'var(--bg)'}; border-radius:8px; display:flex; align-items:center; justify-content:center; color:${isVid ? '#7a8bff' : 'var(--text-muted)'}; margin-bottom:20px;">
         <div style="text-align:center;"><i class="fas fa-${isVid ? 'film' : 'image'}" style="font-size:36px; display:block; margin-bottom:8px;"></i>${isVid ? 'VID 소재 – 링크 없음' : '미리보기 없음'}</div>
       </div>`;

  const allTagHtml = creative.tags.map(t => {
    const cls = tagClass(t);
    return `<span class="tag-pill ${cls}">${t}</span>`;
  }).join('');

  const insight = CLUSTER_INSIGHTS[creative.cluster];
  const insightHtml = insight
    ? `<div style="background:var(--bg); border-radius:8px; padding:14px; margin-top:16px; font-size:13px; line-height:1.7; color:var(--text-secondary);">
         <strong style="color:var(--text-primary);">군집 인사이트</strong><br/>
         ${creative.score >= 50 ? '✅ 성공 요인: ' + insight.successCause : '⚠️ 실패 요인: ' + insight.failCause}
         <br/><strong style="color:var(--text-primary);">개선 방향:</strong> ${insight.improvement}
       </div>`
    : '';

  document.getElementById('modalContent').innerHTML = `
    <div style="margin-bottom:16px; padding-bottom:14px; border-bottom:1px solid var(--border);">
      <h3 style="font-size:16px; font-weight:800; margin-bottom:8px;">${creative.name}</h3>
      <div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;">
        <span class="type-badge ${typeCls}">${creative.type}</span>
        <span class="grade-badge grade-${creative.grade}">${creative.grade}</span>
        <span class="cluster-tag ${clsCls}">${creative.cluster}</span>
        <span style="font-size:13px; color:var(--text-muted);">파일 ${creative.fileCount}개</span>
      </div>
    </div>

    ${imagesHtml}

    <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; margin-bottom:16px;">
      <div style="background:var(--primary-light); border-radius:8px; padding:12px; text-align:center;">
        <div style="font-size:24px; font-weight:800; color:var(--primary);">${creative.score}</div>
        <div style="font-size:11px; color:var(--text-muted);">Total Score</div>
      </div>
      <div style="background:#f0fdf4; border-radius:8px; padding:12px; text-align:center;">
        <div style="font-size:24px; font-weight:800; color:var(--success);">#${creative.rank}</div>
        <div style="font-size:11px; color:var(--text-muted);">순위</div>
      </div>
      <div style="background:#f5f5f5; border-radius:8px; padding:12px; text-align:center;">
        <div style="font-size:22px; font-weight:800; color:var(--text-primary);">${creative.type}</div>
        <div style="font-size:11px; color:var(--text-muted);">포맷</div>
      </div>
    </div>

    <div style="margin-bottom:16px;">
      <div style="font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:0.8px; color:var(--text-muted); margin-bottom:8px;">태그 구성</div>
      <div style="display:flex; flex-wrap:wrap; gap:5px;">${allTagHtml}</div>
    </div>

    ${insightHtml}

    <div style="margin-top:16px; display:flex; gap:8px; flex-wrap:wrap;">
      ${imgUrls.map((url, i) =>
        `<a href="${url}" target="_blank" rel="noopener" class="btn-secondary" style="font-size:12px;">
           <i class="fas fa-${isVid ? 'play-circle' : 'external-link-alt'}"></i>
           ${isVid ? `영상 파일 ${i+1} 보기` : `원본 이미지 ${i+1}`}
         </a>`
      ).join('')}
      ${imgUrls.length === 0 && creative.link
        ? `<a href="${creative.link}" target="_blank" rel="noopener" class="btn-secondary" style="font-size:12px;">
             <i class="fas fa-play-circle"></i> 원본 영상 보기
           </a>`
        : ''}
    </div>
  `;

  document.getElementById('previewModal').classList.add('show');
  document.body.style.overflow = 'hidden';
}

/* ── 모달 닫기 */
function closePreviewModal() {
  document.getElementById('previewModal').classList.remove('show');
  document.body.style.overflow = '';
}

/* ── 이벤트 바인딩 */
function initPreview() {
  // 필터 버튼 (등급/유형 그룹 분리)
  document.querySelectorAll('.preview-filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const filterType = btn.dataset.filterType; // 'grade' or 'type'
      // 같은 그룹 내 active 제거
      document.querySelectorAll(`.preview-filter-btn[data-filter-type="${filterType}"]`)
        .forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentPreviewFilter[filterType] = btn.dataset.filter;
      renderPreviewGrid(window.AppData.creatives);
    });
  });

  // 모달 닫기
  const modalClose = document.getElementById('modalClose');
  if (modalClose) modalClose.addEventListener('click', closePreviewModal);

  const overlay = document.getElementById('previewModal');
  if (overlay) {
    overlay.addEventListener('click', e => {
      if (e.target === overlay) closePreviewModal();
    });
  }

  // ESC 키
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closePreviewModal();
  });

  // 초기 렌더
  renderPreviewGrid(window.AppData.creatives);
}

/* ── window에 노출 (table.js의 onclick 사용) */
window.openPreviewModal = openPreviewModal;
