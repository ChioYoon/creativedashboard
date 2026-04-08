/**
 * ========================================
 * Pepp Heroes 소재 분석 엔진 v2.0
 * ========================================
 * 
 * Step 1: 데이터 통합 및 스코어링
 * - 일자별 로데이터 → 소재별 기간 합계
 * - 기간 필터링 지원 (시작일~종료일)
 * - 전환/CPA/IPM Rank 점수 산출
 * - Total Score 계산
 */

// ══════════════════════════════════════════
// 날짜 유틸리티
// ══════════════════════════════════════════

/**
 * CSV에서 날짜 컬럼 자동 감지
 */
function detectDateColumn(headers) {
  const datePatterns = [
    /^일$/,
    /^날짜$/,
    /^일자$/,
    /^date$/i,
    /^day$/i,
    /투입일/,
    /집행일/,
    /^시기$/
  ];
  
  for (const header of headers) {
    if (datePatterns.some(pattern => pattern.test(header))) {
      return header;
    }
  }
  
  return null;
}

/**
 * 날짜 문자열을 Date 객체로 변환
 * 지원 형식: YYYY-MM-DD, YYYY.MM.DD, YYYY/MM/DD, YYYYMMDD
 */
function parseDate(dateStr) {
  if (!dateStr) return null;
  
  const str = String(dateStr).trim();
  
  // YYYY-MM-DD, YYYY.MM.DD, YYYY/MM/DD
  if (/^\d{4}[-./]\d{1,2}[-./]\d{1,2}$/.test(str)) {
    return new Date(str.replace(/[./]/g, '-'));
  }
  
  // YYYYMMDD
  if (/^\d{8}$/.test(str)) {
    const y = str.substring(0, 4);
    const m = str.substring(4, 6);
    const d = str.substring(6, 8);
    return new Date(`${y}-${m}-${d}`);
  }
  
  return null;
}

/**
 * Date 객체를 YYYY-MM-DD 형식으로 변환
 */
function formatDate(date) {
  if (!date || !(date instanceof Date)) return '';
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

// ══════════════════════════════════════════
// Step 1-0: 기간 필터링
// ══════════════════════════════════════════

/**
 * 날짜 범위로 로데이터 필터링
 * 
 * @param {Array} rows - 전체 로데이터 행
 * @param {String} dateColumn - 날짜 컬럼명
 * @param {String} startDate - 시작일 (YYYY-MM-DD, 선택)
 * @param {String} endDate - 종료일 (YYYY-MM-DD, 선택)
 * @returns {Array} 필터링된 행
 */
function filterByDateRange(rows, dateColumn, startDate, endDate) {
  if (!dateColumn) {
    console.log('⚠️ 날짜 컬럼이 지정되지 않아 전체 데이터 사용');
    return rows;
  }

  const start = startDate ? new Date(startDate) : null;
  const end = endDate ? new Date(endDate) : null;

  const filtered = rows.filter(row => {
    const dateStr = row[dateColumn];
    const date = parseDate(dateStr);
    
    if (!date) return false; // 날짜 파싱 실패 시 제외
    
    if (start && date < start) return false;
    if (end && date > end) return false;
    
    return true;
  });

  console.log(`📅 기간 필터링: ${rows.length}개 행 → ${filtered.length}개 행`);
  if (start || end) {
    console.log(`   범위: ${start ? formatDate(start) : '처음'} ~ ${end ? formatDate(end) : '끝'}`);
  }

  return filtered;
}

/**
 * 데이터셋에서 날짜 범위 추출 (최소/최대 날짜)
 */
function getDateRange(rows, dateColumn) {
  if (!dateColumn) return { min: null, max: null };

  let min = null;
  let max = null;

  rows.forEach(row => {
    const date = parseDate(row[dateColumn]);
    if (!date) return;
    
    if (!min || date < min) min = date;
    if (!max || date > max) max = date;
  });

  return {
    min: min ? formatDate(min) : null,
    max: max ? formatDate(max) : null
  };
}

// ══════════════════════════════════════════
// Step 1-1: 소재별 데이터 집계 (기간 합계)
// ══════════════════════════════════════════

/**
 * CSV 로데이터를 소재별로 집계
 * 
 * 입력: 일자별 행 데이터 (소재명이 중복될 수 있음)
 * 출력: 소재별 합계 데이터 (소재명당 1개 행)
 * 
 * @param {Array} rows - 전체 행 데이터
 * @param {String} groupBy - 집계 기준 컬럼 ('소재명' 또는 '파일명', 기본값: '소재명')
 * 
 * 집계 지표:
 * - 전환: 합계
 * - 비용: 합계
 * - 노출수: 합계
 * - 클릭수: 합계
 * - CPA: 총비용 / 총전환
 * - IPM: (총전환 / 총노출수) * 1000
 * - 태그: 첫 번째 행의 태그 유지 (소재당 태그는 동일하다고 가정)
 */
function aggregateCreativeData(rows, groupBy = '소재명') {
  const creativeMap = new Map();

  // groupBy 컬럼 검증
  const sampleRow = rows.find(r => ['BNR', 'VID'].includes((r['유형'] || '').toUpperCase()));
  
  if (sampleRow && !sampleRow[groupBy]) {
    console.warn(`⚠️ 지정된 집계 기준 "${groupBy}" 컬럼을 찾을 수 없습니다.`);
    console.warn(`   사용 가능한 컬럼:`, Object.keys(sampleRow).slice(0, 10).join(', '));
    console.warn(`   '소재명'으로 대체합니다.`);
    groupBy = '소재명';
  }

  // TXT 유형 제외 (BNR/VID만 분석)
  const bnrVidRows = rows.filter(r => ['BNR', 'VID'].includes((r['유형'] || '').toUpperCase()));
  
  console.log(`📊 집계 대상 필터링: 전체 ${rows.length}개 행 → BNR/VID ${bnrVidRows.length}개 행`);

  bnrVidRows.forEach(row => {
    const key = row[groupBy];
    if (!key || !key.trim()) {
      console.warn(`⚠️ 집계 기준 "${groupBy}" 값이 비어있는 행 발견:`, row);
      return;
    }

    const conv = parseFloat(row['전환']) || 0;
    const cost = parseFloat(row['비용']) || 0;
    const impr = parseFloat(row['노출수']) || 0;
    const click = parseFloat(row['클릭수']) || 0;

    if (!creativeMap.has(key)) {
      // 첫 번째 행: 소재 초기화
      creativeMap.set(key, {
        소재명: row['소재명'] || '',       // 원본 소재명 보존
        파일명: row['파일명'] || '',       // 원본 파일명 보존
        집계기준: key,                     // 실제 집계에 사용된 값
        유형: row['유형'] || '',
        전환: conv,
        비용: cost,
        노출수: impr,
        클릭수: click,
        // 태그 및 메타 데이터는 첫 행 기준
        tags: {},        // 태그 컬럼들
        insights: {},    // 인사이트 컬럼들
        meta: {}         // 기타 메타 데이터
      });
      
      // 태그 컬럼 추출 (첫 행 기준)
      Object.keys(row).forEach(colKey => {
        const val = row[colKey];
        if (!val || val.trim() === '') return;
        
        // 필수 컬럼 제외
        if (['소재명', '파일명', '유형', '전환', '비용', '노출수', '클릭수'].includes(colKey)) return;
        
        // 메타 컬럼 패턴 (날짜, 캠페인, 링크 등)
        if (/^(일|날짜|캠페인|광고그룹|링크|통화|orientation)/.test(colKey)) {
          creativeMap.get(key).meta[colKey] = val;
        }
        // 인사이트 컬럼
        else if (/insight|인사이트|memo|메모/i.test(colKey)) {
          creativeMap.get(key).insights[colKey] = val;
        }
        // 태그 컬럼
        else {
          creativeMap.get(key).tags[colKey] = val;
        }
      });
    } else {
      // 기존 소재: 수치 합산
      const creative = creativeMap.get(key);
      creative.전환 += conv;
      creative.비용 += cost;
      creative.노출수 += impr;
      creative.클릭수 += click;
    }
  });

  // Map → Array 변환 및 파생 지표 계산
  const aggregated = Array.from(creativeMap.values()).map(c => {
    c.CPA = c.전환 > 0 ? c.비용 / c.전환 : 0;
    c.IPM = c.노출수 > 0 ? (c.전환 / c.노출수) * 1000 : 0;
    c.CTR = c.노출수 > 0 ? (c.클릭수 / c.노출수) * 100 : 0;
    return c;
  });

  console.log(`✅ 소재 집계 완료 (기준: ${groupBy}): ${bnrVidRows.length}개 행 → ${aggregated.length}개 소재`);
  
  // 샘플 출력 (디버깅용)
  if (aggregated.length > 0) {
    const sample = aggregated[0];
    console.log(`   샘플 소재:`, {
      집계기준: sample.집계기준,
      소재명: sample.소재명?.substring(0, 30) + '...',
      파일명: sample.파일명?.substring(0, 30) + '...',
      전환: sample.전환,
      유형: sample.유형
    });
  }
  
  return aggregated;
}

// ══════════════════════════════════════════
// Step 1-2: Rank 점수 산출 (Percentile Ranking)
// ══════════════════════════════════════════

/**
 * 전환/CPA/IPM 각 지표의 Rank 점수 산출
 * 
 * 로직:
 * - 전환: 많을수록 높은 점수 (오름차순 순위)
 * - CPA: 낮을수록 높은 점수 (내림차순 순위)
 * - IPM: 높을수록 높은 점수 (오름차순 순위)
 * 
 * Rank 점수 = (순위 / 전체 개수) * 100
 * → 0~100점 범위, 100점이 최고
 */
function calculateRankScores(creatives) {
  const n = creatives.length;
  if (n === 0) return [];

  // 1. 전환 Rank: 전환 많을수록 높은 순위
  const sortedByConv = [...creatives].sort((a, b) => a.전환 - b.전환);
  sortedByConv.forEach((c, idx) => {
    c.전환Rank = ((idx + 1) / n) * 100;
  });

  // 2. CPA Rank: CPA 낮을수록 높은 순위
  // CPA=0인 경우 (전환=0) 최하위 처리
  const sortedByCPA = [...creatives].sort((a, b) => {
    if (a.CPA === 0 && b.CPA === 0) return 0;
    if (a.CPA === 0) return 1;  // a가 최하위
    if (b.CPA === 0) return -1; // b가 최하위
    return b.CPA - a.CPA; // 높은 CPA가 낮은 순위
  });
  sortedByCPA.forEach((c, idx) => {
    c.CPARank = c.CPA === 0 ? 0 : ((idx + 1) / n) * 100;
  });

  // 3. IPM Rank: IPM 높을수록 높은 순위
  const sortedByIPM = [...creatives].sort((a, b) => a.IPM - b.IPM);
  sortedByIPM.forEach((c, idx) => {
    c.IPMRank = ((idx + 1) / n) * 100;
  });

  console.log(`✅ Rank 점수 산출 완료: 전환/CPA/IPM`);
  return creatives;
}

// ══════════════════════════════════════════
// Step 1-3: Total Score 산출
// ══════════════════════════════════════════

/**
 * Total Score = 전환Rank × 40% + CPARank × 35% + IPMRank × 25%
 * 
 * 가중치:
 * - 전환 40%: 볼륨 중시
 * - CPA 35%: 효율 중시
 * - IPM 25%: 전환률 중시
 */
function calculateTotalScore(creatives, weights = { conv: 0.40, cpa: 0.35, ipm: 0.25 }) {
  creatives.forEach(c => {
    c.TotalScore = (
      c.전환Rank * weights.conv +
      c.CPARank * weights.cpa +
      c.IPMRank * weights.ipm
    );
    c.TotalScore = Math.round(c.TotalScore * 10) / 10; // 소수점 1자리
  });

  // Total Score 기준 내림차순 정렬
  creatives.sort((a, b) => b.TotalScore - a.TotalScore);

  // 순위 부여
  creatives.forEach((c, idx) => {
    c.Rank = idx + 1;
  });

  // 성과 등급 부여 (4분위)
  const q1 = Math.ceil(creatives.length * 0.25);
  const q2 = Math.ceil(creatives.length * 0.50);
  const q3 = Math.ceil(creatives.length * 0.75);

  creatives.forEach((c, idx) => {
    if (idx < q1) c.등급 = '최우수';
    else if (idx < q2) c.등급 = '우수';
    else if (idx < q3) c.등급 = '보통';
    else c.등급 = '미흡';
  });

  console.log(`✅ Total Score 산출 완료 (가중치: 전환${weights.conv*100}% CPA${weights.cpa*100}% IPM${weights.ipm*100}%)`);
  return creatives;
}

// ══════════════════════════════════════════
// Step 1: 통합 실행 함수
// ══════════════════════════════════════════

/**
 * Step 1 전체 실행: 집계 → Rank → Total Score
 * 
 * @param {Array} rows - CSV 파싱된 로데이터 행 배열
 * @param {Object} options - 옵션
 *   - weights: Total Score 가중치 { conv, cpa, ipm }
 *   - dateColumn: 날짜 컬럼명 (자동 감지 시 null)
 *   - startDate: 시작일 (YYYY-MM-DD, 선택)
 *   - endDate: 종료일 (YYYY-MM-DD, 선택)
 *   - groupBy: 집계 기준 ('소재명' 또는 '파일명', 기본값: '소재명')
 * @returns {Object} { creatives, dateRange, dateColumn, groupBy }
 */
function runStep1_Scoring(rows, options = {}) {
  console.log(`\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
  console.log(`📊 Step 1: 데이터 통합 및 스코어링 시작`);
  console.log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`);

  // 옵션 추출
  const { 
    weights, 
    dateColumn: userDateColumn, 
    startDate, 
    endDate,
    groupBy = '소재명' 
  } = options;

  console.log(`📋 집계 기준: ${groupBy}`);

  // 0. 날짜 컬럼 감지
  const headers = rows.length > 0 ? Object.keys(rows[0]) : [];
  const dateColumn = userDateColumn || detectDateColumn(headers);
  
  if (dateColumn) {
    console.log(`📅 날짜 컬럼: "${dateColumn}"`);
  } else {
    console.log(`⚠️ 날짜 컬럼을 찾을 수 없습니다. 전체 데이터 사용`);
  }

  // 전체 데이터 날짜 범위
  const fullDateRange = getDateRange(rows, dateColumn);
  console.log(`📅 전체 데이터 기간: ${fullDateRange.min || 'N/A'} ~ ${fullDateRange.max || 'N/A'}`);

  // 1. 기간 필터링
  const filteredRows = filterByDateRange(rows, dateColumn, startDate, endDate);
  
  if (filteredRows.length === 0) {
    console.log(`❌ 필터링 결과 데이터가 없습니다.`);
    return { 
      creatives: [], 
      dateRange: fullDateRange, 
      dateColumn, 
      filteredDateRange: { min: null, max: null },
      groupBy
    };
  }

  // 실제 필터링된 날짜 범위
  const filteredDateRange = getDateRange(filteredRows, dateColumn);
  console.log(`✅ 분석 대상 기간: ${filteredDateRange.min || 'N/A'} ~ ${filteredDateRange.max || 'N/A'}\n`);

  // 2. 소재별 집계 (groupBy 옵션 적용)
  const aggregated = aggregateCreativeData(filteredRows, groupBy);
  
  // 3. Rank 점수 산출
  const ranked = calculateRankScores(aggregated);
  
  // 4. Total Score 산출
  const scored = calculateTotalScore(ranked, weights);

  console.log(`\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
  console.log(`✅ Step 1 완료: ${scored.length}개 소재 분석`);
  console.log(`   - 집계 기준: ${groupBy}`);
  console.log(`   - 최고 점수: ${scored[0]?.TotalScore || 0}점 (${scored[0]?.집계기준 || 'N/A'})`);
  console.log(`   - 평균 점수: ${(scored.reduce((s, c) => s + c.TotalScore, 0) / scored.length).toFixed(1)}점`);
  console.log(`   - 최저 점수: ${scored[scored.length - 1]?.TotalScore || 0}점`);
  console.log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`);

  return {
    creatives: scored,
    fullDateRange,
    filteredDateRange,
    dateColumn,
    groupBy
  };
}

// ══════════════════════════════════════════
// Step 1-4: 기간 비교 분석 (소재 피로도)
// ══════════════════════════════════════════

/**
 * 두 기간의 소재 성과를 비교하여 순위 변동 분석
 * 
 * @param {Array} rows - 전체 로데이터
 * @param {String} dateColumn - 날짜 컬럼명
 * @param {String} baseStart - 기준 기간 시작일
 * @param {String} baseEnd - 기준 기간 종료일
 * @param {String} compStart - 비교 기간 시작일
 * @param {String} compEnd - 비교 기간 종료일
 * @param {Object} weights - Total Score 가중치
 * @param {String} groupBy - 집계 기준 ('소재명' 또는 '파일명')
 * @returns {Object} 비교 분석 결과
 */
function comparePeriods(rows, dateColumn, baseStart, baseEnd, compStart, compEnd, weights, groupBy = '소재명') {
  console.log(`\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
  console.log(`📊 기간 비교 분석 시작 (기준: ${groupBy})`);
  console.log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`);

  // 기준 기간 분석
  console.log(`📅 기준 기간: ${baseStart} ~ ${baseEnd}`);
  const baseRows = filterByDateRange(rows, dateColumn, baseStart, baseEnd);
  const baseAgg = aggregateCreativeData(baseRows, groupBy);
  const baseRanked = calculateRankScores(baseAgg);
  const baseScored = calculateTotalScore(baseRanked, weights);

  // 비교 기간 분석
  console.log(`\n📅 비교 기간: ${compStart} ~ ${compEnd}`);
  const compRows = filterByDateRange(rows, dateColumn, compStart, compEnd);
  const compAgg = aggregateCreativeData(compRows, groupBy);
  const compRanked = calculateRankScores(compAgg);
  const compScored = calculateTotalScore(compRanked, weights);

  // 소재별 비교 데이터 생성 (집계기준 사용)
  const comparison = [];
  const baseMap = new Map(baseScored.map(c => [c.집계기준, c]));
  const compMap = new Map(compScored.map(c => [c.집계기준, c]));

  // 모든 소재 순회
  const allCreatives = new Set([...baseMap.keys(), ...compMap.keys()]);

  allCreatives.forEach(key => {
    const base = baseMap.get(key);
    const comp = compMap.get(key);

    if (!base && !comp) return;

    const item = {
      소재명: (base || comp).소재명,
      파일명: (base || comp).파일명,
      집계기준: key,
      유형: (base || comp).유형,
      
      // 기준 기간 데이터
      baseRank: base?.Rank || null,
      baseScore: base?.TotalScore || 0,
      base전환: base?.전환 || 0,
      baseCPA: base?.CPA || 0,
      baseIPM: base?.IPM || 0,
      
      // 비교 기간 데이터
      compRank: comp?.Rank || null,
      compScore: comp?.TotalScore || 0,
      comp전환: comp?.전환 || 0,
      compCPA: comp?.CPA || 0,
      compIPM: comp?.IPM || 0,
      
      // 변동 지표
      rankChange: null,
      scoreChange: null,
      status: 'stable', // 'improved', 'declined', 'stable', 'new', 'removed'
      
      // 메타 데이터
      tags: (base || comp).tags,
      insights: (base || comp).insights,
      meta: (base || comp).meta
    };

    // 순위 변동 계산
    if (base && comp) {
      item.rankChange = base.Rank - comp.Rank; // 양수면 순위 상승, 음수면 하락
      item.scoreChange = comp.TotalScore - base.TotalScore;
      
      if (item.rankChange > 0) item.status = 'improved';
      else if (item.rankChange < 0) item.status = 'declined';
      else item.status = 'stable';
    } else if (comp && !base) {
      item.status = 'new';
    } else if (base && !comp) {
      item.status = 'removed';
    }

    comparison.push(item);
  });

  // 순위 변동 순으로 정렬 (개선 순)
  comparison.sort((a, b) => {
    if (a.rankChange === null && b.rankChange === null) return 0;
    if (a.rankChange === null) return 1;
    if (b.rankChange === null) return -1;
    return b.rankChange - a.rankChange;
  });

  console.log(`\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
  console.log(`✅ 기간 비교 완료: ${comparison.length}개 소재`);
  console.log(`   - 개선: ${comparison.filter(c => c.status === 'improved').length}개`);
  console.log(`   - 하락: ${comparison.filter(c => c.status === 'declined').length}개`);
  console.log(`   - 유지: ${comparison.filter(c => c.status === 'stable').length}개`);
  console.log(`   - 신규: ${comparison.filter(c => c.status === 'new').length}개`);
  console.log(`   - 제거: ${comparison.filter(c => c.status === 'removed').length}개`);
  console.log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`);

  return {
    comparison,
    basePeriod: { start: baseStart, end: baseEnd, creatives: baseScored },
    compPeriod: { start: compStart, end: compEnd, creatives: compScored },
    groupBy
  };
}

/**
 * 일자별 소재 순위 변화 추적 (시계열 데이터)
 * 
 * @param {Array} rows - 전체 로데이터
 * @param {String} dateColumn - 날짜 컬럼명
 * @param {Array} targetCreatives - 추적할 소재명/파일명 배열 (선택)
 * @param {Object} weights - Total Score 가중치
 * @param {String} groupBy - 집계 기준 ('소재명' 또는 '파일명')
 * @returns {Object} { dates: [], creatives: { 소재명: [rank1, rank2, ...] } }
 */
function trackDailyRankings(rows, dateColumn, targetCreatives = null, weights, groupBy = '소재명') {
  if (!dateColumn) {
    console.log('⚠️ 날짜 컬럼이 없어 일자별 추적 불가');
    return { dates: [], creatives: {}, groupBy };
  }

  console.log(`\n📈 일자별 순위 추적 시작 (기준: ${groupBy})`);

  // 날짜별로 데이터 그룹화
  const dateGroups = new Map();
  rows.forEach(row => {
    const date = parseDate(row[dateColumn]);
    if (!date) return;
    
    const dateKey = formatDate(date);
    if (!dateGroups.has(dateKey)) {
      dateGroups.set(dateKey, []);
    }
    dateGroups.get(dateKey).push(row);
  });

  // 날짜 정렬
  const sortedDates = Array.from(dateGroups.keys()).sort();

  // 각 날짜별로 분석 실행
  const rankingsByDate = new Map();
  sortedDates.forEach(date => {
    const dayRows = dateGroups.get(date);
    const agg = aggregateCreativeData(dayRows, groupBy);
    const ranked = calculateRankScores(agg);
    const scored = calculateTotalScore(ranked, weights);
    
    rankingsByDate.set(date, scored);
  });

  // 소재별 순위 시계열 구성
  const creativesMap = new Map();
  
  sortedDates.forEach(date => {
    const dayRankings = rankingsByDate.get(date);
    
    dayRankings.forEach(c => {
      const key = c.집계기준;
      
      // 타겟 소재 필터링
      if (targetCreatives && !targetCreatives.includes(key)) return;
      
      if (!creativesMap.has(key)) {
        creativesMap.set(key, {
          소재명: c.소재명,
          파일명: c.파일명,
          집계기준: key,
          유형: c.유형,
          ranks: [],
          scores: [],
          dates: []
        });
      }
      
      const creative = creativesMap.get(key);
      creative.ranks.push(c.Rank);
      creative.scores.push(c.TotalScore);
      creative.dates.push(date);
    });
  });

  const result = {
    dates: sortedDates,
    creatives: Object.fromEntries(creativesMap),
    groupBy
  };

  console.log(`✅ 일자별 추적 완료: ${sortedDates.length}일, ${creativesMap.size}개 소재`);

  return result;
}

// ══════════════════════════════════════════
// Export
// ══════════════════════════════════════════
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    detectDateColumn,
    parseDate,
    formatDate,
    filterByDateRange,
    getDateRange,
    aggregateCreativeData,
    calculateRankScores,
    calculateTotalScore,
    runStep1_Scoring,
    comparePeriods,
    trackDailyRankings
  };
}
