/**
 * ═══════════════════════════════════════════════════════════════
 *  데이터 소스 추상화 레이어 (data-source.js)
 *  Com2uS R팀 소재 분석 대시보드 — Stage 1
 *
 *  목적:
 *  - CSV 업로드 / CSV 붙여넣기 / JSON 업로드 / JSON URL fetch 를 단일 진입점으로 통합
 *  - 백엔드 파이프라인 산출물(public/data/{title}.json)을 자동 로드하는 기반 마련
 *  - 향후 Stage 2~에서 추가될 백엔드 모드와 매끄럽게 공존
 *
 *  의존성:
 *  - step1_integrated.html 인라인 `plParseCSV()` (전역 함수)
 *  - sessionStorage 키 격리 헬퍼 (`getSessionKey`) 노출
 *
 *  ★ 본 모듈은 기존 processCSV / processPastedCSV 의 *상위 wrapper* 역할만 한다.
 *    하위 호환을 위해 기존 함수 시그니처를 절대 변경하지 않는다.
 * ═══════════════════════════════════════════════════════════════
 */

(function () {
  'use strict';

  // ─────────────────────────────────────────────────────────────
  // 1. 데이터 소스 메타 (전역 노출)
  // ─────────────────────────────────────────────────────────────
  const DataSourceMeta = {
    SCHEMA_VERSION: '1.0',
    SUPPORTED_SOURCES: ['csv-upload', 'csv-paste', 'json-upload', 'json-url'],
  };

  // 현재 활성 타이틀 (URL ?title= 또는 셀렉터에서 설정)
  let _activeTitleId = '';

  function getActiveTitleId() {
    return _activeTitleId || '';
  }

  function setActiveTitleId(id) {
    _activeTitleId = (id || '').trim();
    // URL도 갱신 (히스토리 push 없이 replace) — 새로고침 시 같은 타이틀 유지
    try {
      const url = new URL(window.location.href);
      if (_activeTitleId) {
        url.searchParams.set('title', _activeTitleId);
      } else {
        url.searchParams.delete('title');
      }
      window.history.replaceState({}, '', url.toString());
    } catch (_) {}
  }

  // URL에서 초기 타이틀 추출 (DOMContentLoaded 전후 어디서든 동작)
  function readTitleFromUrl() {
    try {
      return new URLSearchParams(window.location.search).get('title') || '';
    } catch (_) {
      return '';
    }
  }

  // ─────────────────────────────────────────────────────────────
  // 2. sessionStorage 키 격리 헬퍼
  // ─────────────────────────────────────────────────────────────
  /**
   * 타이틀별 sessionStorage 키를 생성한다.
   * - titleId 없음 → 기존 키 그대로 (하위 호환)
   * - titleId 있음 → `${baseKey}_${titleId}` 형태
   *
   * 예) getSessionKey('r_team_cluster_session', 'pepp-us')
   *     → 'r_team_cluster_session_pepp-us'
   *
   * @param {string} baseKey
   * @param {string} [titleId] - 생략 시 현재 활성 타이틀 사용
   * @returns {string}
   */
  function getSessionKey(baseKey, titleId) {
    const tid = (titleId === undefined ? getActiveTitleId() : titleId) || '';
    if (!tid) return baseKey;
    // 영숫자·하이픈·언더스코어만 허용 (XSS·키 충돌 방지)
    const safe = tid.replace(/[^a-zA-Z0-9_-]/g, '');
    return `${baseKey}_${safe}`;
  }

  // ─────────────────────────────────────────────────────────────
  // 2-b. 데이터 신선도 (freshness) 유틸
  // ─────────────────────────────────────────────────────────────
  /**
   * creatives[] 의 kpi_daily / mmp_daily 를 훑어 가장 최근 데이터 날짜(YYYY-MM-DD)를 구한다.
   * 집행 데이터가 하나도 없으면 빈 문자열.
   * @param {Array} creatives
   * @returns {string}
   */
  function computeDataAsOf(creatives) {
    let max = '';
    const scan = (arr) => {
      if (!Array.isArray(arr)) return;
      for (const d of arr) {
        const dt = (d && (d.date || d.day)) || '';
        if (typeof dt === 'string' && dt > max) max = dt;
      }
    };
    (creatives || []).forEach((c) => {
      if (!c) return;
      scan(c.kpi_daily);
      scan(c.mmp_daily);
    });
    return max;
  }

  function _fx_daysBetween(isoA, isoB) {
    // 두 'YYYY-MM-DD' 사이 일수(정수, A가 과거면 양수). 파싱 실패 시 null.
    const a = Date.parse((isoA || '').slice(0, 10) + 'T00:00:00Z');
    const b = Date.parse((isoB || '').slice(0, 10) + 'T00:00:00Z');
    if (isNaN(a) || isNaN(b)) return null;
    return Math.round((b - a) / 86400000);
  }

  function _fx_esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, (ch) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]));
  }

  function _fx_shortGen(gen) {
    // '2026-07-10T13:00:56+09:00' → '07-10 13:00'
    const m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/.exec(gen || '');
    return m ? `${m[2]}-${m[3]} ${m[4]}:${m[5]}` : ((gen || '').slice(0, 10) || '미상');
  }

  /**
   * 데이터 신선도 배지 정보 + DS(모노+Red) 인라인 HTML 을 만든다.
   * 판정 기준: 파이프라인 생성일과 최신 데이터일의 간격(gap).
   *   gap ≤ 2 → fresh / 3–14 → aging / >14 → stale / 데이터 없음 → empty
   * @param {{generatedAt?:string, pipelineVersion?:string, dataAsOf?:string}} opts
   * @returns {{level:string, gapDays:(number|null), asOf:string, generatedAt:string,
   *            pipelineVersion:string, label:string, html:string}}
   */
  function freshness(opts) {
    opts = opts || {};
    const asOf = opts.dataAsOf || '';
    const gen = opts.generatedAt || '';
    const pv = opts.pipelineVersion || '';
    const genDate = (gen || '').slice(0, 10);

    let level, gapDays = null, label;
    if (!asOf) {
      level = 'empty';
      label = '집행 데이터 없음';
    } else {
      gapDays = genDate ? _fx_daysBetween(asOf, genDate) : null;
      if (gapDays == null) { level = 'fresh'; label = '데이터 로드됨'; }
      else if (gapDays <= 2) { level = 'fresh'; label = '데이터 최신'; }
      else if (gapDays <= 14) { level = 'aging'; label = `업데이트 지연 (${gapDays}일)`; }
      else { level = 'stale'; label = `오래된 데이터 (${gapDays}일 경과)`; }
    }

    // DS 모노 + Red 램프
    const TONE = {
      fresh: { bg: '#F7F4EE', bd: '#E4E1DC', fg: '#4C4C4C', dot: '#767676' },
      aging: { bg: '#FAF9F7', bd: '#E4E1DC', fg: '#4C4C4C', dot: '#999999' },
      stale: { bg: 'rgba(220,40,40,.06)', bd: 'rgba(220,40,40,.28)', fg: '#DC2828', dot: '#DC2828' },
      empty: { bg: '#F7F4EE', bd: '#E4E1DC', fg: '#808080', dot: '#CCCCCC' },
    };
    const t = TONE[level] || TONE.fresh;

    // pipeline_version 은 개발 메타라 배지에는 노출하지 않는다(반환 객체에는 포함).
    const detail = (level === 'empty')
      ? '<span style="color:#808080;font-weight:500;">이 타이틀은 아직 집행(KPI) 데이터가 없습니다</span>'
      : `<span style="color:var(--text-secondary,#767676);font-weight:500;">기준일 <strong style="color:inherit;">${_fx_esc(asOf)}</strong> · 생성 ${_fx_esc(_fx_shortGen(gen))}</span>`;

    const html =
      `<div class="ds-freshness ds-freshness-${level}" title="파이프라인 생성일과 최신 데이터일의 간격으로 신선도를 판정합니다." ` +
      `style="display:inline-flex;align-items:center;gap:10px;flex-wrap:wrap;font-size:12px;line-height:1.4;` +
      `padding:7px 12px;border-radius:8px;border:1px solid ${t.bd};background:${t.bg};color:${t.fg};">` +
      `<span style="display:inline-flex;align-items:center;gap:6px;font-weight:700;white-space:nowrap;">` +
      `<span style="width:7px;height:7px;border-radius:50%;background:${t.dot};flex:none;"></span>${_fx_esc(label)}</span>` +
      detail +
      `</div>`;

    return { level, gapDays, asOf, generatedAt: gen, pipelineVersion: pv, label, html };
  }

  // ─────────────────────────────────────────────────────────────
  // 3. JSON 스키마 v1 → 내부 normalizedData 변환
  // ─────────────────────────────────────────────────────────────
  /**
   * 백엔드 산출 JSON(스키마 v1)을 대시보드 내부 구조로 변환한다.
   * 결과는 plParseCSV()의 출력과 동일한 형태 (`{ columns, rows, _renameMap }`).
   *
   * JSON 스키마 v1 (Stage 2 Pydantic 모델과 동일):
   * {
   *   "schema_version": "1.0",
   *   "title_id": "starseed-jp",
   *   "generated_at": "2026-05-29T03:00:00+09:00",
   *   "creatives": [
   *     { "creative_id": "...", "유형": "BNR", "소재명": "...", "전환": 100, ... }
   *   ]
   * }
   *
   * @param {object} data - JSON.parse 결과
   * @returns {{columns: string[], rows: object[], _renameMap: object, _meta: object}}
   */
  function normalizeFromJson(data) {
    if (!data || typeof data !== 'object') {
      throw new Error('JSON 데이터가 유효하지 않습니다.');
    }
    if (!Array.isArray(data.creatives)) {
      throw new Error('JSON 스키마 오류: creatives 배열이 없습니다.');
    }
    if (data.schema_version && data.schema_version !== DataSourceMeta.SCHEMA_VERSION) {
      console.warn(
        `[data-source] 스키마 버전 불일치 — 입력: ${data.schema_version}, 기대: ${DataSourceMeta.SCHEMA_VERSION}. ` +
        `호환 처리하지만 누락된 필드가 있을 수 있습니다.`
      );
    }

    const rows = data.creatives;

    // Stage 5-F-1: deprecated `marketer_insight` 필드를 `one_line_insight` 로 alias.
    // - Stage 5-E 가 Python 측에서 dual-write 하던 것을 JS 한 곳으로 격상 (정규화는 데이터 경계에서).
    // - 구 JSON 이 marketer_insight 를 직접 가지고 있는 경우 보존 (== null 가드).
    // - one_line_insight 부재 시 아무 작업도 안 함 (graceful).
    rows.forEach((r) => {
      if (r && r.marketer_insight == null && typeof r.one_line_insight === 'string') {
        r.marketer_insight = r.one_line_insight;
      }
    });

    // 컬럼 헤더는 첫 행에서 추출 (병합 union)
    const colSet = new Set();
    rows.forEach((r) => Object.keys(r || {}).forEach((k) => colSet.add(k)));
    const columns = Array.from(colSet);

    return {
      columns,
      rows,
      _renameMap: {},
      _meta: {
        source: 'json',
        title_id: data.title_id || '',
        generated_at: data.generated_at || '',
        pipeline_version: data.pipeline_version || '',
        data_as_of: computeDataAsOf(rows),
        schema_version: data.schema_version || DataSourceMeta.SCHEMA_VERSION,
        creative_count: rows.length,
        campaign_canonical: (data.campaign_canonical && typeof data.campaign_canonical === 'object') ? data.campaign_canonical : {},
        unmatched_assets: Array.isArray(data.unmatched_assets) ? data.unmatched_assets : [],
        game_context: (typeof data.game_context === 'string') ? data.game_context : '',
      },
    };
  }

  // ─────────────────────────────────────────────────────────────
  // 4. 단일 진입점: loadCreativeData
  // ─────────────────────────────────────────────────────────────
  /**
   * 모든 데이터 소스를 동일한 인터페이스로 로드한다.
   *
   * @param {'csv-upload'|'csv-paste'|'json-upload'|'json-url'} source
   * @param {object} opts
   * @param {File} [opts.file]      - csv-upload / json-upload
   * @param {string} [opts.text]    - csv-paste 의 raw 텍스트
   * @param {string} [opts.url]     - json-url 의 fetch 대상
   * @param {string} [opts.titleId] - 명시적 타이틀 지정 (없으면 활성 타이틀 사용)
   * @returns {Promise<{normalized: object, sourceMeta: object}>}
   *
   * 주의: 본 함수는 normalized 데이터만 반환한다. 실제 점수 계산·UI 렌더링은
   *      step1_integrated.html 의 기존 흐름을 그대로 사용한다.
   */
  async function loadCreativeData(source, opts) {
    opts = opts || {};
    if (!DataSourceMeta.SUPPORTED_SOURCES.includes(source)) {
      throw new Error(`지원하지 않는 데이터 소스: ${source}`);
    }
    if (opts.titleId) setActiveTitleId(opts.titleId);

    const tid = getActiveTitleId();
    const sourceMeta = { source, title_id: tid, loaded_at: new Date().toISOString() };

    if (source === 'csv-upload' || source === 'csv-paste') {
      let text = '';
      if (source === 'csv-upload') {
        if (!opts.file) throw new Error('CSV 파일이 지정되지 않았습니다.');
        text = await opts.file.text();
        sourceMeta.file_name = opts.file.name;
      } else {
        text = opts.text || '';
      }
      if (typeof window.plParseCSV !== 'function') {
        throw new Error('CSV 파서(plParseCSV)가 로드되지 않았습니다.');
      }
      const normalized = window.plParseCSV(text);
      if (!normalized) throw new Error('CSV 파싱 실패: 유효하지 않은 데이터');
      sourceMeta.row_count = (normalized.rows || []).length;
      return { normalized, sourceMeta };
    }

    if (source === 'json-upload') {
      if (!opts.file) throw new Error('JSON 파일이 지정되지 않았습니다.');
      const text = await opts.file.text();
      const parsed = JSON.parse(text);
      const normalized = normalizeFromJson(parsed);
      sourceMeta.file_name = opts.file.name;
      sourceMeta.row_count = normalized.rows.length;
      sourceMeta.title_id = sourceMeta.title_id || normalized._meta.title_id;
      return { normalized, sourceMeta };
    }

    if (source === 'json-url') {
      if (!opts.url) throw new Error('JSON URL이 지정되지 않았습니다.');
      const res = await fetch(opts.url, { cache: 'no-store' });
      if (!res.ok) {
        const err = new Error(`JSON 로드 실패 (HTTP ${res.status}): ${opts.url}`);
        err.httpStatus = res.status;  // 404(미태깅 타이틀) 구분용 — 호출측에서 graceful 처리
        throw err;
      }
      const parsed = await res.json();
      const normalized = normalizeFromJson(parsed);
      sourceMeta.url = opts.url;
      sourceMeta.row_count = normalized.rows.length;
      sourceMeta.title_id = sourceMeta.title_id || normalized._meta.title_id;
      // JSON에 title_id가 있으면 활성 타이틀 동기화
      if (normalized._meta.title_id && !tid) {
        setActiveTitleId(normalized._meta.title_id);
      }
      return { normalized, sourceMeta };
    }

    throw new Error(`예상치 못한 source 분기: ${source}`);
  }

  // ─────────────────────────────────────────────────────────────
  // 5. 타이틀 메타데이터 로더 (js/titles.json)
  // ─────────────────────────────────────────────────────────────
  /**
   * js/titles.json 로드. 실패 시 빈 배열 반환 (선택적 의존성).
   * @returns {Promise<Array<{id, name, json_url}>>}
   */
  async function loadTitleManifest() {
    try {
      const res = await fetch('js/titles.json', { cache: 'no-store' });
      if (!res.ok) return [];
      const list = await res.json();
      return Array.isArray(list) ? list : [];
    } catch (e) {
      console.warn('[data-source] js/titles.json 로드 실패:', e.message);
      return [];
    }
  }

  // ─────────────────────────────────────────────────────────────
  // 6. 전역 노출 (인라인 스크립트에서 그대로 사용)
  // ─────────────────────────────────────────────────────────────
  window.DataSource = {
    loadCreativeData,
    loadTitleManifest,
    normalizeFromJson,
    computeDataAsOf,
    freshness,
    getActiveTitleId,
    setActiveTitleId,
    readTitleFromUrl,
    getSessionKey,
    META: DataSourceMeta,
  };

  // 페이지 진입 즉시 URL의 ?title= 을 활성 타이틀로 반영
  // (step1_integrated.html 의 DOMContentLoaded 보다 먼저 실행됨)
  const urlTitle = readTitleFromUrl();
  if (urlTitle) {
    _activeTitleId = urlTitle;
    console.log(`[data-source] URL에서 타이틀 감지: ${urlTitle}`);
  }
})();
