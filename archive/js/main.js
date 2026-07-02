/**
 * Pepp Heroes – Main Entry Point
 * 탭 네비게이션 + 초기화
 * ★ v2: 파이프라인 확정 데이터 자동 연동
 */

/* ── 파이프라인 연동 배너 표시 */
function showPipelineBanner(meta) {
  const banner = document.getElementById('pipelineSyncBanner');
  if (!banner) return;
  if (!meta) {
    // 파이프라인 데이터 없음 → 기본 데이터 사용 안내
    banner.className = 'pipeline-sync-banner warn';
    banner.innerHTML = `
      <i class="fas fa-exclamation-triangle"></i>
      <div class="psb-body">
        <strong>파이프라인 데이터 없음</strong>
        <span>현재 기본 샘플 데이터로 표시 중입니다. <a href="pipeline.html">파이프라인</a>에서 분석을 완료하고 차수를 저장하면 자동 반영됩니다.</span>
      </div>`;
    banner.style.display = 'flex';
    return;
  }
  const date = new Date(meta.createdAt).toLocaleDateString('ko-KR', { month:'long', day:'numeric', hour:'2-digit', minute:'2-digit' });
  banner.className = 'pipeline-sync-banner success';
  banner.innerHTML = `
    <i class="fas fa-check-circle"></i>
    <div class="psb-body">
      <strong>파이프라인 데이터 반영 완료</strong>
      <span>
        <b>${meta.roundName}</b> · ${date} 저장 ·
        소재 <b>${meta.count}개</b> · 군집 <b>${meta.clusters}개</b> · 평균 Score <b>${meta.avgScore}</b>
        ${meta.winningFormula ? `· 우승 공식: <em>${meta.winningFormula.slice(0,40)}${meta.winningFormula.length>40?'…':''}</em>` : ''}
      </span>
    </div>
    <a href="pipeline.html" class="psb-link"><i class="fas fa-external-link-alt"></i> 파이프라인 열기</a>`;
  banner.style.display = 'flex';
}

/* ── 탭 전환 */
function switchTab(tabName) {
  document.querySelectorAll('.nav-tab').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === tabName);
  });
  document.querySelectorAll('.tab-section').forEach(sec => {
    sec.classList.toggle('active', sec.id === `tab-${tabName}`);
  });

  // 탭 진입 시 차트 재렌더 (캔버스 크기 문제 방지)
  const data = window.AppData.creatives;
  if (tabName === 'overview') {
    setTimeout(() => {
      renderScoreBarChart(data);
      renderClusterPieChart(data);
      renderTypeCompareChart(data);
    }, 50);
  } else if (tabName === 'tags') {
    setTimeout(() => {
      renderTagImpactChart();
      renderTagLists();
      renderTagCloud(data);
    }, 50);
  } else if (tabName === 'preview') {
    renderPreviewGrid(data);
  } else if (tabName === 'cluster') {
    renderClusterGrid();
  } else if (tabName === 'upload') {
    renderDataSummary();
  }
}

/* ── 탭 버튼 바인딩 */
function initNavTabs() {
  document.querySelectorAll('.nav-tab').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });
}

/* ── 앱 초기화 */
function initApp() {
  // ★ 1단계: 파이프라인 확정 데이터 자동 적용
  const pipelineMeta = applyPipelineDataToDashboard();
  showPipelineBanner(pipelineMeta || null);

  const data = window.AppData.creatives;

  // 탭 네비게이션
  initNavTabs();

  // 각 모듈 초기화
  initTable();
  initPreview();
  initUpload();

  // 초기 차트 렌더 (overview 탭)
  setTimeout(() => {
    renderAllCharts(data);
    renderClusterGrid();
    renderDataSummary();
  }, 100);

  console.log('🎮 Pepp Heroes 대시보드 초기화 완료 · 소재 수:', data.length,
    pipelineMeta ? `· 파이프라인 차수: ${pipelineMeta.roundName}` : '· (기본 데이터)');
}

/* ── DOM 준비 완료 후 실행 */
document.addEventListener('DOMContentLoaded', initApp);
