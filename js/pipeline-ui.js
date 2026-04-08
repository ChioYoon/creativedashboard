/**
 * Pepp Heroes – Pipeline UI Controller
 * 스테이지 전환, 렌더링, 이벤트 바인딩
 * [4단계] 업로드 → 검증 → 군집화 → 인사이트 확정
 */

let currentStage = 1;
let clusterCompareChartInst = null;
Chart.defaults.font.family  = "'Pretendard', -apple-system, sans-serif";
Chart.defaults.color        = '#5a6072';

// ══════════════════════════════════════════
// 스테이지 전환
// ══════════════════════════════════════════
function goToStage(n) {
  currentStage = n;
  document.querySelectorAll('.pl-stage').forEach((s, i) => {
    s.classList.toggle('active', i + 1 === n);
  });
  document.querySelectorAll('.stage-step').forEach((s, i) => {
    s.classList.remove('active', 'done');
    if (i + 1 < n)  s.classList.add('done');
    if (i + 1 === n) s.classList.add('active');
  });
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ══════════════════════════════════════════
// STAGE 1: 업로드
// ══════════════════════════════════════════
function initStage1() {
  const dropZone  = document.getElementById('dropZone1');
  const fileInput = document.getElementById('csvFileInput');

  dropZone.onclick = () => fileInput.click();
  dropZone.ondragover = e => { e.preventDefault(); dropZone.classList.add('drag-over'); };
  dropZone.ondragleave = () => dropZone.classList.remove('drag-over');
  dropZone.ondrop = e => {
    e.preventDefault(); dropZone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  };
  fileInput.onchange = e => { if (e.target.files[0]) handleFileUpload(e.target.files[0]); };

  // 샘플 데이터 로드
  document.getElementById('btnLoadSample').onclick = () => {
    document.getElementById('roundName').value = '2026년 4월 1차 (US_SEA 사전예약)';
    document.getElementById('uploaderName').value = '테스트 마케터';
    document.getElementById('uploadMemo').value = 'Pepp Heroes 사전예약 UA 소재 – US/SEA 캠페인 (BNR+VID 다중 태그 컬럼 구조)';
    handleRawText(SAMPLE_CSV_DATA, '[PH]_사전예약_US-SEA_크리에이티브_sample.csv');
  };

  document.getElementById('btnToStage2').onclick = () => {
    PipelineSession.roundName = document.getElementById('roundName').value.trim() || `차수_${Date.now()}`;
    PipelineSession.uploader  = document.getElementById('uploaderName').value.trim();
    PipelineSession.memo      = document.getElementById('uploadMemo').value.trim();
    runValidation();
    goToStage(2);
  };
}

function handleFileUpload(file) {
  // ★ 인코딩 자동 감지: UTF-8 시도 후 한글 깨짐 감지 시 EUC-KR 재시도
  const tryRead = (encoding, fallback) => {
    const reader = new FileReader();
    reader.onload = e => {
      const text = e.target.result;
      // 한글 깨짐 감지: replacement character (U+FFFD) 또는 의미불명 바이트 패턴
      // EUC-KR을 UTF-8로 읽으면 U+00C0~U+00BF 범위의 깨진 문자가 연속 등장
      const garbledCount = (text.match(/[\uFFFD]/g) || []).length;
      const latinGarbled = (text.match(/[\u00C0-\u00FF]{4,}/g) || []).length;
      const hasGarbled = garbledCount > 5 || latinGarbled > 3;
      if (hasGarbled && fallback) {
        console.log(`[Pipeline] ${encoding} 인코딩 깨짐 감지 → ${fallback} 재시도`);
        tryRead(fallback, null);
      } else {
        console.log(`[Pipeline] ${encoding} 인코딩으로 파일 로드 완료`);
        handleRawText(text, file.name);
      }
    };
    reader.readAsText(file, encoding);
  };
  tryRead('utf-8', 'euc-kr');
}

function handleRawText(text, filename) {
  const parsed = plParseCSV(text);
  if (!parsed) { alert('CSV 파싱 실패: 내용이 없습니다.'); return; }

  PipelineSession.rawRows   = parsed.rows;
  PipelineSession._headers  = parsed.headers;
  PipelineSession._renameMap = parsed._renameMap || {};

  // BNR/VID 필터: 정규화된 '유형' 컬럼 기준
  PipelineSession.validRows = parsed.rows.filter(r => {
    const t = (r['유형'] || '').toUpperCase().trim();
    return t === 'BNR' || t === 'VID';
  });

  // 정규화 정보를 UI에 표시 (컬럼명이 바뀐 경우 알림)
  const renamedCols = Object.entries(parsed._renameMap || {});

  // 미리보기 카드 표시
  const card = document.getElementById('parsePreviewCard');
  card.style.display = 'block';

  const stats = document.getElementById('parseStats');
  const txtCount = parsed.rows.filter(r=>(r['유형']||'').toUpperCase()==='TXT').length;
  stats.innerHTML = `
    <div class="pstat-item total"><span>${parsed.rows.length}</span>전체 행</div>
    <div class="pstat-item vidbnr"><span>${PipelineSession.validRows.length}</span>BNR+VID (분석 대상)</div>
    <div class="pstat-item txt"><span>${txtCount}</span>TXT (제외)</div>
    <div class="pstat-item cols"><span>${parsed.headers.length}</span>컬럼 수</div>
    <div class="pstat-file"><i class="fas fa-file-csv"></i> ${filename}</div>
    ${renamedCols.length ? `<div class="pstat-norm" style="grid-column:1/-1;font-size:11px;color:#6b7280;margin-top:4px;">
      <i class="fas fa-check-circle" style="color:#10b981"></i> 컬럼 자동 정규화:
      ${renamedCols.map(([o,n])=>`<code>${o}</code> → <code>${n}</code>`).join(', ')}
    </div>` : ''}`;

  // 테이블 미리보기 (상위 5행) – 핵심 컬럼 우선 표시
  const previewTable = document.getElementById('parsePreviewTable');
  const PRIORITY_COLS = ['소재명','유형','전환','비용','노출수','클릭수'];
  const priorityCols = PRIORITY_COLS.filter(c => parsed.headers.includes(c));
  const restCols = parsed.headers.filter(c => !PRIORITY_COLS.includes(c)).slice(0, 5 - priorityCols.length);
  const showCols = [...priorityCols, ...restCols].slice(0, 8);
  const previewRows = PipelineSession.validRows.slice(0, 5);
  previewTable.innerHTML = `
    <thead><tr>${showCols.map(h=>`<th>${h}</th>`).join('')}${parsed.headers.length > 8 ? `<th class="extra-col">+${parsed.headers.length-8}개 컬럼</th>` : ''}</tr></thead>
    <tbody>${previewRows.map(r =>
      `<tr>${showCols.map(c=>`<td title="${(r[c]||'')}">${(r[c]||'').slice(0,28)}${(r[c]||'').length>28?'…':''}</td>`).join('')}</tr>`
    ).join('')}</tbody>`;

  document.getElementById('btnToStage2').disabled = PipelineSession.validRows.length === 0;
  if (PipelineSession.validRows.length === 0) {
    alert(`BNR/VID 유형의 소재가 없습니다.\n\n[진단]\n- 현재 유형 컬럼명: "${parsed.headers.find(h=>h.includes('유형'))||'없음'}"\n- 파이프라인 내부 표준: "유형"\n- 자동 정규화 적용됨: ${JSON.stringify(parsed._renameMap)}`);
  }
}

// ══════════════════════════════════════════
// STAGE 2: 검증
// ══════════════════════════════════════════
function runValidation() {
  const result = plValidateData({ headers: PipelineSession._headers, rows: PipelineSession.rawRows });
  PipelineSession.validationResult = result;
  renderValidation(result);
}

function renderValidation(r) {
  // 컬럼 검증
  document.getElementById('colValidResult').innerHTML = `
    <div class="valid-status ${r.colResult.score}">
      <i class="fas fa-${r.colResult.score==='pass'?'check-circle':'times-circle'}"></i>
      ${r.colResult.score==='pass' ? '필수 컬럼 모두 확인됨' : `필수 컬럼 누락: ${r.colResult.missingRequired.join(', ')}`}
    </div>
    <div class="valid-detail">
      <strong>필수:</strong> ${REQUIRED_COLS.map(c => `<span class="mini-badge ${r.colResult.missingRequired.includes(c)?'fail':'ok'}">${c}</span>`).join('')}
    </div>
    <div class="valid-detail" style="margin-top:8px;">
      <strong>태그 컬럼 (자동 탐지):</strong>
      ${(r.colResult.tagCols||[]).length
        ? r.colResult.tagCols.map(c=>`<span class="mini-badge opt">${c}</span>`).join('')
        : '<span style="color:var(--text-muted)">없음</span>'}
    </div>
    ${(r.colResult.insightCols||[]).length ? `
    <div class="valid-detail" style="margin-top:6px;">
      <strong><i class="fas fa-lightbulb" style="color:#f59e0b"></i> 마케터 인사이트 컬럼:</strong>
      ${r.colResult.insightCols.map(c=>`<span class="mini-badge mi-badge">${c}</span>`).join('')}
      <span class="mini-badge-note">키워드 자동 추출 후 [MI] 태그로 군집화에 반영</span>
    </div>` : ''}`;

  // 데이터 품질
  const d = r.dataResult;
  document.getElementById('dataValidResult').innerHTML = `
    <div class="valid-status ${d.score}">
      <i class="fas fa-${d.score==='pass'?'check-circle':'exclamation-triangle'}"></i>
      ${d.score==='pass'?'데이터 품질 이상 없음':'이상 항목 있음 – 확인 권장'}
    </div>
    <div class="data-count-row">
      <span>전체 ${d.total}행</span>
      <span class="ok-t">BNR+VID ${d.vidBnr}건</span>
      <span class="muted-t">TXT 제외 ${d.txt}건</span>
    </div>
    ${d.issues.map(iss => `
      <div class="issue-item ${iss.type}">
        <i class="fas fa-${iss.type==='error'?'times-circle':iss.type==='warn'?'exclamation-triangle':'info-circle'}"></i>
        ${iss.msg}
      </div>`).join('')}`;

  // 태그 품질
  const t = r.tagResult;
  const totalTagSrc = (t.availTagCols||[]).length + (t.insightCols||[]).length;
  document.getElementById('tagValidResult').innerHTML = `
    <div class="valid-status ${t.score}">
      <i class="fas fa-${t.score==='pass'?'check-circle':'exclamation-triangle'}"></i>
      ${t.score==='pass'?'태그 품질 양호':'태그 누락 소재 다수 – 군집화 정확도 영향'}
    </div>
    <div class="data-count-row">
      <span>평균 태그 수: <strong>${t.avgTagCount}개</strong></span>
      <span class="${t.noTag>0?'warn-t':'ok-t'}">태그 없음: ${t.noTag}건</span>
      <span style="color:var(--primary);font-weight:600;">태그 소스: ${totalTagSrc}개 컬럼</span>
    </div>
    <div class="tag-source-grid">
      <div class="tag-source-block">
        <div class="tsb-label"><i class="fas fa-tags"></i> 태그 컬럼 (${(t.availTagCols||[]).length}개)</div>
        <div class="tsb-pills">
          ${(t.availTagCols||[]).length
            ? t.availTagCols.map(c=>`<span class="mini-badge opt">${c}</span>`).join('')
            : '<span style="color:var(--text-muted);font-size:11px;">탐지된 컬럼 없음</span>'}
        </div>
      </div>
      ${(t.insightCols||[]).length ? `
      <div class="tag-source-block mi-block">
        <div class="tsb-label"><i class="fas fa-lightbulb" style="color:#f59e0b"></i> 마케터 인사이트 컬럼 (${t.insightCols.length}개)</div>
        <div class="tsb-pills">
          ${t.insightCols.map(c=>`<span class="mini-badge mi-badge">${c}</span>`).join('')}
        </div>
        <div class="tsb-note">문장에서 핵심 키워드를 추출해 [MI] 태그로 군집화에 반영합니다.</div>
      </div>` : `
      <div class="tag-source-block" style="opacity:.55">
        <div class="tsb-label"><i class="fas fa-lightbulb"></i> 마케터 인사이트 컬럼</div>
        <div class="tsb-note">탐지되지 않음 · <code>marketer_insight</code> 컬럼 추가 시 활성화</div>
      </div>`}
    </div>`;

  // 요약
  document.getElementById('validSummary').innerHTML = `
    <div class="summary-score-row">
      <div class="sum-score-item ${r.colResult.score}"><i class="fas fa-columns"></i> 컬럼 검증: ${r.colResult.score==='pass'?'통과':'실패'}</div>
      <div class="sum-score-item ${d.score}"><i class="fas fa-database"></i> 데이터 품질: ${d.score==='pass'?'통과':'주의'}</div>
      <div class="sum-score-item ${t.score}"><i class="fas fa-tags"></i> 태그 품질: ${t.score==='pass'?'양호':'주의'}</div>
    </div>
    <p style="margin-top:12px; font-size:13px; color:var(--text-secondary);">
      분석 대상 소재 <strong>${d.vidBnr}개</strong>로 군집화 진행합니다.
      ${d.issues.filter(i=>i.type==='error').length ? ' <span style="color:var(--danger)">⚠️ 오류 항목이 있습니다. 업로드로 돌아가 수정을 권장합니다.</span>' : ''}
    </p>`;

  document.getElementById('btnBackTo1').onclick = () => goToStage(1);
  document.getElementById('btnToStage3').onclick = () => { initStage3(); goToStage(3); };
}

// ══════════════════════════════════════════
// STAGE 3: 군집화
// ══════════════════════════════════════════
let _stage3Initialized = false;

function initStage3() {
  // 슬라이더·버튼 이벤트 중복 등록 방지
  if (_stage3Initialized) return;
  _stage3Initialized = true;

  // 파라미터 슬라이더 바인딩
  const sliders = [
    { id:'wConv', valId:'wConvVal', suffix:'%' },
    { id:'wCpa',  valId:'wCpaVal',  suffix:'%' },
    { id:'wIpm',  valId:'wIpmVal',  suffix:'%' },
    { id:'minCluster', valId:'minClusterVal', suffix:'' },
    { id:'minSupport', valId:'minSupportVal', suffix:'%' },
    { id:'coOccur', valId:'coOccurVal', suffix:'개' },
  ];
  sliders.forEach(({ id, valId, suffix }) => {
    const sl = document.getElementById(id);
    const vl = document.getElementById(valId);
    if (!sl || !vl) return;
    sl.oninput = () => { vl.textContent = sl.value + suffix; checkWeightSum(); };
  });

  // ── 최소 군집 수 보장 옵션 바인딩
  initMinClustersControl();

  document.getElementById('btnBackTo2').onclick = () => goToStage(2);
  document.getElementById('btnRunClustering').onclick = runClustering;
}

// 최소 군집 수 컨트롤 초기화
function initMinClustersControl() {
  const toggle   = document.getElementById('useMinClusters');
  const control  = document.getElementById('minClustersControl');
  const slider   = document.getElementById('minClustersSlider');
  const numInput = document.getElementById('minClustersInput');
  const display  = document.getElementById('minClustersDisplay');
  const btnMinus = document.getElementById('btnMinClusMinus');
  const btnPlus  = document.getElementById('btnMinClusPlus');

  if (!toggle) return;

  // 토글 ON/OFF
  toggle.onchange = () => {
    control.style.display = toggle.checked ? 'block' : 'none';
  };

  // 슬라이더 ↔ 숫자 입력 동기화
  const syncValue = (val) => {
    const v = Math.min(10, Math.max(2, parseInt(val, 10) || 3));
    slider.value   = v;
    numInput.value = v;
    if (display) display.textContent = v;
  };

  slider.oninput   = () => syncValue(slider.value);
  numInput.oninput = () => syncValue(numInput.value);
  numInput.onblur  = () => syncValue(numInput.value);

  // +/- 스텝 버튼
  btnMinus.onclick = () => syncValue(+numInput.value - 1);
  btnPlus.onclick  = () => syncValue(+numInput.value + 1);
}

function checkWeightSum() {
  const w = +document.getElementById('wConv').value
          + +document.getElementById('wCpa').value
          + +document.getElementById('wIpm').value;
  document.getElementById('weightWarning').style.display = w > 100 ? 'flex' : 'none';
}

async function runClustering() {
  const btnNext = document.getElementById('btnToStage4');
  const btnRun  = document.getElementById('btnRunClustering');
  const progress = document.getElementById('clusterProgress');
  const fill     = document.getElementById('progressFill');
  const label    = document.getElementById('progressLabel');

  // 파라미터 수집
  const useMinClusters = document.getElementById('useMinClusters')?.checked || false;
  const minClusters    = useMinClusters
    ? (parseInt(document.getElementById('minClustersInput')?.value, 10) || 3)
    : null;

  PipelineSession.params = {
    wConv:       +document.getElementById('wConv').value,
    wCpa:        +document.getElementById('wCpa').value,
    wIpm:        +document.getElementById('wIpm').value,
    minCluster:  +document.getElementById('minCluster').value,
    minSupport:  +document.getElementById('minSupport').value,
    coOccur:     +document.getElementById('coOccur').value,
    useMinClusters,
    minClusters,
  };

  // 프로그레스 표시
  progress.style.display = 'block';
  btnRun.disabled = true;
  btnNext.disabled = true;

  const steps = [
    [15, 'Total Score 산출 중…'],
    [35, '태그 빈도 분석 중…'],
    [55, '동시출현 행렬 계산 중…'],
    [75, '군집 최적화 중…'],
    [90, '성과 지표 매핑 중…'],
    [100,'분석 완료!'],
  ];

  for (const [pct, msg] of steps) {
    await new Promise(r => setTimeout(r, 280));
    fill.style.width = pct + '%';
    label.textContent = msg;
  }

  try {
    // 실제 분석
    const prevInsights = plGetAccumulatedInsights();
    const creatives = plCalcScores(
      PipelineSession.validRows, PipelineSession.params, PipelineSession._headers
    );
    const clusters   = plRunClusteringWithMinGuarantee(creatives, PipelineSession.params, prevInsights);
    const tagImpacts = plCalcTagImpact(creatives);

    PipelineSession.creatives  = creatives;
    PipelineSession.clusters   = clusters;
    PipelineSession.tagImpacts = tagImpacts;

    await new Promise(r => setTimeout(r, 300));

    // 재시도 발생 여부 안내 메시지
    const retryCount  = clusters._retryCount  || 0;
    const finalParams = clusters._finalParams  || PipelineSession.params;
    const realCount   = clusters.filter(cl => cl.name !== '기타 / 단독 소재').length;
    let retryMsg = '';
    if (retryCount > 0) {
      const coBoostVal    = ((finalParams._coBoost    || 0) * 5).toFixed(0);
      const noiseTightVal = ((finalParams._noiseTighten || 0) * 100).toFixed(0);
      const mcVal         = finalParams.minCluster;
      const parts = [];
      if (coBoostVal > 0)    parts.push(`분리 임계값 +${coBoostVal}%`);
      if (noiseTightVal > 0) parts.push(`노이즈 필터 +${noiseTightVal}%`);
      if (mcVal < PipelineSession.params.minCluster) parts.push(`최소 소재 수 → ${mcVal}개`);
      retryMsg = `<span class="run-retry-badge">
        <i class="fas fa-sync-alt"></i> ${retryCount}회 자동 조정 · ${parts.join(' · ')}
      </span>`;
    }

    document.getElementById('runInfo').innerHTML =
      `<i class="fas fa-check-circle" style="color:var(--success)"></i> 분석 완료 · 유효 군집 ${realCount}개 (전체 ${clusters.length}개), 소재 ${creatives.length}개 ${retryMsg}`;

    try {
      renderClusterResults(clusters, creatives, tagImpacts);
    } catch (renderErr) {
      console.warn('renderClusterResults 오류 (결과 표시 실패):', renderErr);
    }

    // disabled 속성 완전 제거 (CSS :disabled pseudo-class 해제)
    btnNext.removeAttribute('disabled');
    btnNext.style.removeProperty('opacity');
    btnNext.style.removeProperty('cursor');
    btnNext.classList.remove('disabled');

  } catch (err) {
    console.error('군집화 분석 오류:', err);
    document.getElementById('runInfo').innerHTML =
      `<i class="fas fa-exclamation-circle" style="color:var(--danger)"></i> 분석 중 오류가 발생했습니다: ${err.message}`;
  } finally {
    progress.style.display = 'none';
    btnRun.disabled = false;
  }
}

function renderClusterResults(clusters, creatives, tagImpacts) {
  document.getElementById('clusterResultArea').style.display = 'block';

  // 군집 카드
  const colors = ['#5c6ef8','#ff7043','#26c281','#ffd234','#29b6f6','#ab47bc','#78909c'];
  document.getElementById('clusterResultGrid').innerHTML = clusters.map((cl, i) => {
    const color = cl.name === '기타 / 단독 소재' ? '#9e9e9e' : colors[i % colors.length];
    const isNewBadge = cl.isNew ? '<span class="new-cluster-badge">NEW</span>' : '';
    const prevBadge  = !cl.isNew && cl.prevRef
      ? `<span class="prev-cluster-badge">← ${cl.prevRef}</span>` : '';
    const top3 = (cl.creatives || []).slice().sort((a,b)=>b.score-a.score).slice(0,3);

    return `
    <div class="cluster-result-card" style="border-top: 4px solid ${color}">
      <div class="crc-header">
        <div class="crc-name">${cl.name} ${isNewBadge} ${prevBadge}</div>
        <div class="crc-meta">
          <span>${cl.creativeCount}개 소재</span>
          <span>VID ${cl.vidCount} / BNR ${cl.bnrCount}</span>
          <span class="crc-score" style="color:${color}">평균 ${cl.avgScore}점</span>
        </div>
      </div>
      <div class="crc-desc">${cl.description}</div>
      <div class="crc-tags">${cl.topTags.slice(0,6).map(t=>`<span class="tag-pill-sm">${t}</span>`).join('')}</div>
      ${(cl.topMITags||[]).length ? `
      <div class="crc-mi-tags">
        <span class="crc-mi-label"><i class="fas fa-lightbulb"></i> 인사이트</span>
        ${cl.topMITags.slice(0,4).map(t=>`<span class="tag-pill-sm mi-pill">${t.replace('[MI] ','')}</span>`).join('')}
      </div>` : ''}
      <div class="crc-top3">
        <div class="crc-top3-label">🏆 TOP 3 소재</div>
        ${top3.map(c=>`
          <div class="crc-top3-item">
            <span class="crc-top3-rank">#${c.rank||creatives.indexOf(c)+1}</span>
            <span class="crc-top3-name">${c.name}</span>
            <span class="crc-top3-score" style="color:${color}">${c.score}점</span>
            <span class="grade-pill grade-${c.grade}">${c.grade}</span>
          </div>`).join('')}
      </div>
    </div>`;
  }).join('');

  // 군집별 성과 차트
  if (clusterCompareChartInst) clusterCompareChartInst.destroy();
  const ctx = document.getElementById('clusterCompareChart');
  if (ctx) {
    clusterCompareChartInst = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: clusters.map(c => c.name),
        datasets: [
          { label: '평균 Score', data: clusters.map(c=>c.avgScore),
            backgroundColor: clusters.map((_,i)=>`${colors[i%colors.length]}cc`), borderRadius: 6 },
          { label: '소재 수',   data: clusters.map(c=>c.creativeCount),
            backgroundColor: 'rgba(150,150,150,0.3)', borderRadius: 6, yAxisID: 'y2' }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'top', labels: { font:{size:12} } } },
        scales: {
          y:  { grid:{color:'#f0f2f5'}, title:{display:true,text:'평균 Score'} },
          y2: { position:'right', grid:{display:false}, title:{display:true,text:'소재 수'} },
          x:  { grid:{display:false}, ticks:{font:{size:11}} }
        }
      }
    });
  }

  // 소재별 Score 매핑 테이블
  const sorted = [...creatives].sort((a,b)=>b.score-a.score);
  // MI 태그를 가진 소재가 있으면 인사이트 컬럼 추가
  const hasAnyMI = sorted.some(c => (c.tagSources?.fromInsight||[]).length > 0);
  const cols = ['이름','유형','Score','등급','군집','주요 태그', ...(hasAnyMI ? ['인사이트 태그'] : [])];
  document.getElementById('scoreMappingTable').innerHTML = `
    <thead><tr>${cols.map(c=>`<th>${c}</th>`).join('')}</tr></thead>
    <tbody>${sorted.map((c,i) => {
      const normalTags = (c.tags||[]).filter(t => !t.startsWith('[MI]'));
      const miTags     = (c.tagSources?.fromInsight)||[];
      return `
      <tr>
        <td><strong>#${i+1} ${c.name}</strong></td>
        <td><span class="type-badge-sm ${c.type.toLowerCase()}">${c.type}</span></td>
        <td><strong style="color:${c.score>=60?'#5c6ef8':c.score>=40?'#26c281':c.score>=20?'#f9a825':'#f44336'}">${c.score}</strong></td>
        <td><span class="grade-pill grade-${c.grade}">${c.grade}</span></td>
        <td>${c.cluster}</td>
        <td style="max-width:220px;">${normalTags.slice(0,4).map(t=>`<span class="tag-pill-sm">${t}</span>`).join('')}${normalTags.length>4?`<span class="tag-pill-sm muted">+${normalTags.length-4}</span>`:''}</td>
        ${hasAnyMI ? `<td style="max-width:200px;">${miTags.slice(0,3).map(t=>`<span class="tag-pill-sm mi-pill">${t.replace('[MI] ','')}</span>`).join('')}${!miTags.length?'<span style="color:var(--text-muted);font-size:11px;">-</span>':''}</td>` : ''}
      </tr>`;
    }).join('')}
    </tbody>`;
}

// ══════════════════════════════════════════
// STAGE 4: 인사이트 확정
// ══════════════════════════════════════════
function renderStage4() {
  const { clusters, creatives, tagImpacts, roundName } = PipelineSession;
  const safeImpacts = (tagImpacts && tagImpacts.impacts) ? tagImpacts.impacts : [];
  const avgScore = creatives.length
    ? +(creatives.reduce((s,c)=>s+c.score,0)/creatives.length).toFixed(1) : 0;
  const topCreative = creatives.length ? creatives.reduce((a,b)=>a.score>b.score?a:b, creatives[0]) : {};
  const winTags  = safeImpacts.filter(t=>t.impact>0).slice(0,6);
  const loseTags = safeImpacts.filter(t=>t.impact<0).slice(-5).reverse();

  document.getElementById('finalSummaryContent').innerHTML = `
    <div class="final-kpi-row">
      <div class="final-kpi"><div class="fk-val">${creatives.length}</div><div class="fk-label">분석 소재 수</div></div>
      <div class="final-kpi"><div class="fk-val">${clusters.length}</div><div class="fk-label">생성 군집 수</div></div>
      <div class="final-kpi"><div class="fk-val">${avgScore}</div><div class="fk-label">평균 Total Score</div></div>
      <div class="final-kpi primary"><div class="fk-val">${topCreative.score||0}</div><div class="fk-label">최고 Score</div></div>
      <div class="final-kpi success"><div class="fk-val">${creatives.filter(c=>c.grade==='최우수').length}</div><div class="fk-label">최우수 소재</div></div>
    </div>
    <div class="two-col-sm" style="margin-top:16px;">
      <div>
        <div class="final-label"><i class="fas fa-crown" style="color:var(--warning)"></i> 최고 소재</div>
        <strong>${topCreative.name||'-'}</strong> · ${topCreative.score||0}점 · ${topCreative.cluster||''}
      </div>
      <div>
        <div class="final-label"><i class="fas fa-trophy" style="color:var(--success)"></i> 1위 군집</div>
        <strong>${clusters[0]?.name||'-'}</strong> · 평균 ${clusters[0]?.avgScore||0}점
      </div>
    </div>
    <div style="margin-top:16px;">
      <div class="final-label">✅ 승리 태그: ${winTags.map(t=>`<span class="tag-pill-sm win">${t.tag}(+${t.impact})</span>`).join('')}</div>
      <div class="final-label" style="margin-top:6px;">⛔ 패배 태그: ${loseTags.map(t=>`<span class="tag-pill-sm lose">${t.tag}(${t.impact})</span>`).join('')}</div>
    </div>`;

  // 승리 공식 / 중단 패턴 이전 차수 값 불러오기
  const prevInsights = plGetAccumulatedInsights();
  if (prevInsights?.winningFormula) {
    document.getElementById('winningFormula').innerHTML =
      `<div class="prev-formula"><i class="fas fa-history"></i> 이전 차수: ${prevInsights.winningFormula}</div>`;
    document.getElementById('winningFormulaInput').placeholder = prevInsights.winningFormula;
  }
  if (prevInsights?.exitPattern) {
    document.getElementById('exitPattern').innerHTML =
      `<div class="prev-formula exit"><i class="fas fa-history"></i> 이전 차수: ${prevInsights.exitPattern}</div>`;
    document.getElementById('exitPatternInput').placeholder = prevInsights.exitPattern;
  }

  // 차수 히스토리
  renderRoundHistory();

  // 버튼 (onclick으로 덮어쓰기 → 중복 바인딩 방지)
  document.getElementById('btnBackTo3').onclick = () => goToStage(3);
  document.getElementById('btnSaveFormula').onclick = () => {
    PipelineSession.winningFormula = document.getElementById('winningFormulaInput').value.trim()
      || document.getElementById('winningFormulaInput').placeholder;
    document.getElementById('btnSaveFormula').innerHTML = '<i class="fas fa-check"></i> 저장됨';
    setTimeout(() => { document.getElementById('btnSaveFormula').innerHTML = '<i class="fas fa-save"></i> 저장'; }, 1500);
  };
  document.getElementById('btnSaveExit').onclick = () => {
    PipelineSession.exitPattern = document.getElementById('exitPatternInput').value.trim()
      || document.getElementById('exitPatternInput').placeholder;
    document.getElementById('btnSaveExit').innerHTML = '<i class="fas fa-check"></i> 저장됨';
    setTimeout(() => { document.getElementById('btnSaveExit').innerHTML = '<i class="fas fa-save"></i> 저장'; }, 1500);
  };
  document.getElementById('btnSaveRound').onclick = saveRound;
}

function renderRoundHistory() {
  const rounds = plLoadRounds();
  const el = document.getElementById('roundHistoryList');
  if (!rounds.length) {
    el.innerHTML = '<p style="color:var(--text-muted);font-size:13px;">저장된 차수가 없습니다.</p>';
    return;
  }
  el.innerHTML = `
    <div class="history-table-wrap">
      <table class="mini-table">
        <thead><tr><th>#</th><th>차수명</th><th>날짜</th><th>소재</th><th>군집</th><th>평균 Score</th><th>업로더</th><th>메모</th></tr></thead>
        <tbody>${rounds.map((r,i)=>`
          <tr>
            <td><strong>${i+1}</strong></td>
            <td>${r.name}</td>
            <td>${new Date(r.createdAt).toLocaleDateString('ko-KR')}</td>
            <td>${r.validCount}</td>
            <td>${r.clusters?.length||0}</td>
            <td><strong>${r.avgScore||0}</strong></td>
            <td>${r.uploader||'-'}</td>
            <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;">${r.memo||''}</td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>`;
}

function saveRound() {
  const { creatives, clusters, tagImpacts, roundName, uploader, memo, params,
          winningFormula, exitPattern, insightMemos } = PipelineSession;

  const safeImpacts = (tagImpacts && tagImpacts.impacts) ? tagImpacts.impacts : [];
  const avgScore = creatives.length
    ? +(creatives.reduce((s,c)=>s+c.score,0)/creatives.length).toFixed(1) : 0;
  const topScore = creatives.length ? Math.max(...creatives.map(c=>c.score)) : 0;

  const round = {
    id: String(Date.now()),
    name: roundName || `차수_${Date.now()}`,
    uploader, memo,
    createdAt: Date.now(),
    rawCount: PipelineSession.rawRows.length,
    validCount: creatives.length,
    params,
    creatives: creatives.map(c => ({
      name:c.name, type:c.type, conversions:c.conversions, cost:c.cost,
      impressions:c.impressions, score:c.score, grade:c.grade, cluster:c.cluster,
      tags: c.tags, ipm:c.ipm, cpa:c.cpa
    })),
    clusters: clusters.map(cl => ({
      id:cl.id, name:cl.name, topTags:cl.topTags, avgScore:cl.avgScore,
      creativeCount:cl.creativeCount, vidCount:cl.vidCount, bnrCount:cl.bnrCount,
      description:cl.description
    })),
    winningTags:  safeImpacts.filter(t=>t.impact>0).slice(0,15),
    losingTags:   safeImpacts.filter(t=>t.impact<0).slice(-10),
    winningFormula: winningFormula || document.getElementById('winningFormulaInput').value.trim(),
    exitPattern:    exitPattern    || document.getElementById('exitPatternInput').value.trim(),
    insightMemos: insightMemos || [],
    avgScore, topScore
  };

  const rounds = plLoadRounds();
  rounds.push(round);
  plSaveRounds(rounds);
  plClearCurrent();

  // 인사이트 히스토리 누적
  const insights = plLoadInsights();
  insights.push({ roundId: round.id, roundName: round.name, createdAt: round.createdAt,
    winningTags: round.winningTags, losingTags: round.losingTags,
    winningFormula: round.winningFormula, exitPattern: round.exitPattern,
    insightMemos: round.insightMemos });
  plSaveInsights(insights);

  renderRoundHistory();
  updateHeaderBadge();

  // 저장 성공 배너 표시 (alert 대신)
  const banner = document.getElementById('saveSuccessBanner');
  if (banner) {
    banner.style.display = 'flex';
    banner.scrollIntoView({ behavior: 'smooth', block: 'center' });
  } else {
    alert(`✅ "${round.name}" 분석 결과가 저장되었습니다.\n다음 차수 분석 시 이번 차수의 인사이트가 자동 반영됩니다.`);
  }
}

// ══════════════════════════════════════════
// 공통 유틸
// ══════════════════════════════════════════
function updateHeaderBadge() {
  const rounds = plLoadRounds();
  const badge  = document.getElementById('currentRoundBadge');
  const footer = document.getElementById('footerRound');
  if (rounds.length) {
    const latest = rounds[rounds.length-1];
    badge.textContent  = `최신 차수: ${latest.name} (${rounds.length}차)`;
    if (footer) footer.textContent = `최근 저장: ${new Date(latest.createdAt).toLocaleDateString('ko-KR')}`;
  } else {
    badge.textContent = '저장된 차수 없음';
  }
}

// ══════════════════════════════════════════
// 앱 초기화
// ══════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
  initStage1();
  updateHeaderBadge();

  // Stage 4 진입 버튼 (군집화 완료 후 활성화됨)
  document.getElementById('btnToStage4').onclick = () => { renderStage4(); goToStage(4); };
});
