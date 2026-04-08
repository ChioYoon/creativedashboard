/**
 * Pepp Heroes – Charts Module
 * Chart.js 기반 시각화
 */

let scoreBarChartInst = null;
let clusterPieChartInst = null;
let typeCompareChartInst = null;
let tagImpactChartInst = null;

// ── 공통 Chart 기본값
Chart.defaults.font.family = "'Pretendard', -apple-system, sans-serif";
Chart.defaults.color = '#5a6072';

function destroyChart(inst) {
  if (inst) { try { inst.destroy(); } catch(e) {} }
}

/* ── 1. 소재명별 Total Score 가로 바 차트 */
function renderScoreBarChart(data) {
  destroyChart(scoreBarChartInst);
  const sorted = [...data].sort((a, b) => a.score - b.score);
  const labels = sorted.map(c => c.name.replace('A-', '').replace('-DA','').replace('-UA','').replace('-FK',''));
  const scores = sorted.map(c => c.score);
  const colors = sorted.map(c => {
    if (c.score >= 50) return 'rgba(92,110,248,0.85)';
    if (c.score >= 35) return 'rgba(38,194,129,0.85)';
    if (c.score >= 20) return 'rgba(255,210,52,0.85)';
    return 'rgba(244,67,54,0.8)';
  });

  const ctx = document.getElementById('scoreBarChart');
  if (!ctx) return;
  scoreBarChartInst = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Total Score',
        data: scores,
        backgroundColor: colors,
        borderRadius: 5,
        borderSkipped: false
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: (items) => {
              const idx = items[0].dataIndex;
              return sorted[idx].name;
            },
            label: (item) => {
              const d = sorted[item.dataIndex];
              return [
                ` Score: ${d.score}`,
                ` Rank: #${d.rank}`,
                ` 등급: ${d.grade}`,
                ` 군집: ${d.cluster}`,
                ` 유형: ${d.type}`
              ];
            }
          }
        }
      },
      scales: {
        x: {
          max: 65,
          grid: { color: '#f0f2f5' },
          ticks: { font: { size: 11 } }
        },
        y: {
          grid: { display: false },
          ticks: { font: { size: 11 } }
        }
      }
    }
  });
}

/* ── 2. 군집별 도넛 차트 */
function renderClusterPieChart(data) {
  destroyChart(clusterPieChartInst);
  const clusterCounts = {};
  data.forEach(c => {
    clusterCounts[c.cluster] = (clusterCounts[c.cluster] || 0) + 1;
  });
  const labels = Object.keys(clusterCounts);
  const counts = Object.values(clusterCounts);
  const colors = ['#5c6ef8', '#ff7043', '#26c281', '#ffd234', '#29b6f6'];

  const ctx = document.getElementById('clusterPieChart');
  if (!ctx) return;
  clusterPieChartInst = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data: counts,
        backgroundColor: colors.slice(0, labels.length),
        borderWidth: 3,
        borderColor: '#fff',
        hoverOffset: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '60%',
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (item) => ` ${item.label}: ${item.raw}개`
          }
        }
      }
    }
  });

  // Custom legend
  const legendEl = document.getElementById('clusterLegend');
  if (legendEl) {
    legendEl.innerHTML = labels.map((l, i) =>
      `<div class="legend-item">
        <span class="legend-dot" style="background:${colors[i]}"></span>
        <span>${l} (${counts[i]}개)</span>
      </div>`
    ).join('');
  }
}

/* ── 3. VID vs BNR 비교 차트 */
function renderTypeCompareChart(data) {
  destroyChart(typeCompareChartInst);
  const vid = data.filter(c => c.type === 'VID');
  const bnr = data.filter(c => c.type === 'BNR');
  const avg = arr => arr.length ? +(arr.reduce((s,c) => s+c.score,0)/arr.length).toFixed(1) : 0;
  const max = arr => arr.length ? Math.max(...arr.map(c=>c.score)) : 0;
  const min = arr => arr.length ? Math.min(...arr.map(c=>c.score)) : 0;

  const ctx = document.getElementById('typeCompareChart');
  if (!ctx) return;
  typeCompareChartInst = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: ['평균 Score', '최고 Score', '최저 Score', '소재 수'],
      datasets: [
        {
          label: 'VID',
          data: [avg(vid), max(vid), min(vid), vid.length],
          backgroundColor: 'rgba(41,182,246,0.8)',
          borderRadius: 6
        },
        {
          label: 'BNR',
          data: [avg(bnr), max(bnr), min(bnr), bnr.length],
          backgroundColor: 'rgba(255,112,67,0.8)',
          borderRadius: 6
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'top',
          labels: { font: { size: 12 }, padding: 12 }
        }
      },
      scales: {
        y: { grid: { color: '#f0f2f5' }, ticks: { font: { size: 11 } } },
        x: { grid: { display: false }, ticks: { font: { size: 11 } } }
      }
    }
  });
}

/* ── 4. 태그 영향도 차트 */
function renderTagImpactChart() {
  destroyChart(tagImpactChartInst);

  const allTags = [
    ...WINNING_TAGS.slice(0, 8).map(t => ({ ...t, dir: 'win' })),
    ...LOSING_TAGS.slice(0, 8).map(t => ({ ...t, dir: 'lose' }))
  ].sort((a, b) => b.impact - a.impact);

  if (!allTags.length) return; // 데이터 없으면 스킵

  const labels = allTags.map(t => t.tag);
  const values = allTags.map(t => t.impact);
  const colors = allTags.map(t => t.dir === 'win' ? 'rgba(38,194,129,0.8)' : 'rgba(244,67,54,0.8)');

  const ctx = document.getElementById('tagImpactChart');
  if (!ctx) return;
  tagImpactChartInst = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: '점수 영향도',
        data: values,
        backgroundColor: colors,
        borderRadius: 5
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: i => ` 영향도: ${i.raw > 0 ? '+' : ''}${i.raw.toFixed(1)}점`
          }
        }
      },
      scales: {
        x: {
          grid: { color: '#f0f2f5' },
          ticks: { font: { size: 11 } }
        },
        y: {
          grid: { display: false },
          ticks: { font: { size: 11 } }
        }
      }
    }
  });
}

/* ── 태그 영향도 리스트 렌더 */
function renderTagLists() {
  const winEl = document.getElementById('winningTagsList');
  if (winEl) {
    if (!WINNING_TAGS.length) {
      winEl.innerHTML = '<p style="color:var(--text-muted);font-size:13px;padding:8px 0;">파이프라인에서 차수를 저장하면 자동으로 반영됩니다.</p>';
    } else {
      const maxWin = Math.max(...WINNING_TAGS.map(t => t.impact), 0.1);
      winEl.innerHTML = WINNING_TAGS.slice(0, 10).map(t => `
        <div class="tag-impact-item">
          <span class="tag-impact-name">${t.tag.replace('[MI] ','')}</span>
          <div class="tag-impact-bar-wrap">
            <div class="tag-impact-bar-bg">
              <div class="tag-impact-bar-fill win" style="width:${(t.impact/maxWin*100).toFixed(0)}%"></div>
            </div>
          </div>
          <span class="tag-impact-val win">+${t.impact.toFixed(1)}</span>
        </div>
      `).join('');
    }
  }

  const loseEl = document.getElementById('losingTagsList');
  if (loseEl) {
    if (!LOSING_TAGS.length) {
      loseEl.innerHTML = '<p style="color:var(--text-muted);font-size:13px;padding:8px 0;">파이프라인에서 차수를 저장하면 자동으로 반영됩니다.</p>';
    } else {
      const maxLose = Math.max(...LOSING_TAGS.map(t => Math.abs(t.impact)), 0.1);
      loseEl.innerHTML = LOSING_TAGS.slice(0, 10).map(t => `
        <div class="tag-impact-item">
          <span class="tag-impact-name">${t.tag.replace('[MI] ','')}</span>
          <div class="tag-impact-bar-wrap">
            <div class="tag-impact-bar-bg">
              <div class="tag-impact-bar-fill lose" style="width:${(Math.abs(t.impact)/maxLose*100).toFixed(0)}%"></div>
            </div>
          </div>
          <span class="tag-impact-val lose">${t.impact.toFixed(1)}</span>
        </div>
      `).join('');
    }
  }
}

/* ── 태그 클라우드 */
function renderTagCloud(data) {
  const tagFreq = {};
  data.forEach(c => {
    c.tags.forEach(tag => {
      tagFreq[tag] = (tagFreq[tag] || 0) + 1;
    });
  });
  const sorted = Object.entries(tagFreq).sort((a,b) => b[1]-a[1]).slice(0, 40);
  const max = sorted[0][1];

  const cloudEl = document.getElementById('tagCloud');
  if (!cloudEl) return;
  cloudEl.innerHTML = sorted.map(([tag, count]) => {
    const size = 11 + Math.round((count / max) * 14);
    const opacity = 0.5 + (count / max) * 0.5;
    let bg = '#f0f2ff', color = '#5c6ef8';
    if (WIN_TAG_SET.has(tag)) { bg = '#e8f8f1'; color = '#1b7d52'; }
    if (LOSE_TAG_SET.has(tag)) { bg = '#ffeeed'; color = '#c62828'; }
    return `<span class="cloud-tag" title="${tag}: ${count}개 소재"
      style="font-size:${size}px; background:${bg}; color:${color}; opacity:${opacity}">${tag}</span>`;
  }).join('');
}

/* ── KPI 업데이트 */
function updateKPIs(data) {
  const stats = calcStats(data);
  const set = (id, val) => { const el = document.getElementById(id); if(el) el.textContent = val; };
  set('kpi-total', stats.total);
  set('kpi-top',   stats.topScore);
  set('kpi-avg',   stats.avgScore);
  set('kpi-vid',   stats.vidAvg);
  set('kpi-bnr',   stats.bnrAvg);
}

/* ── 모든 차트 렌더링 */
function renderAllCharts(data) {
  updateKPIs(data);
  renderScoreBarChart(data);
  renderClusterPieChart(data);
  renderTypeCompareChart(data);
  renderTagLists();
  renderTagCloud(data);
}
