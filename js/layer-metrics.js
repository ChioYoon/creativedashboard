/* ═══════════════════════════════════════════════════════════════
 *  공용 레이어 지표 모듈 (layer-metrics.js)
 *  Com2uS R팀 소재 분석 대시보드 — step1_integrated.html · step2_clustering.html 공유
 *
 *  목적: 분석 레이어(Google Ads / MMP) 지표 산출 로직의 단일 소스.
 *  step1_integrated.html 에서 바이트 동일 추출(동작 불변). 의존: window.currentAnalysisLayer.
 *
 *  노출: 각 정의를 window 전역(step1 인라인 bare 참조 호환) + window.LayerMetrics(네임스페이스)에.
 * ═══════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  // Stage 5-I: 풀 대비 백분위(0-100, 높을수록 우수) → 상위/하위 배지 HTML.
  // 절반 기준: pct>=50 → 상위 (녹색), pct<50 → 하위 (주황).
  function pctBadgeHtml(pct) {
    if (pct === null || pct === undefined) return '';
    const top = pct >= 50;
    const label = top ? `상위 ${Math.max(1, 100 - pct)}%` : `하위 ${Math.max(1, pct)}%`;
    const cls = top ? 'pctile-top' : 'pctile-bottom';
    return ` <span class="pctile-badge ${cls}">${label}</span>`;
  }

  // 소재 품질(MMP) 등급 배지 색.
  const MMP_GRADE_STYLE = {
    '최우수': 'background:#ccfbf1;color:#115e59;',
    '우수':   'background:#d1fae5;color:#065f46;',
    '양호':   'background:#fef9c3;color:#854d0e;',
    '보통':   'background:#fed7aa;color:#9a3412;',
    '개선필요': 'background:#fee2e2;color:#991b1b;',
  };

  // MMP 윈도우 집계 → 4 품질지표 (파이프라인 compute_mmp_quality 동일: 잔존0→cpi null, 비용0→roas null)
  function mmpQualityMetrics(a) {
    return {
      d1_ipm: a.imp > 0 ? (a.retained_d1 / a.imp) * 1000 : 0,
      d1_cpi: a.retained_d1 > 0 ? (a.cost / a.retained_d1) : null,
      d1_ret: a.installs > 0 ? (a.retained_d1 / a.installs) * 100 : 0,
      d7_roas: a.cost > 0 ? (a.revenue_d7 / a.cost) : null,
    };
  }

  // MMP 4지표(전환=installs↑·D1 CPI↓·D1 IPM↑·D7 ROAS↑)를 rank 점수화 → 항목 순서대로 점수 배열 반환.
  // 파이프라인 compute_mmp_quality_scores 동일(균등 25%·None→0·등급컷). 2-0b·피로도 공용. items 는 내부 필드 추가됨.
  function scoreMmpItems(items) {
    const n = items.length; if (!n) return [];
    const r = (v, d) => { const p = Math.pow(10, d); return Math.round(v * p) / p; };
    items.forEach(it => it._s = {});
    const assignRankTies = (ordered, val) => { let rank = 1, prev = null; ordered.forEach((it, k) => { const v = val(it); if (!(prev !== null && Math.abs(v - prev) < 0.0001)) rank = k + 1; it._rk = rank; prev = v; }); };
    const rankScore = (field, higher) => {
      const val = it => { const v = it[field]; return v == null ? (higher ? -Infinity : Infinity) : v; };
      const ordered = [...items].sort((a, b) => higher ? (val(b) - val(a)) : (val(a) - val(b)));
      assignRankTies(ordered, val);
      ordered.forEach(it => { it._s[field] = (it[field] == null) ? 0 : ((n - it._rk + 1) / n) * 100; });
    };
    rankScore('installs', true); rankScore('d1_cpi', false); rankScore('d1_ipm', true); rankScore('d7_roas', true);
    items.forEach(it => it._total = (it._s.installs + it._s.d1_cpi + it._s.d1_ipm + it._s.d7_roas) / 4);
    const ranked = [...items].sort((a, b) => b._total - a._total);
    const rankMap = new Map(); ranked.forEach((it, i) => rankMap.set(it, i + 1));
    return items.map(it => {
      const t = it._total;
      const grade = t >= 80 ? '최우수' : t >= 60 ? '우수' : t >= 40 ? '양호' : t >= 20 ? '보통' : '개선필요';
      return { total: r(t, 2), grade, rank: rankMap.get(it), conv: r(it._s.installs, 1), cpi: r(it._s.d1_cpi, 1), ipm: r(it._s.d1_ipm, 1), roas: r(it._s.d7_roas, 1) };
    });
  }

  // 활성 레이어 라벨·툴팁 단일 소스 — setLayerHeaders(헤더+data-tip)·renderTypeSummaryTable·export 공용.
  //   m1~m4/score=컬럼 라벨, tip1~tip4/tipScore=헤더 툴팁, s2~s4=export 점수 라벨, tag=레이어 배지.
  function layerLabels() {
    return (window.currentAnalysisLayer || 'ads') === 'mmp'
      ? { tag: 'MMP 품질 기준', m1: '전환', m2: 'D1 CPI', m3: 'D1 IPM', m4: 'D7 ROAS', score: '품질점수',
          s2: 'D1 CPI점수', s3: 'D1 IPM점수', s4: 'D7 ROAS점수',
          tip1: 'MMP 설치수 (installs)', tip2: '비용 ÷ D1 잔존수 · 낮을수록 효율적',
          tip3: '(D1 잔존수 ÷ 노출) × 1,000 · 높을수록 우수', tip4: '(D0~D7 누적매출 ÷ 비용) × 100% · 설치 후 7일 내 조기 회수율(전체 ROAS 아님) · 데이터 없으면 —',
          tipScore: '전환·D1 CPI·D1 IPM·D7 ROAS 점수의 가중 합산 (MMP)' }
      : { tag: 'Google Ads 기준', m1: '전환', m2: 'CPA', m3: 'IPM', m4: 'ROAS', score: '총점',
          s2: 'CPA점수', s3: 'IPM점수', s4: 'ROAS점수',
          tip1: '설치 또는 목표 행동 완료 횟수', tip2: '비용 ÷ 전환수 · 낮을수록 효율적',
          tip3: '(전환수 ÷ 노출수) × 1,000 · 높을수록 우수', tip4: '(매출 ÷ 비용) × 100% · Revenue 컬럼 없으면 —',
          tipScore: '전환수·CPA·IPM·ROAS 점수의 가중치 합산 (Google Ads)' };
  }

  // ── 노출: window 전역(인라인 bare 참조 호환) + 네임스페이스 ──
  const _exports = { pctBadgeHtml, MMP_GRADE_STYLE, mmpQualityMetrics, scoreMmpItems, layerLabels };
  Object.assign(window, _exports);
  window.LayerMetrics = Object.assign(window.LayerMetrics || {}, _exports);
})();
