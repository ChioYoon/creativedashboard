/**
 * ═══════════════════════════════════════════════════════════════
 *  Gemini API 공통 모듈  |  Com2uS R팀 소재 분석 대시보드
 *  - API 키 관리 (localStorage 영속화)
 *  - 공통 호출 함수 (재시도, 에러 핸들링)
 *  - 마케팅 분석 특화 프롬프트 빌더
 * ═══════════════════════════════════════════════════════════════
 */

/* ──────────────────────────────────────
   1. 설정 상수
────────────────────────────────────── */
const GEMINI_CONFIG = {
  MODEL:        'gemini-2.5-flash',        // Gemini 2.5 Flash (thinkingBudget:0으로 thinking 비활성화 → JSON 잘림 방지)
  BASE_URL:     'https://generativelanguage.googleapis.com/v1beta/models',
  STORAGE_KEY:  'r_team_gemini_api_key',
  PLAN_KEY:     'r_team_gemini_plan',       // 'free' | 'paid'
  DEFAULT_KEY:  'AIzaSyDLfOtC-fVYgVBtOgDF8A84mOoyK5MS38M',

  // ── 플랜별 출력 토큰 한도 ────────────────────────────────
  // Gemini 2.5 Flash 실제 제한: 입출력 합산 65,536(유료) / 8,192(무료) 토큰
  //
  // ★ 무료 전략: 1회 호출 + 핵심 슬롯 1개만 → rate limit 최소화 + 토큰 극소화
  //   소재 성과: winTags 슬롯 1개 (1회 호출)  → ~400자 × 1.3(한글비율) ≈ 800토큰
  //   피로도:    riseReason 슬롯 1개 (1회 호출) → ~350자 × 1.3 ≈ 700토큰
  //   ※ 마케터 인사이트(marketer_insight) 완전 미전송 → 입력 절감 → 출력 품질 향상
  //
  // ★ 유료 전략: marketer_insight 원문 200자 포함, 전체 슬롯
  //   소재 성과: 3슬롯씩 2회 호출 (6슬롯)
  //   피로도: 2슬롯씩 2회 호출 (4슬롯)
  // ── 토큰 계산 근거 ────────────────────────────────────────────────────────
  // 한글 1자 ≈ 1.5~2토큰 (UTF-8 멀티바이트)
  // 무료 winTags: 목표 출력 500자 × 2토큰 + 입력오버헤드 500 = 1500 → 1500 (여유)
  // 유료 3슬롯: 슬롯당 300자 × 3 × 2토큰 + 오버헤드 = 2200 → 2500 (여유)
  FREE_TOKENS:  1500,      // 무료: winTags 1슬롯 완전 출력 보장 (500자×2토큰+여유)
  PAID_TOKENS:  2500,      // 유료: 3슬롯 × 300자 × 2토큰 + 안전마진

  // 피로도 분석 토큰
  // 무료 riseReason: 목표 출력 500자 × 2토큰 + 오버헤드 = 1500 → 1500 (여유)
  // 유료 2슬롯: 슬롯당 300자 × 2 × 2토큰 + 오버헤드 = 1600 → 2000 (여유)
  FREE_FATIGUE_TOKENS:  1500,  // 무료 피로도: riseReason 1슬롯 완전 출력 보장
  PAID_FATIGUE_TOKENS:  2000,  // 유료 피로도: 2슬롯씩 2회 × ~300자 × 2토큰

  MAX_TOKENS:   2048,
  CLUSTER_TOKENS: 2400,
  TEMPERATURE:  0.2,       // 낮출수록 JSON 형식 준수율 상승 (0.25 → 0.2)
  TOP_P:        0.85,
  MAX_RETRY:    2,
  RETRY_DELAY:  1500,
  BLOCK_INTERVAL: 1600,
};

/* ──────────────────────────────────────
   2. API 키 관리
────────────────────────────────────── */
const GeminiKeyManager = {
  get() {
    const stored = localStorage.getItem(GEMINI_CONFIG.STORAGE_KEY);
    if (!stored && GEMINI_CONFIG.DEFAULT_KEY) {
      localStorage.setItem(GEMINI_CONFIG.STORAGE_KEY, GEMINI_CONFIG.DEFAULT_KEY);
      return GEMINI_CONFIG.DEFAULT_KEY;
    }
    return stored || '';
  },
  set(key)   { localStorage.setItem(GEMINI_CONFIG.STORAGE_KEY, key.trim()); },
  clear()    { localStorage.removeItem(GEMINI_CONFIG.STORAGE_KEY); },
  isSet()    { return !!this.get(); },

  // ── 플랜 관리 (free / paid) ───────────────────────────────
  getPlan()  { return localStorage.getItem(GEMINI_CONFIG.PLAN_KEY) || 'free'; },
  setPlan(p) { localStorage.setItem(GEMINI_CONFIG.PLAN_KEY, p === 'paid' ? 'paid' : 'free'); },
  isPaid()   { return this.getPlan() === 'paid'; },
  clearPlan(){ localStorage.removeItem(GEMINI_CONFIG.PLAN_KEY); },

  // 플랜에 따른 출력 토큰 반환 (소재 성과 분석용)
  getMaxTokens() {
    return this.isPaid() ? GEMINI_CONFIG.PAID_TOKENS : GEMINI_CONFIG.FREE_TOKENS;
  },

  // 피로도 분석용 출력 토큰 반환
  getFatigueTokens() {
    return this.isPaid() ? GEMINI_CONFIG.PAID_FATIGUE_TOKENS : GEMINI_CONFIG.FREE_FATIGUE_TOKENS;
  },

  // marketer_insight를 프롬프트에 포함할지 여부
  // ★ 무료: 완전 제외 (입력 토큰 절감 → 출력 예산 확보)
  // ★ 유료: 원문 최대 200자 포함
  includeInsight() { return this.isPaid(); },
};

/* ──────────────────────────────────────
   3. 핵심 API 호출
   ※ RATE_LIMIT(429)은 재시도하지 않음
     → 재시도할수록 한도를 추가 소진하므로 즉시 에러 반환
   ※ 네트워크 오류(fetch 실패)만 1회 재시도
────────────────────────────────────── */
async function callGeminiAPI(prompt, { maxTokens = GEMINI_CONFIG.MAX_TOKENS, temperature = GEMINI_CONFIG.TEMPERATURE, topP = GEMINI_CONFIG.TOP_P } = {}) {
  const apiKey = GeminiKeyManager.get();
  if (!apiKey) throw new Error('API_KEY_MISSING');

  const url = `${GEMINI_CONFIG.BASE_URL}/${GEMINI_CONFIG.MODEL}:generateContent?key=${apiKey}`;
  const body = {
    contents: [{ parts: [{ text: prompt }] }],
    generationConfig: {
      maxOutputTokens: maxTokens,
      temperature,
      topP,
      // ★ thinkingBudget: 0 → thinking 모드 비활성화
      //   gemini-2.0-flash에서는 이 필드 무시됨 (무해)
      //   gemini-2.5-flash에서 thinking이 기본 활성화되면 출력 한도 대부분 소진 → JSON 잘림
      thinkingConfig: { thinkingBudget: 0 },
    },
    safetySettings: [
      { category: 'HARM_CATEGORY_HARASSMENT',        threshold: 'BLOCK_NONE' },
      { category: 'HARM_CATEGORY_HATE_SPEECH',       threshold: 'BLOCK_NONE' },
      { category: 'HARM_CATEGORY_SEXUALLY_EXPLICIT', threshold: 'BLOCK_NONE' },
      { category: 'HARM_CATEGORY_DANGEROUS_CONTENT', threshold: 'BLOCK_NONE' },
    ],
  };

  // HTTP 오류 → 즉시 throw (재시도 없음)
  // 네트워크 오류(fetch 자체 실패) → 1회만 재시도
  for (let attempt = 0; attempt <= 1; attempt++) {
    let res;
    try {
      res = await fetch(url, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(body),
      });
    } catch (networkErr) {
      // fetch 자체가 실패(오프라인, CORS 프리플라이트 오류 등)
      if (attempt === 1) throw new Error(`네트워크 오류: ${networkErr.message}`);
      await new Promise(r => setTimeout(r, 1000));
      continue;
    }

    if (!res.ok) {
      // HTTP 오류는 재시도하지 않고 원인을 그대로 전달
      let apiMsg = '';
      try { apiMsg = (await res.json())?.error?.message || ''; } catch (_) {}

      switch (res.status) {
        case 429:
          throw new Error('RATE_LIMIT');
        case 400:
          throw new Error(`잘못된 요청(400): ${apiMsg || '프롬프트 또는 파라미터를 확인하세요.'}`);
        case 403:
          throw new Error('INVALID_API_KEY');
        case 500:
        case 503:
          throw new Error(`Gemini 서버 오류(${res.status}): 잠시 후 다시 시도하세요.`);
        default:
          throw new Error(`HTTP ${res.status}: ${apiMsg || res.statusText}`);
      }
    }

    const json = await res.json();
    const candidate = json?.candidates?.[0];
    const text = candidate?.content?.parts?.[0]?.text;
    const finishReason = candidate?.finishReason || 'UNKNOWN';
    // 토큰 사용량 로그 (디버깅 핵심 — MAX_TOKENS 문제 추적용)
    const usage = json?.usageMetadata;
    const tokenInfo = usage
      ? `입력:${usage.promptTokenCount} / 출력:${usage.candidatesTokenCount} / 합계:${usage.totalTokenCount}`
      : '토큰정보없음';
    console.log(`[Gemini] finishReason: ${finishReason} | 출력길이: ${(text||'').length}자 | 토큰: ${tokenInfo}`);
    if (!text) {
      throw new Error(`응답 없음 (사유: ${finishReason})`);
    }
    return text.trim();
  }
}

/* ──────────────────────────────────────
   3-B. 텍스트 압축 유틸리티
   ─ 긴 자유 텍스트 컬럼(marketer_insight 등)에서
     핵심 키워드만 추출하여 토큰 사용량을 최소화
────────────────────────────────────── */

/**
 * marketer_insight 전용 키워드 압축기
 * ─────────────────────────────────────────────────────────────
 * 입력 예시 (400자):
 *   "[전략적 의도] 와이드 뷰를 통해 거대 보스와의 대립 구도를 선명하게 노출...
 *    [타겟 심리] '작지만 강력한' 히어로들의 부대 단위 전투가 주는 스케일감...
 *    [성과 예측 및 확장] 페이스북/인스타그램 뉴스피드 최적화..."
 *
 * 출력 예시 (25자):
 *   "보스대립·레이드|스케일감|FB최적화"
 *
 * 규칙:
 *   1) [전략적 의도] 섹션 → 동사 제거, 명사구 2개 이내, 각 6자 이내
 *   2) [타겟 심리]   섹션 → 핵심 감정/욕구 키워드 1개, 6자 이내
 *   3) [성과 예측]   섹션 → 매체명 or 지표명 1개, 4자 이내
 *   4) 섹션 구분자: '|'  /  키워드 구분자: '·'
 *   5) 전체 출력 30자 이내 강제 절단
 *
 * @param {string} text - marketer_insight 원문
 * @returns {string}    - 압축된 키워드 문자열 (빈 값이면 '')
 */
function extractInsightKeywords(text) {
  if (!text || typeof text !== 'string') return '';
  const t = text.trim();
  if (t.length <= 30) return t; // 이미 짧으면 그대로

  // ── 섹션별 파싱 ──────────────────────────────────────────
  // PHPH_v4.csv 에서 확인된 두 가지 포맷:
  //   포맷 A: "[전략적 의도] 내용 [타겟 심리] 내용"        → 닫는 ] 이후에 내용
  //   포맷 B: "[전략적 의도 - 내용] - [타겟 심리 - 내용]"  → 대괄호 안에 내용 포함

  const extractSection = (src, sectionName) => {
    // 포맷 A: [섹션명] 내용 (다음 [ 또는 끝까지)
    const patA = new RegExp(
      `\\[${sectionName}[^\\]]*\\]\\s*[-–]?\\s*([^\\[]{2,150})`, 's'
    );
    const mA = src.match(patA);
    if (mA?.[1]?.trim().length > 2) return mA[1].trim();

    // 포맷 B: [섹션명 - 내용] (대괄호 안에 내용 포함)
    const patB = new RegExp(
      `\\[${sectionName}\\s*[-–]\\s*([^\\]]{2,150})\\]`, 's'
    );
    const mB = src.match(patB);
    if (mB?.[1]?.trim().length > 2) return mB[1].trim();

    return '';
  };

  const intentRaw   = extractSection(t, '전략적\\s*의도');
  const psychoRaw   = extractSection(t, '타겟\\s*심리');
  const forecastRaw = extractSection(t, '성과\\s*예측[^\\]]*');

  // ── 핵심 명사구 추출 헬퍼 ────────────────────────────────
  // 전략: 문장에서 핵심 명사성 어구(2~6자)를 앞에서부터 N개 추출
  // 조사/용언 어미/연결어 제거 후 의미 있는 단어만 선별
  const extractKeywords = (raw, maxKw, maxCharPerKw) => {
    if (!raw) return '';

    // 불용어 및 어미 정규화
    const cleaned = raw
      .replace(/\s*[-–]\s*/g, ' ')           // 대시 → 공백
      .replace(/[「」『』《》〈〉\[\]]/g, ' ') // 특수 괄호 제거
      .replace(/[,，、.。!！?？]/g, ' ')       // 문장 부호 → 공백
      .replace(/\s*(을|를|이|가|은|는|의|에|로|으로|과|와|도|만|에서|하여|하고|하는|한|있는|있어|위해|통해|대한|부터|까지|처럼|보다|라는|이라는|이며|이고|이다|했다|합니다|입니다|됩니다|됨|함|할|할수|할때|하기|하면|하며)\s*/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();

    // 의미 있는 단어 추출: 2~6자, 숫자/영문 혼재 허용, 단순 조사 단어 제외
    const words = cleaned
      .split(' ')
      .map(w => w.replace(/[()'"''""]/g, '').trim())
      .filter(w => {
        if (w.length < 2 || w.length > 8) return false;
        // 단독 숫자/조사만인 단어 제외
        if (/^[0-9]+$/.test(w)) return false;
        if (/^[가-힣]{1}$/.test(w)) return false;
        return true;
      });

    // 중복 제거 후 앞에서부터 N개
    const unique = [...new Set(words)].slice(0, maxKw);
    return unique.map(w => w.slice(0, maxCharPerKw)).join('·');
  };

  const kIntent   = extractKeywords(intentRaw,   2, 5); // 전략적 의도: 2단어 × 5자
  const kPsycho   = extractKeywords(psychoRaw,   1, 5); // 타겟 심리:   1단어 × 5자
  const kForecast = extractKeywords(forecastRaw, 1, 4); // 성과 예측:   1단어 × 4자

  // ── 섹션 조합 → 전체 28자 이내 ─────────────────────────
  // 섹션 구분: '|' / 키워드 구분: '·'
  const parts = [kIntent, kPsycho, kForecast].filter(Boolean);

  // 섹션이 하나도 추출 안 된 경우: 원문 앞부분 단어 추출로 폴백
  if (parts.length === 0) {
    return extractKeywords(t, 3, 5) || t.slice(0, 20);
  }

  return parts.join('|').slice(0, 28);
}

/**
 * 범용 텍스트 압축기 — marketer_insight 외 긴 컬럼(hooking_strategy 등)에 사용
 * 쉼표/슬래시로 구분된 열거형 텍스트에서 앞 N개 항목만 추출
 *
 * @param {string} text   - 원문
 * @param {number} maxLen - 최대 출력 길이 (기본 25)
 * @returns {string}
 */
function compressTagText(text, maxLen = 25) {
  if (!text || typeof text !== 'string') return '';
  const t = text.trim();
  if (t.length <= maxLen) return t;

  // 쉼표·슬래시·세미콜론으로 분리된 열거형 처리
  const items = t.split(/[,，/；;]/).map(s => s.trim()).filter(Boolean);
  let out = '';
  for (const item of items) {
    const candidate = out ? out + ',' + item.slice(0, 12) : item.slice(0, 12);
    if (candidate.length > maxLen) break;
    out = candidate;
  }
  return (out || t.slice(0, maxLen));
}

/* ──────────────────────────────────────
   4. 마케팅 분석 프롬프트 빌더
────────────────────────────────────── */
const GeminiPrompts = {

  /**
   * 소재 성과 분석 — 플랜별 슬롯 JSON 출력
   * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   * 플랜별 슬롯 구조:
   *   무료 (1회 호출):
   *     winTags     : 승리 패턴 태그 (1회)
   *   유료 (2회 호출):
   *     winTags / formatGap / lossReason  (1회서)
   *     actionItems / scaleUp / stopNow   (2회서)
   *
   * @param {Array}  highPerf  - 고효율 소재 배열 (상위 N개)
   * @param {Array}  lowPerf   - 저효율 소재 배열 (하위 N개)
   * @param {Object} opts      - { tagCols: string[], context: string, isPaid: boolean }
   */
  scoringInsight(highPerf, lowPerf, opts = {}) {
    const { tagCols = [], context = '', isPaid = false } = opts;

    // ── 플랜별 컬럼 처리 전략 ────────────────────────────────────
    // ★ 무료: marketer_insight 등 INSIGHT_COLS 완전 제외
    //         → 입력 토큰 절반 절감 → 출력 예산 2배 이상 확보
    //         → 태그 컬럼도 8자로 짧게 절단
    // ★ 유료: marketer_insight 원문 최대 200자 포함 → 깊은 인사이트
    //         → 태그 컬럼 20자까지 허용
    const INSIGHT_COLS = new Set([
      'marketer_insight', 'insight', '마케터_인사이트', '마케터인사이트'
    ]);
    const COPY_COLS = new Set([
      'text_analysis_extracted_copy', 'hooking_strategy',
      'text_analysis_core_usp', '추출카피', '카피'
    ]);

    const compressColValue = (col, val) => {
      const v = String(val || '').trim();
      if (!v) return '';

      // ★★ 무료 플랜: INSIGHT_COLS 완전 제외 (토큰 0 소비)
      if (!isPaid && INSIGHT_COLS.has(col)) return '';

      // 유료 플랜: marketer_insight 원문 최대 200자
      if (isPaid && INSIGHT_COLS.has(col)) return v.slice(0, 200);

      // COPY_COLS: 유료 30자 / 무료 15자
      if (COPY_COLS.has(col)) return compressTagText(v, isPaid ? 30 : 15);

      // 일반 태그: 유료 20자 / 무료 8자 (최대한 경량)
      return v.slice(0, isPaid ? 20 : 8);
    };

    // ── 소재 포맷터: 1소재 = 1줄 (최대한 압축) ──────────────────
    // 무료: 소재명 30자, 태그 최대 3개 / 유료: 소재명 35자, 태그 최대 5개
    // ★ nameLen 늘림: 소재명이 '-'/'_'로 끝나면 Gemini가 미완성으로 인식 → 계속 생성 → MAX_TOKENS 조기 소진
    const nameLen = isPaid ? 35 : 30;
    const maxTags = isPaid ? 5 : 3;

    const fmtMat = (m, idx) => {
      const rank  = idx + 1;  // 1-based 순위
      const type  = (m.유형 || m.type || '-').toUpperCase();
      const score = (m.TotalScore || 0).toFixed(1);
      const conv  = Math.round(m.전환 || 0);
      const cpa   = m.CPA > 0 ? Math.round(m.CPA) : 0;
      const ipm   = (m.IPM  || 0).toFixed(3);  // 소수 3자리 (정밀도 향상)
      const roas  = (m.ROAS || 0).toFixed(2);
      // 소재명: key > 소재명 > 파일명 순서, 파일확장자 제거
      // ★ 끝의 '-' 또는 '_' 제거: Gemini가 미완성 토큰으로 인식해 계속 생성 → MAX_TOKENS 조기 소진 버그 방지
      const rawName = (m.key || m.소재명 || m.파일명 || '');
      const name  = rawName.replace(/\.[a-z]{2,4}$/i,'').slice(0, nameLen).replace(/[-_]+$/, '');

      const tags  = tagCols
        .map(col => {
          const compressed = compressColValue(col, m.meta?.[col]);
          return compressed || null;
        })
        .filter(Boolean)
        .slice(0, maxTags)
        .join('/');

      return `${rank}|${type}|${name}|${score}|전${conv}|CPA${cpa}|IPM${ipm}|ROAS${roas}${tags ? '|'+tags : ''}`;
    };

    // BNR / VID 포맷별 집계 (단 1줄 요약)
    const byType = (arr, t) => arr.filter(m => (m.유형||m.type||'').toUpperCase().includes(t));
    const avg    = (arr, f) => arr.length ? (arr.reduce((s,m)=>s+(m[f]||0),0)/arr.length) : null;
    const hBNR = byType(highPerf,'BNR'), hVID = byType(highPerf,'VID');
    const lBNR = byType(lowPerf, 'BNR'), lVID = byType(lowPerf, 'VID');
    const fmtAvg = (v, dec=2) => v !== null ? v.toFixed(dec) : 'N/A';
    const typeSummary =
      `고효율 BNR:${hBNR.length}개 avgIPM:${fmtAvg(avg(hBNR,'IPM'))} avgCPA:${fmtAvg(avg(hBNR,'CPA'),0)}` +
      ` | VID:${hVID.length}개 avgIPM:${fmtAvg(avg(hVID,'IPM'))} avgCPA:${fmtAvg(avg(hVID,'CPA'),0)}\n` +
      `저효율 BNR:${lBNR.length}개 avgIPM:${fmtAvg(avg(lBNR,'IPM'))} avgCPA:${fmtAvg(avg(lBNR,'CPA'),0)}` +
      ` | VID:${lVID.length}개 avgIPM:${fmtAvg(avg(lVID,'IPM'))} avgCPA:${fmtAvg(avg(lVID,'CPA'),0)}`;

    // ── 공통 헤더 ─────────────────────────────────────
    // ★ 역할·출력 규칙을 1줄로 압축 + 마크다운 허용 명시
    const header =
      `퍼포먼스 마케터. CSV소재 분석. JSON만 출력. 값 안에서 **중요어구**=볼드, 줄바꿈=\\n 사용 가능.` +
      (context ? ` [${context}]` : '') + `\n`;

    // ── 데이터 블록 ────────────────────────────────────────────
    // H=고효율, L=저효율, S=유형별요약
    const dataBlock =
      `H: ${highPerf.map(fmtMat).join(' || ')}\n` +
      `L: ${lowPerf.map(fmtMat).join(' || ')}\n` +
      `S: ${typeSummary}`;

    // ── 슬롯별 프롬프트 ─────────────────────────────────────
    // ★ 핵심 설계 무료/유료 완전 분리:
    //   무료: 1회 호출 — winTags 1슬롯만 (rate limit & 토큰 최소화)
    //   유료: 2회 호출 — 전체 6슬롯 + marketer_insight 원문 포함
    const base = header + dataBlock + '\n\n';

    if (isPaid) {
      // ── 유료: 2회 호출, 3슬롯씩 ─────────────────────────────
      const inst1 =
        `\n아래 JSON을 채워서 출력해 (개조식·태그 원인 분석 필수):\n` +
        `- winTags: 고효율 소재 공통 태그 기반 원인 분석. 형식 → \n` +
        `  • **[공통 태그명]** — 이 태그가 성과에 미친 영향 (소재명·IPM·CPA 수치 인용)\n` +
        `  • 최우수/우수 소재의 크리에이티브 공통점 1~2줄\n` +
        `  • 저효율 소재와의 핵심 태그 차이 1줄\n` +
        `- formatGap: BNR/VID 포맷별 성과 차이 개조식 분석. 형식 →\n` +
        `  • **BNR**: avgIPM X.XX / avgCPA XXX — 특징 1줄\n` +
        `  • **VID**: avgIPM X.XX / avgCPA XXX — 특징 1줄\n` +
        `  • 포맷 선택 권고 1줄\n` +
        `- lossReason: 저효율 소재 공통 태그·패턴 분석. 형식 →\n` +
        `  • **[공통 약점 태그/패턴]** — 성과 저하 원인 (소재명·수치 인용)\n` +
        `  • 고효율 소재와 비교한 태그 차이 1줄\n` +
        `{"winTags":"","formatGap":"","lossReason":""}`;
      const inst2 =
        `\n아래 JSON을 채워서 출력해 (개조식, 소재명·수치 필수 인용):\n` +
        `- actionItems: 형식 →\n` +
        `  • **즉시 ON**: 소재명 — 근거 태그·수치 1줄\n` +
        `  • **즉시 OFF**: 소재명 — 저하 원인·수치 1줄\n` +
        `- scaleUp: 예산 확대 우선순위 개조식 →\n` +
        `  • **1순위** 소재명 — 태그 근거·IPM·CPA 수치\n` +
        `  • **2순위** 소재명 — 태그 근거·수치 (있을 경우)\n` +
        `- stopNow: 즉시 중단 소재 개조식 →\n` +
        `  • **중단** 소재명 — 문제 태그·패턴·수치\n` +
        `  • 교체 방향 제안 1줄\n` +
        `{"actionItems":"","scaleUp":"","stopNow":""}`;
      const prompt1 = base + inst1;
      const prompt2 = base + inst2;
      return { prompt1, prompt2, splitMode: 'paid_2call' };
    } else {
      // ── 무료: 1회 호출, winTags 단독 ──────────────────────────
      // ★ 핵심 전략:
      //   - 개조식 + 태그 원인 분석 구조로 출력 품질 향상
      //   - marketer_insight 완전 미포함 (입력 토큰 절감)
      //   - **볼드**, \n 줄바꿈 허용 → 렌더러에서 HTML 변환
      const inst1 =
        `\nJSON winTags를 채워 출력 (다른 텍스트 금지). 개조식·태그 원인 분석으로 작성:\n` +
        `• **[고효율 공통 태그]** — 해당 태그가 성과 우수한 이유 (소재명·IPM·CPA 수치 인용) 2줄\n` +
        `• **포맷 비교** — BNR avgIPM/avgCPA vs VID avgIPM/avgCPA 수치 인용 1줄\n` +
        `• **저효율 차이점** — 고효율 대비 부족한 태그·크리에이티브 요소 1줄\n` +
        `• **즉시 권고** — 소재명 명시 1줄\n` +
        `(줄바꿈은 \\n, 중요 어구는 **볼드** 처리)\n` +
        `{"winTags":""}`;
      const prompt1 = base + inst1;
      return { prompt1, splitMode: 'free_1call' };
    }
  },

  /**
   * 피로도 분석 — 사전 정의형 4-슬롯 JSON 출력
   * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   * 슬롯 구조:
   *   riseReason  : 급등 소재 원인 (100자 이내)
   *   fatigueDiag : 피로도 진단  (100자 이내)
   *   swapTiming  : 교체 타이밍 권고 (80자 이내)
   *   opsAction   : 운영 액션 2가지 (130자 이내)
   *
   * @param {Array}  movers  - 순위 변동이 큰 소재 목록
   * @param {Object} periods - { basePeriod, compPeriod }
   */
  fatigueInsight(movers, periods = {}, opts = {}) {
    const { isPaid = false } = opts;

    // ★ 플랜별 분석 소재 수
    //   무료: 상승/하락 각 3개 → 1회 호출 riseReason에 집중
    //   유료: 상승/하락 각 6개 → 2회 호출, 4슬롯 전체
    const moverSlice = isPaid ? 6 : 3;

    // ── 압축 포맷터: 1줄 CSV + 태그 포함 ──────────────────────────
    // 유료: 소재명 최대 40자 / 무료: 최대 30자
    // ★ meta 태그(hooking, emotion, mechanic 등)를 추가해
    //    태그 기반 원인 분석이 가능하도록 최대 2~3개 핵심 태그 포함
    const nameLen = isPaid ? 40 : 30;
    const fmtMover = (m, i) => {
      const dir   = m.rankChange > 0 ? `▲${m.rankChange}` : `▼${Math.abs(m.rankChange)}`;
      // 소재명: 끝의 '-'/'_' 제거 (Gemini 미완성 토큰 방지)
      const name  = (m.key || '').slice(0, nameLen).replace(/[-_]+$/, '');
      const cpaB  = Math.round(m.baseCPA  || 0).toLocaleString();
      const cpaC  = Math.round(m.compCPA  || 0).toLocaleString();
      const cpaR  = (m.cpaChangeRate > 0 ? '+' : '') + (m.cpaChangeRate||0).toFixed(1);
      const convB = Math.round(m.baseConv  || 0);
      const convC = Math.round(m.compConv  || 0);
      const sB    = (m.baseScore || 0).toFixed(1);
      const sC    = (m.compScore || 0).toFixed(1);
      const fat   = (m.fatigueStatus || '-').slice(0, 8);

      // 태그 추출: meta 객체에서 hooking·emotion·mechanic 최대 3개 (무료 8자, 유료 15자)
      const tagLen = isPaid ? 15 : 8;
      const tagKeys = ['hooking', 'emotion', 'mechanic', 'theme', 'visual'];
      const tags = m.meta
        ? tagKeys
            .map(k => m.meta[k])
            .filter(v => v && String(v).trim())
            .slice(0, isPaid ? 3 : 2)
            .map(v => String(v).slice(0, tagLen))
            .join('/')
        : '';

      return `${i+1}|${dir}위|${name}|피:${fat}|CPA:${cpaB}→${cpaC}(${cpaR}%)|전:${convB}→${convC}|점:${sB}→${sC}${tags ? '|태그:'+tags : ''}`;
    };

    const risers  = movers.filter(m => m.rankChange > 0).slice(0, moverSlice);
    const fallers = movers.filter(m => m.rankChange < 0).slice(0, moverSlice);

    // ── 전체 피로도 트렌드 요약 (무료·유료 공통) ──────────────────
    // 하락 소재 중 CPA 대폭 증가(+20% 이상) 소재를 피로 집중 목록으로 표시
    const tiredList = fallers
      .filter(m => (m.cpaChangeRate || 0) >= 20)
      .map(m => `${(m.key||'').slice(0, 20)}(CPA+${(m.cpaChangeRate||0).toFixed(1)}%)`)
      .join(', ');
    const tiredSummary = tiredList
      ? `★피로집중: ${tiredList}`
      : '';

    const dataBlock =
      `기간: ${periods.basePeriod||'기준'} → ${periods.compPeriod||'비교'}\n` +
      `상승(순위|변화|소재명|피로도|CPA변화|전환|점수|태그): ${risers.length ? risers.map(fmtMover).join(' // ') : '없음'}\n` +
      `하락: ${fallers.length ? fallers.map(fmtMover).join(' // ') : '없음'}` +
      (tiredSummary ? `\n${tiredSummary}` : '');

    // 헤더 ───────────────────────────────────────────────────────
    const header =
      `모바일 게임 소재 수명주기 전문가. JSON만 출력. 값 안에서 **중요어구**=볼드, 줄바꿈=\\n 사용 가능.\n`;

    const base = header + dataBlock + '\n\n';

    if (isPaid) {
      // ── 유료: 2회 호출, 4슬롯 전체 ──────────────────────────────
      // ★ riseReason: 급등 원인 → 태그 기반 원인 분석 강화
      // ★ fatigueDiag: CPA 증가 트렌드 + 피로 패턴 진단
      const pInst1 =
        `\n아래 JSON을 채워서 출력해 (개조식·태그 원인 분석 필수):\n` +
        `- riseReason: 급등 소재 분석. 형식 →\n` +
        `  • **[상승 소재명]** CPA [수치]→[수치]([변화율]%) — 공통 태그 기반 급등 원인 2줄\n` +
        `  • 전체 상승 소재의 공통 태그 패턴 1줄 (태그명 인용)\n` +
        `- fatigueDiag: 피로 하락 소재 진단. 형식 →\n` +
        `  • **[하락 소재명]** CPA +[변화율]% → 피로 진단(태그·크리에이티브 취약점 인용) 2줄\n` +
        `  • 전체 CPA 증가 트렌드 요약 1줄 (★피로집중 소재 언급)\n` +
        `{"riseReason":"","fatigueDiag":""}`;
      const pInst2 =
        `\n아래 JSON을 채워서 출력해 (개조식·소재명·수치 인용 필수):\n` +
        `- swapTiming: 교체 타이밍 판단 기준. 형식 →\n` +
        `  • **즉시 교체**: 소재명 — CPA·전환 수치 기반 근거 1줄\n` +
        `  • **모니터링**: 소재명 — 경고 기준 수치 1줄\n` +
        `- opsAction: 운영 액션 (태그 기반 신소재 방향 포함). 형식 →\n` +
        `  • **ON 확대**: 소재명 — 성공 태그·IPM·CPA 근거 1줄\n` +
        `  • **OFF 실행**: 소재명 — 피로 태그·CPA 증가율 근거 1줄\n` +
        `  • **신소재 방향**: 급등 소재 태그 기반 제작 가이드 1줄\n` +
        `{"swapTiming":"","opsAction":""}`;
      const prompt1 = base + pInst1;
      const prompt2 = base + pInst2;
      return { prompt1, prompt2, splitMode: 'paid_2call' };

    } else {
      // ── 무료: 1회 호출, riseReason 단독 ──────────────────────────
      // ★ 핵심 설계:
      //   ① 급등 원인 = 태그 기반 분석 (hooking·emotion 태그 인용 필수)
      //   ② CPA 증가 트렌드 진단 (★피로집중 소재 명시)
      //   ③ 교체 우선순위 = CPA +% 순으로 소재명 나열
      //   ④ 운영 액션 = 급등 소재 태그를 교체 소재에 적용 방향
      //   ⑤ 신선도 회복 같은 추상적 표현 제외, 수치·태그 필수
      const pInst1 =
        `\nJSON riseReason을 채워 출력 (다른 텍스트 금지). 개조식·태그 원인 분석으로 작성:\n` +
        `• **[급등 소재명]** CPA [수치]→[수치]([변화율]%) — 공통 태그([태그명]) 기반 급등 원인 2줄\n` +
        `• **피로 트렌드** — 하락 소재 CPA 증가 현황 요약. ★피로집중 소재 명시, 공통 피로 패턴 1줄\n` +
        `• **즉시 교체 우선순위** — CPA 증가율 순 소재명 나열 + 교체 근거 수치 1줄\n` +
        `• **운영 액션** — 급등 소재 태그([태그명])를 교체 소재에 적용하는 방향 1줄\n` +
        `(줄바꿈=\\n, 중요 어구=**볼드**, 태그명은 반드시 인용, "신선도 회복" 등 추상어 금지)\n` +
        `{"riseReason":""}`;
      const prompt1 = base + pInst1;
      return { prompt1, splitMode: 'free_1call' };
    }
  },

  /**
   * API 키 유효성 테스트용 경량 프롬프트
   */
  testPrompt() {
    return '안녕하세요. 퍼포먼스 마케팅 분석을 도와주세요. "준비 완료"라고만 답하세요.';
  },

  /* ════════════════════════════════════════════════
     군집화 분석 전용 프롬프트 빌더
     ※ 일관성 확보를 위한 설계 원칙:
       - temperature 0.3 고정 (GEMINI_CONFIG.TEMPERATURE)
       - 출력 포맷을 ## 헤더 + 불릿 구조로 명시 고정
       - 숫자 표기 형식 한국식으로 고정 지시
       - 분석 관점(시니어 퍼포먼스 마케터)을 매 프롬프트에 명시
  ════════════════════════════════════════════════ */

  /**
   * 블록 A — 승리 공식 (Winning Logic) 도출
   * @param {Array}  clusters    - 군집화 결과 배열
   * @param {Array}  topTags     - 태그-성과 히트맵 상위 태그 [{tag, avg, cnt}]
   * @param {Array}  lowTags     - 태그-성과 히트맵 하위 태그 [{tag, avg, cnt}]
   * @param {Object} meta        - { gameName, totalMaterials }
   */
  clusteringWinningLogic(clusters, topTags, lowTags, meta = {}) {
    const { gameName = '게임', totalMaterials = 0 } = meta;
    const overallAvg = clusters.length
      ? (clusters.reduce((s, c) => s + c.avgScore * c.materials.length, 0) / totalMaterials).toFixed(1)
      : 0;

    const clusterSummary = clusters.map((c, i) => {
      const bnrCnt = c.materials.filter(m => (m.type||'').toUpperCase().includes('BNR')).length;
      const vidCnt = c.materials.filter(m => (m.type||'').toUpperCase().includes('VID')).length;
      const top1   = c.top3?.[0];
      return [
        `[군집 ${i + 1}] ${c.name}  (등급: ${c.grade} | 평균: ${c.avgScore}점 | 소재: ${c.materials.length}개)`,
        `  핵심 태그: ${(c.topTags || []).slice(0, 6).join(', ')}`,
        `  최고 소재: ${top1 ? top1.name + ' (' + top1.score + '점)' : 'N/A'}`,
        `  BNR: ${bnrCnt}개 / VID: ${vidCnt}개`,
      ].join('\n');
    }).join('\n\n');

    const topTagStr = topTags.slice(0, 12).map(t =>
      `  ${t.tag}: 평균 ${t.avg.toFixed(1)}점 (${t.cnt}개 소재)`
    ).join('\n');

    const lowTagStr = lowTags.slice(0, 6).map(t =>
      `  ${t.tag}: 평균 ${t.avg.toFixed(1)}점 (${t.cnt}개 소재)`
    ).join('\n');

    return `당신은 글로벌 게임사의 시니어 퍼포먼스 마케터이자 데이터 사이언티스트입니다.
광고 소재의 태그 데이터와 매체 성과 지표를 결합하여 '승리 공식(Winning Logic)'을 도출하는 것이 임무입니다.

[분석 대상]
게임: ${gameName} | 전체 소재: ${totalMaterials}개 | 군집: ${clusters.length}개 | 전체 평균 점수: ${overallAvg}점

[군집별 성과 요약]
${clusterSummary}

[태그-성과 히트맵 — 상위 태그]
${topTagStr}

[태그-성과 히트맵 — 하위 태그]
${lowTagStr}

위 데이터를 분석하여 아래 형식으로 한국어로 응답하세요.
출력 형식을 반드시 준수하고, 각 항목은 구체적인 태그명·수치를 인용하세요.
숫자는 한국 형식(쉼표 구분)으로 표기하고, 전체 응답은 700자 이내로 작성하세요.

## 🚀 Scale-up 전략
유지 및 확장해야 할 태그 조합과 이유 — 불릿 2~3개, 태그명·점수 수치 필수 인용

## 🔄 Pivot 전략
보강하거나 새로 시도해야 할 크리에이티브 방향 — 불릿 2~3개, 구체적 제작 가이드 포함

## ⛔ Exit 전략
성과가 낮아 제작·예산을 중단해야 할 패턴 — 불릿 1~2개, 근거 수치 포함

## 🏷️ 핵심 태그 성과 가중치
- 승리 태그 상위 3개: 태그명과 평균 점수를 함께 제시
- 손실 태그 상위 2개: 태그명과 평균 점수를 함께 제시`;
  },

  /**
   * 블록 B — 군집별 심층 맥락 분석
   * @param {Array} topClusters - 상위 N개 군집 배열 (전체 or 상위 3)
   * @param {number} overallAvg - 전체 소재 평균 점수
   */
  clusteringDeepDive(topClusters, overallAvg) {
    const clusterDetail = topClusters.map((c, i) => {
      const mats = (c.materials || []).slice(0, 8);
      const bnrMats = mats.filter(m => (m.type||'').toUpperCase().includes('BNR'));
      const vidMats = mats.filter(m => (m.type||'').toUpperCase().includes('VID'));
      const bnrAvg  = bnrMats.length ? (bnrMats.reduce((s, m) => s + m.score, 0) / bnrMats.length).toFixed(1) : 'N/A';
      const vidAvg  = vidMats.length ? (vidMats.reduce((s, m) => s + m.score, 0) / vidMats.length).toFixed(1) : 'N/A';
      const worst   = [...(c.materials || [])].sort((a, b) => a.score - b.score)[0];
      const best    = c.top3?.[0];

      const matList = mats.map(m =>
        `    · ${m.name} | ${m.type || '-'} | ${m.score}점 | 전환:${(m.전환||0).toLocaleString()} | CPA:${m.CPA > 0 ? Math.round(m.CPA).toLocaleString() + '원' : '-'} | 태그: ${(m.topTags||[]).slice(0,4).join(', ')}`
      ).join('\n');

      return [
        `═══ 군집 ${i + 1}: ${c.name} ═══`,
        `등급: ${c.grade} | 평균: ${c.avgScore}점 | 소재: ${c.materials.length}개 | 전체 평균 대비: ${c.avgScore > overallAvg ? '+' : ''}${(c.avgScore - overallAvg).toFixed(1)}점`,
        `핵심 태그: ${(c.topTags || []).slice(0, 6).join(', ')}`,
        `BNR 평균: ${bnrAvg}점 (${bnrMats.length}개) / VID 평균: ${vidAvg}점 (${vidMats.length}개)`,
        `최고 소재: ${best ? best.name + ' (' + best.score + '점)' : 'N/A'}`,
        `최저 소재: ${worst ? worst.name + ' (' + worst.score + '점)' : 'N/A'}`,
        `소재 목록:`,
        matList,
      ].join('\n');
    }).join('\n\n');

    return `당신은 광고 소재의 시각적·청각적 맥락 데이터를 실제 매체 성과와 결합하여 Winning Logic을 도출하는 시니어 퍼포먼스 마케터입니다.

[전체 평균 점수: ${overallAvg.toFixed(1)}점]

[군집별 상세 데이터]
${clusterDetail}

위 데이터를 분석하여 아래 형식으로 한국어로 응답하세요.
출력 형식을 반드시 준수하고, 각 항목은 구체적인 소재명·태그·수치를 인용하세요.
숫자는 한국 형식(쉼표 구분)으로 표기하고, 전체 응답은 750자 이내로 작성하세요.

## 🔬 군집별 마케팅 맥락 해석
각 군집의 태그 조합이 어떤 마케팅 원리로 이 성과를 만들었는지 설명 — 군집당 2문장, 태그명 필수 인용

## ⚔️ 성패 소재 결정적 차이
동일 군집 내 최고 vs 최저 소재의 태그·지표 차이로 본 성패 분기점 — 군집당 1항목

## 📱 BNR vs VID 유형별 최적화 포인트
배너와 동영상의 성과 차이 분석 및 각 유형별 강화 방향 — 불릿 2~3개`;
  },

  /**
   * 블록 C — 소재별 1줄 AI 코멘트 (JSON 배열 반환)
   * @param {Array} materials - 소재 배열 [{name, type, score, grade, 전환, CPA, topTags, clusterName}]
   */
  clusteringMaterialComment(materials) {
    const matList = materials.map((m, i) => {
      const cpa = m.CPA > 0 ? Math.round(m.CPA).toLocaleString() + '원' : '-';
      return `${i + 1}. ${m.name} | ${m.type || '-'} | ${m.score}점(${m.grade}등급) | 전환:${(m.전환||0).toLocaleString()} | CPA:${cpa} | 군집:[${m.clusterName || '-'}] | 태그:${(m.topTags||[]).slice(0,3).join(',')}`;
    }).join('\n');

    return `당신은 모바일 게임 광고 소재 분석 전문가입니다.
아래 소재 목록의 각 소재에 대해, 성과 특이점 또는 개선/확장 힌트를 한국어 1줄(최대 35자)로 작성하세요.
반드시 JSON 배열 형식으로만 응답하고, 다른 설명 텍스트는 절대 포함하지 마세요.

[소재 목록]
${matList}

응답 형식 (JSON 배열만):
[
  {"idx": 1, "comment": "여기에 1줄 코멘트"},
  {"idx": 2, "comment": "여기에 1줄 코멘트"}
]`;
  },
};

/* ──────────────────────────────────────
   5. UI 렌더링 헬퍼 (공통)
────────────────────────────────────── */

/**
 * 마크다운 → HTML 변환 (## 헤더, ** 볼드, - 불릿)
 */
function geminiMarkdownToHtml(md) {
  if (!md) return '';
  return md
    .replace(/^## (.+)$/gm, '<h4 class="gai-section-title">$1</h4>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^[-•] (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>\n?)+/g, s => `<ul class="gai-list">${s}</ul>`)
    .replace(/\n{2,}/g, '</p><p class="gai-para">')
    .replace(/^(?!<[hul])(.+)$/gm, (line) => line.trim() ? `<p class="gai-para">${line}</p>` : '')
    .replace(/<p class="gai-para"><\/p>/g, '');
}

/**
 * ══════════════════════════════════════════════════════════
 *  사전 정의형 6-슬롯 인사이트 카드 렌더러 (소재 성과 분석용)
 *  parseScoringSlots(raw) → { winTags, formatGap, lossReason,
 *                              actionItems, scaleUp, stopNow }
 * ══════════════════════════════════════════════════════════
 */
/**
 * JSON 정제 공통 유틸
 *  1) 코드펜스 제거
 *  2) 잘린 JSON 복원 시도 (마지막 완성된 키-값 쌍까지만)
 *  3) 제어문자 정리
 */
/**
 * JSON 추출 및 복원 유틸
 * ────────────────────────────────────────────────────────
 * 핵심 전략: 코드펜스 정규식으로 내용을 지우지 않고,
 *   "{" 첫 등장 위치부터 슬라이스하여 JSON 만 추출한다.
 *   잘린 경우 완성된 마지막 키:값 쌍 뒤에 "}" 를 붙여 복원.
 */
function _cleanAndRepairJson(raw) {
  if (!raw || typeof raw !== 'string') return '{}';

  // 제어문자 제거 (탭·줄바꿈은 유지)
  let s = raw.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '');

  // ── Step 1: "{" 첫 위치부터 추출 ───────────────────────
  const start = s.indexOf('{');
  if (start === -1) return s;          // JSON 자체가 없으면 원본 반환
  s = s.slice(start);

  // ── Step 2: 닫는 "}" 위치까지 자르기 ──────────────────
  const end = s.lastIndexOf('}');
  if (end !== -1) s = s.slice(0, end + 1);

  // 완전한 JSON이면 그대로 반환
  try { JSON.parse(s); return s; } catch(_) {}

  // ── Step 3: 잘린 JSON 다단계 복원 ────────────────────
  // 전략 A: 마지막 완성된 "key": "value", 패턴 뒤에서 닫기
  const lastComma = s.lastIndexOf('",');
  if (lastComma > 0) {
    const repaired = s.slice(0, lastComma + 1) + '\n}';
    try { JSON.parse(repaired); return repaired; } catch(_) {}
  }

  // 전략 B: 마지막 완성된 "key": "value" (쉼표 없음, 마지막 키)
  const lastQuote = s.lastIndexOf('"');
  if (lastQuote > 0) {
    const repaired = s.slice(0, lastQuote + 1) + '\n}';
    try { JSON.parse(repaired); return repaired; } catch(_) {}
  }

  // 전략 C: 잘린 마지막 값을 "..." 로 닫고 복원
  // "key": "미완성 텍스트 → "key": "미완성 텍스트..."  + }
  const truncMatch = s.match(/("(\w+)"\s*:\s*"[^"]{0,1200})$/);
  if (truncMatch) {
    const repaired = s.slice(0, truncMatch.index + truncMatch[1].length) + '…"\n}';
    try { JSON.parse(repaired); return repaired; } catch(_) {}
  }

  // 전략 D: 정규식으로 완성된 키:값 쌍만 수집해 재조립
  const pairs = [...s.matchAll(/"(\w+)"\s*:\s*"((?:[^"\\]|\\.)*)"/g)];
  if (pairs.length > 0) {
    const rebuilt = '{\n' + pairs.map(p => `  "${p[1]}": "${p[2]}"`).join(',\n') + '\n}';
    try { JSON.parse(rebuilt); return rebuilt; } catch(_) {}
  }

  // 전략 E: 배열 응답 처리 (Gemini가 ["값1","값2"] 형태로 응답하는 경우)
  const arrMatch = s.match(/\[([^\]]+)\]/);
  if (arrMatch) return `{"text":"${arrMatch[1].replace(/"/g,"'").slice(0,200)}"}`;

  return s;
}

function parseScoringSlots(raw) {
  const KEYS = ['winTags','formatGap','lossReason','actionItems','scaleUp','stopNow'];

  // ── 시도 1: JSON 추출·복원 후 파싱 ────────────────────
  const cleaned = _cleanAndRepairJson(raw);
  try {
    const obj = JSON.parse(cleaned);
    if (KEYS.some(k => k in obj)) {
      // 배열 값 → 문자열로 변환 (Gemini가 [...] 배열로 응답하는 경우 대비)
      const normalized = {};
      KEYS.forEach(k => {
        if (!(k in obj)) return;
        normalized[k] = Array.isArray(obj[k]) ? obj[k].join(' ') : String(obj[k] ?? '');
      });
      return normalized;
    }
  } catch(_) {}

  // ── 시도 2: 정규식으로 개별 키:값 직접 추출 ──────────
  // 문자열 값: "key": "value..."
  // 배열 값:   "key": ["value..."]
  const result = {};
  KEYS.forEach(k => {
    // ① 완전한 문자열 값
    let m = raw.match(new RegExp(`"${k}"\\s*:\\s*"((?:[^"\\\\]|\\\\.)*)"`, 's'));
    if (m) { result[k] = m[1]; return; }

    // ② 배열 값 (["..."] 또는 ["...", "..."])
    m = raw.match(new RegExp(`"${k}"\\s*:\\s*\\[([^\\]]{1,1200})`, 's'));
    if (m) {
      // 배열 내 문자열 추출
      const inner = m[1].replace(/^"/, '').replace(/"$/, '');
      result[k] = inner.replace(/",\s*"/g, ' ').trim();
      return;
    }

    // ③ 잘린 문자열 값 (닫는 " 없음) — 1200자까지 허용 (기존 500 → 1200)
    m = raw.match(new RegExp(`"${k}"\\s*:\\s*"([^"]{0,1200})`, 's'));
    if (m) { result[k] = m[1].trimEnd() + '…(잘림)'; return; }
  });
  if (Object.keys(result).length > 0) return result;

  return null;
}

/**
 * 슬롯 텍스트 → HTML 안전 렌더링
 * - XSS 방지 이스케이프
 * - 줄바꿈 → <br>
 * - '…(잘림)' 포함 시 ⚠️ 배지 표시
 * - 값이 없으면 null 반환 → 카드 숨김
 */
/**
 * 슬롯 텍스트 → HTML 렌더링
 * ─────────────────────────────────────────────────────────
 * 지원 마크다운:
 *   **텍스트**   → <strong> 볼드
 *   \n (리터럴 백슬래시n 또는 실제 줄바꿈) → <br>
 *   • 로 시작하는 줄 → 불릿 아이템 스타일
 * XSS 방지: &, <, > 이스케이프 (마크다운 처리 전 원본 기준)
 */
function _slotText(val, slotKey) {
  if (!val || String(val).trim() === '') return null; // null = 카드 숨김

  const str = String(val);
  const isTruncated = str.includes('…(잘림)');

  // ── 마크다운 → HTML 변환 파이프라인 ────────────────────────
  let out = str;

  // 1) 리터럴 \n (백슬래시+n) → 실제 줄바꿈 통일
  out = out.replace(/\\n/g, '\n');

  // 2) XSS 이스케이프 (& → &amp; 먼저, < > 순서대로)
  //    단, **...** 볼드 마커는 이스케이프 이후 처리하므로 ** 자체는 그대로
  out = out
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // 3) **텍스트** → <strong>텍스트</strong> (볼드)
  out = out.replace(/\*\*([^*\n]+?)\*\*/g, '<strong>$1</strong>');

  // 4) 줄 단위 처리: • 불릿 → 스타일 적용, 일반 줄 → <br>
  const lines = out.split('\n');
  const htmlLines = lines.map((line, i) => {
    const trimmed = line.trim();
    if (!trimmed) return i === 0 ? '' : '<br>';          // 빈 줄
    // 불릿 라인: '•', '-', '▸', '▪' 로 시작
    if (/^[•\-▸▪◆]/.test(trimmed)) {
      return `<div class="gai-bullet">${trimmed}</div>`;
    }
    // 첫 줄이 아니면 앞에 <br> 추가 (단락 구분)
    return (i > 0 ? '<br>' : '') + trimmed;
  });
  out = htmlLines.join('');

  if (!isTruncated) return out;

  // 잘린 경우: 잘림 배지 추가
  const mainText = out.replace('…(잘림)', '…').replace(/…$/, '').trimEnd();
  return `${mainText}<br><span class="gai-truncate-badge" style="font-size:10px;color:#92400e;background:#fef3c7;padding:2px 6px;border-radius:4px;margin-top:4px;display:inline-block;">⚠️ 응답 일부 잘림 — 🔄 재분석하면 더 완전한 결과</span>`;
}

function buildScoringSlotCards(slots) {
  const defs = [
    { key: 'winTags',     icon: '🏷️', title: '승리 패턴 태그',   color: '#10b981', bg: '#ecfdf5' },
    { key: 'formatGap',   icon: '📊', title: '포맷별 성과 격차', color: '#3b82f6', bg: '#eff6ff' },
    { key: 'lossReason',  icon: '⚠️', title: '효율 하락 원인',   color: '#f59e0b', bg: '#fffbeb' },
    { key: 'actionItems', icon: '⚡', title: '즉시 실행 액션',   color: '#8b5cf6', bg: '#f5f3ff' },
    { key: 'scaleUp',     icon: '🚀', title: '스케일업 후보',    color: '#E8003D', bg: '#fff1f2' },
    { key: 'stopNow',     icon: '🛑', title: '중단 권고',        color: '#6b7280', bg: '#f9fafb' },
  ];

  // 값이 있는 슬롯만 필터링
  const activeDefs = defs.filter(d => {
    const v = slots[d.key];
    return v && String(v).trim() !== '';
  });

  if (activeDefs.length === 0) {
    return '<p style="color:#6b7280;font-size:13px;padding:8px 0;">인사이트 데이터가 없습니다.</p>';
  }

  // 활성 슬롯 수에 따라 그리드 컬럼 동적 결정
  const cols = activeDefs.length >= 4 ? 3 : activeDefs.length >= 2 ? 2 : 1;
  const totalSlots = defs.length;
  const missingCount = totalSlots - activeDefs.length;
  const hasTruncated = activeDefs.some(d => (slots[d.key] || '').includes('…(잘림)'));

  // 요약 바 문구
  const summaryParts = [];
  if (activeDefs.length < totalSlots) {
    summaryParts.push(`📌 ${activeDefs.length}/${totalSlots}개 인사이트 생성됨`);
    summaryParts.push(`(${missingCount}개 항목은 데이터 부족으로 생략)`);
  } else {
    summaryParts.push(`✅ 전체 ${totalSlots}개 인사이트 생성`);
  }
  if (hasTruncated) {
    summaryParts.push(`· ⚠️ 일부 내용이 잘렸습니다`);
  }

  const retryBtn = (missingCount > 0 || hasTruncated)
    ? `<button class="gai-retry-btn" onclick="runScoringAIInsight()" title="재분석하면 누락된 슬롯을 복구할 수 있습니다">🔄 재분석</button>`
    : '';

  const cardHtmlArr = activeDefs.map(d => {
    const html = _slotText(slots[d.key], d.key);
    if (!html) return ''; // null이면 카드 자체 제거 (이중 방어)
    return `
        <div class="gai-slot-card" style="border-left:4px solid ${d.color};background:${d.bg};">
          <div class="gai-slot-header">
            <span class="gai-slot-icon">${d.icon}</span>
            <span class="gai-slot-title" style="color:${d.color};">${d.title}</span>
          </div>
          <div class="gai-slot-body">${html}</div>
        </div>`;
  }).filter(Boolean);

  if (cardHtmlArr.length === 0) {
    return '<p style="color:#6b7280;font-size:13px;padding:8px 0;">인사이트 데이터가 없습니다.</p>';
  }

  return `
    <div class="gai-slot-grid" style="grid-template-columns:repeat(${cols},1fr);">
      ${cardHtmlArr.join('')}
    </div>
    <div class="gai-slot-summary">
      <span>${summaryParts.join(' ')}</span>
      ${retryBtn}
    </div>`;
}

/**
 * 사전 정의형 4-슬롯 인사이트 카드 렌더러 (피로도 분석용)
 */
function parseFatigueSlots(raw) {
  const KEYS = ['riseReason','fatigueDiag','swapTiming','opsAction'];

  // ── 시도 1: JSON 추출·복원 후 파싱 ────────────────────
  const cleaned = _cleanAndRepairJson(raw);
  try {
    const obj = JSON.parse(cleaned);
    if (KEYS.some(k => k in obj)) {
      const normalized = {};
      KEYS.forEach(k => {
        if (!(k in obj)) return;
        normalized[k] = Array.isArray(obj[k]) ? obj[k].join(' ') : String(obj[k] ?? '');
      });
      return normalized;
    }
  } catch(_) {}

  // ── 시도 2: 정규식으로 개별 키:값 직접 추출 ──────────
  const result = {};
  KEYS.forEach(k => {
    // ① 완전한 문자열 값
    let m = raw.match(new RegExp(`"${k}"\\s*:\\s*"((?:[^"\\\\]|\\\\.)*)"`, 's'));
    if (m) { result[k] = m[1]; return; }

    // ② 배열 값
    m = raw.match(new RegExp(`"${k}"\\s*:\\s*\\[([^\\]]{1,1200})`, 's'));
    if (m) {
      const inner = m[1].replace(/^"/, '').replace(/"$/, '');
      result[k] = inner.replace(/",\s*"/g, ' ').trim();
      return;
    }

    // ③ 잘린 문자열 값 — 1200자까지 허용 (기존 500 → 1200)
    m = raw.match(new RegExp(`"${k}"\\s*:\\s*"([^"]{0,1200})`, 's'));
    if (m) { result[k] = m[1].trimEnd() + '…(잘림)'; return; }
  });
  if (Object.keys(result).length > 0) return result;

  return null;
}

function buildFatigueSlotCards(slots) {
  const defs = [
    { key: 'riseReason',  icon: '📈', title: '급등 소재 원인',   color: '#10b981', bg: '#ecfdf5' },
    { key: 'fatigueDiag', icon: '📉', title: '피로도 진단',      color: '#ef4444', bg: '#fef2f2' },
    { key: 'swapTiming',  icon: '⏱️', title: '교체 타이밍 기준', color: '#f59e0b', bg: '#fffbeb' },
    { key: 'opsAction',   icon: '🔄', title: '운영 액션',        color: '#8b5cf6', bg: '#f5f3ff' },
  ];

  // 값이 있는 슬롯만 필터링
  const activeDefs = defs.filter(d => {
    const v = slots[d.key];
    return v && String(v).trim() !== '';
  });

  if (activeDefs.length === 0) {
    return '<p style="color:#6b7280;font-size:13px;padding:8px 0;">인사이트 데이터가 없습니다.</p>';
  }

  const cols = activeDefs.length >= 3 ? 2 : activeDefs.length;
  const totalSlots = defs.length;
  const missingCount = totalSlots - activeDefs.length;
  const hasTruncated = activeDefs.some(d => (slots[d.key] || '').includes('…(잘림)'));

  const summaryParts = [];
  if (activeDefs.length < totalSlots) {
    summaryParts.push(`📌 ${activeDefs.length}/${totalSlots}개 인사이트 생성됨`);
    summaryParts.push(`(${missingCount}개 항목은 데이터 부족으로 생략)`);
  } else {
    summaryParts.push(`✅ 전체 ${totalSlots}개 인사이트 생성`);
  }
  if (hasTruncated) summaryParts.push(`· ⚠️ 일부 내용이 잘렸습니다`);

  const retryBtn = (missingCount > 0 || hasTruncated)
    ? `<button class="gai-retry-btn" onclick="runFatigueAIInsight()" title="재분석">🔄 재분석</button>`
    : '';

  const fCardHtmlArr = activeDefs.map(d => {
    const html = _slotText(slots[d.key], d.key);
    if (!html) return '';
    return `
        <div class="gai-slot-card" style="border-left:4px solid ${d.color};background:${d.bg};">
          <div class="gai-slot-header">
            <span class="gai-slot-icon">${d.icon}</span>
            <span class="gai-slot-title" style="color:${d.color};">${d.title}</span>
          </div>
          <div class="gai-slot-body">${html}</div>
        </div>`;
  }).filter(Boolean);

  if (fCardHtmlArr.length === 0) {
    return '<p style="color:#6b7280;font-size:13px;padding:8px 0;">인사이트 데이터가 없습니다.</p>';
  }

  return `
    <div class="gai-slot-grid gai-slot-grid-4" style="grid-template-columns:repeat(${cols},1fr);">
      ${fCardHtmlArr.join('')}
    </div>
    <div class="gai-slot-summary">
      <span>${summaryParts.join(' ')}</span>
      ${retryBtn}
    </div>`;
}
/**
 * AI 인사이트 박스 HTML 생성
 * @param {string} content   - 렌더링할 HTML 문자열 (슬롯 카드 or 마크다운 변환)
 * @param {string} status    - 'loading' | 'done' | 'error'
 * @param {string} errorMsg  - 에러 메시지 (status==='error' 일 때)
 * @param {string} boxType   - 'scoring' | 'fatigue' | '' (슬롯 타입 구분)
 */
function buildGeminiBox(content = '', status = 'done', errorMsg = '', boxType = '') {
  if (status === 'loading') {
    return `
      <div class="gai-box gai-loading">
        <div class="gai-header">
          <span class="gai-icon">✨</span>
          <span class="gai-title">Gemini AI 분석 중...</span>
          <span class="gai-spinner"></span>
        </div>
        <p class="gai-hint">Gemini 2.5 Flash가 데이터를 분석하고 있습니다</p>
      </div>`;
  }
  if (status === 'error') {
    let friendly, detail = '';
    if (errorMsg === 'RATE_LIMIT') {
      friendly = '⏳ 분당 요청 한도 초과(429)';
      detail   = '무료 Gemini API는 분당 15회 한도입니다. 1분 후 다시 시도하세요.';
    } else if (errorMsg === 'INVALID_API_KEY') {
      friendly = '🔑 API 키 오류(403)';
      detail   = 'API 키가 유효하지 않습니다. 네비게이션의 <strong>✨ AI 설정</strong>에서 재입력하세요.';
    } else if (errorMsg === 'API_KEY_MISSING') {
      friendly = '🔑 API 키 미설정';
      detail   = '네비게이션의 <strong>✨ AI 설정</strong>을 클릭해 키를 입력하세요.';
    } else {
      friendly = '❌ 분석 실패';
      detail   = errorMsg;
    }
    return `
      <div class="gai-box gai-error">
        <div class="gai-header">
          <span class="gai-icon">⚠️</span>
          <span class="gai-title">AI 분석 오류 — ${friendly}</span>
        </div>
        <p class="gai-hint">${detail}</p>
      </div>`;
  }
  return `
    <div class="gai-box gai-done">
      <div class="gai-header">
        <span class="gai-icon">✨</span>
        <span class="gai-title">Gemini AI 인사이트</span>
        <span class="gai-badge">Gemini 2.5 Flash</span>
        <span class="gai-plan-badge" style="
          font-size:10px;font-weight:700;padding:2px 7px;border-radius:20px;
          margin-left:4px;
          color:${GeminiKeyManager.isPaid() ? '#7c3aed' : '#d97706'};
          background:${GeminiKeyManager.isPaid() ? '#f5f3ff' : '#fffbeb'};
        ">${GeminiKeyManager.isPaid() ? '💎 유료 Pro' : '🆓 무료'}</span>
      </div>
      <div class="gai-body gai-body-slots">${content}</div>
    </div>`;
}

/* ──────────────────────────────────────
   6. API 키 설정 모달 HTML 빌더
────────────────────────────────────── */
function buildGeminiKeyModal() {
  return `
  <div id="geminiKeyModal" class="gai-modal-overlay" style="display:none;" onclick="if(event.target===this)closeGeminiModal()">
    <div class="gai-modal" style="max-width:480px;">
      <div class="gai-modal-header">
        <span style="font-size:22px;">✨</span>
        <h3>Gemini API 키 설정</h3>
        <button onclick="closeGeminiModal()" class="gai-modal-close">✕</button>
      </div>
      <div class="gai-modal-body">

        <!-- ── API 키 입력 ────────────────────────── -->
        <div style="margin-bottom:16px;">
          <label style="font-size:12px;font-weight:600;color:#374151;display:block;margin-bottom:6px;">
            API 키
            <a href="https://aistudio.google.com/apikey" target="_blank"
               style="font-weight:400;color:#6366f1;margin-left:6px;font-size:11px;">
              Google AI Studio에서 발급 ↗
            </a>
          </label>
          <input type="password" id="geminiKeyInput" placeholder="AIza..."
            style="width:100%;padding:10px 14px;border:1.5px solid #d1d5db;border-radius:8px;
                   font-size:13px;font-family:monospace;box-sizing:border-box;"
            value="${GeminiKeyManager.get()}">
        </div>

        <!-- ── 플랜 선택 토글 ─────────────────────── -->
        <div style="margin-bottom:16px;">
          <label style="font-size:12px;font-weight:600;color:#374151;display:block;margin-bottom:8px;">
            API 플랜 선택
          </label>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;" id="planToggleGroup">
            <!-- 무료 플랜 -->
            <label id="planCard_free" onclick="_selectPlan('free')"
              style="cursor:pointer;border-radius:10px;border:2px solid #e5e7eb;padding:12px 10px;
                     transition:all .15s;position:relative;background:#fff;">
              <input type="radio" name="geminiPlan" value="free" id="planRadio_free"
                style="position:absolute;opacity:0;width:0;height:0;">
              <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
                <span style="font-size:15px;">🆓</span>
                <span style="font-size:13px;font-weight:700;color:#374151;">무료 플랜</span>
              </div>
              <div style="font-size:11px;color:#6b7280;line-height:1.55;">
                분당 15req · 일 500req<br>
                <span style="color:#d97706;">▸ marketer_insight 미전송 (입력 절감 → 출력 극대화)</span><br>
                <span style="color:#d97706;">▸ 소재 최대 3개 · <strong>1회 호출</strong></span><br>
                <span style="color:#d97706;">▸ 핵심 인사이트 1슬롯만 제공</span>
              </div>
              <div class="gai-plan-check" id="planCheck_free"
                style="display:none;position:absolute;top:8px;right:8px;
                       width:18px;height:18px;border-radius:50%;
                       background:#10b981;color:#fff;font-size:11px;
                       display:none;align-items:center;justify-content:center;">✓</div>
            </label>
            <!-- 유료 플랜 -->
            <label id="planCard_paid" onclick="_selectPlan('paid')"
              style="cursor:pointer;border-radius:10px;border:2px solid #e5e7eb;padding:12px 10px;
                     transition:all .15s;position:relative;background:#fff;">
              <input type="radio" name="geminiPlan" value="paid" id="planRadio_paid"
                style="position:absolute;opacity:0;width:0;height:0;">
              <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
                <span style="font-size:15px;">💎</span>
                <span style="font-size:13px;font-weight:700;color:#374151;">유료 플랜</span>
                <span style="font-size:10px;font-weight:700;color:#7c3aed;
                             background:#f5f3ff;padding:1px 6px;border-radius:20px;">PRO</span>
              </div>
              <div style="font-size:11px;color:#6b7280;line-height:1.55;">
                분당 1,000req · 무제한<br>
                <span style="color:#059669;">▸ marketer_insight 원문 포함 (최대 200자)</span><br>
                <span style="color:#059669;">▸ 소재 최대 5개 · <strong>2회 호출</strong></span><br>
                <span style="color:#059669;">▸ 6슬롯 전체 제공</span>
              </div>
              <div class="gai-plan-check" id="planCheck_paid"
                style="display:none;position:absolute;top:8px;right:8px;
                       width:18px;height:18px;border-radius:50%;
                       background:#7c3aed;color:#fff;font-size:11px;
                       align-items:center;justify-content:center;">✓</div>
            </label>
          </div>

          <!-- 플랜 비교 상세 접기/펼치기 -->
          <details style="margin-top:8px;">
            <summary style="font-size:11px;color:#6366f1;cursor:pointer;list-style:none;
                            display:flex;align-items:center;gap:4px;">
              ▸ 플랜별 AI 인사이트 품질 차이 자세히 보기
            </summary>
            <div style="margin-top:8px;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;font-size:11.5px;">
              <table style="width:100%;border-collapse:collapse;">
                <thead>
                  <tr style="background:#f9fafb;">
                    <th style="padding:7px 10px;text-align:left;font-weight:600;color:#374151;border-bottom:1px solid #e5e7eb;">항목</th>
                    <th style="padding:7px 10px;text-align:center;font-weight:600;color:#374151;border-bottom:1px solid #e5e7eb;">🆓 무료</th>
                    <th style="padding:7px 10px;text-align:center;font-weight:600;color:#7c3aed;border-bottom:1px solid #e5e7eb;">💎 유료</th>
                  </tr>
                </thead>
                <tbody>
                  <tr style="border-bottom:1px solid #f3f4f6;">
                    <td style="padding:6px 10px;color:#6b7280;">marketer_insight</td>
                    <td style="padding:6px 10px;text-align:center;color:#d97706;">미전송<br><span style="font-size:10px;">(입력 토큰 절감→출력 확보)</span></td>
                    <td style="padding:6px 10px;text-align:center;color:#059669;">원문 포함<br><span style="font-size:10px;">(최대 200자)</span></td>
                  </tr>
                  <tr style="border-bottom:1px solid #f3f4f6;">
                    <td style="padding:6px 10px;color:#6b7280;">분석 소재 수</td>
                    <td style="padding:6px 10px;text-align:center;color:#d97706;">최대 3개</td>
                    <td style="padding:6px 10px;text-align:center;color:#059669;">최대 5개</td>
                  </tr>
                  <tr style="border-bottom:1px solid #f3f4f6;">
                    <td style="padding:6px 10px;color:#6b7280;">호출 횟수</td>
                    <td style="padding:6px 10px;text-align:center;color:#d97706;">1회<br><span style="font-size:10px;">(레이트리미트 최소화)</span></td>
                    <td style="padding:6px 10px;text-align:center;color:#059669;">2회<br><span style="font-size:10px;">(3슬롯씩 분할)</span></td>
                  </tr>
                  <tr style="border-bottom:1px solid #f3f4f6;">
                    <td style="padding:6px 10px;color:#6b7280;">소재성과 슬롯</td>
                    <td style="padding:6px 10px;text-align:center;color:#d97706;">1개<br><span style="font-size:10px;">학승패턴 태그만</span></td>
                    <td style="padding:6px 10px;text-align:center;color:#059669;">6개<br><span style="font-size:10px;">전체 인사이트</span></td>
                  </tr>
                  <tr style="border-bottom:1px solid #f3f4f6;">
                    <td style="padding:6px 10px;color:#6b7280;">피로도 슬롯</td>
                    <td style="padding:6px 10px;text-align:center;color:#d97706;">1개<br><span style="font-size:10px;">급등원인 통합</span></td>
                    <td style="padding:6px 10px;text-align:center;color:#059669;">4개<br><span style="font-size:10px;">진단+타이밍+액션</span></td>
                  </tr>
                  <tr style="border-bottom:1px solid #f3f4f6;">
                    <td style="padding:6px 10px;color:#6b7280;">출력 토큰/회</td>
                    <td style="padding:6px 10px;text-align:center;color:#d97706;">800 토큰</td>
                    <td style="padding:6px 10px;text-align:center;color:#059669;">2,000 토큰</td>
                  </tr>
                  <tr>
                    <td style="padding:6px 10px;color:#6b7280;">인사이트 깊이</td>
                    <td style="padding:6px 10px;text-align:center;color:#d97706;">핵심 요약 중심</td>
                    <td style="padding:6px 10px;text-align:center;color:#059669;">마케터 의도 반영</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </details>
        </div>

        <!-- ── 버튼 영역 ──────────────────────────── -->
        <div style="display:flex;gap:8px;">
          <button onclick="saveGeminiKey()"
            style="flex:1;padding:10px;background:#E8003D;color:#fff;border:none;
                   border-radius:8px;font-size:13px;font-weight:700;cursor:pointer;">
            저장 &amp; 테스트
          </button>
          <button onclick="clearGeminiKey()"
            style="padding:10px 16px;background:#f3f4f6;color:#374151;border:none;
                   border-radius:8px;font-size:13px;cursor:pointer;">
            초기화
          </button>
        </div>
        <div id="geminiKeyTestResult" style="margin-top:12px;font-size:13px;min-height:20px;"></div>
      </div>
    </div>
  </div>`;
}

/* ──────────────────────────────────────
   7. 모달 컨트롤러
────────────────────────────────────── */
function openGeminiModal() {
  const m = document.getElementById('geminiKeyModal');
  if (m) {
    m.style.display = 'flex';
    document.getElementById('geminiKeyInput').value = GeminiKeyManager.get();
    document.getElementById('geminiKeyTestResult').textContent = '';
    // 저장된 플랜 반영
    _selectPlan(GeminiKeyManager.getPlan(), false); // false = 저장 없이 UI만 갱신
  }
}

/** 플랜 카드 UI 선택 상태 업데이트
 * @param {'free'|'paid'} plan
 * @param {boolean} [persist=true] - localStorage 저장 여부
 */
function _selectPlan(plan, persist = true) {
  ['free', 'paid'].forEach(p => {
    const card  = document.getElementById(`planCard_${p}`);
    const check = document.getElementById(`planCheck_${p}`);
    if (!card) return;
    const active = (p === plan);
    card.style.border        = active ? `2px solid ${p === 'paid' ? '#7c3aed' : '#10b981'}` : '2px solid #e5e7eb';
    card.style.background    = active ? (p === 'paid' ? '#faf5ff' : '#f0fdf4') : '#fff';
    if (check) check.style.display = active ? 'flex' : 'none';
  });
  if (persist) GeminiKeyManager.setPlan(plan);
  // 현재 플랜 배지 업데이트 (인사이트 박스 헤더)
  _updatePlanBadges(plan);
}

function closeGeminiModal() {
  const m = document.getElementById('geminiKeyModal');
  if (m) m.style.display = 'none';
}

async function saveGeminiKey() {
  const val = document.getElementById('geminiKeyInput').value.trim();
  const resultEl = document.getElementById('geminiKeyTestResult');
  if (!val) { resultEl.innerHTML = '<span style="color:#dc2626;">키를 입력하세요.</span>'; return; }

  resultEl.innerHTML = '<span style="color:#6b7280;">🔄 키 유효성 확인 중...</span>';
  GeminiKeyManager.set(val);

  // ★ 선택된 플랜 저장 (라디오 대신 카드 border 상태로 판별)
  const paidCard = document.getElementById('planCard_paid');
  const isPaidSelected = paidCard?.style.border?.includes('7c3aed');
  GeminiKeyManager.setPlan(isPaidSelected ? 'paid' : 'free');

  try {
    await callGeminiAPI(GeminiPrompts.testPrompt(), { maxTokens: 100 });
    const plan = GeminiKeyManager.getPlan();
    const planLabel = plan === 'paid' ? '💎 유료 Pro' : '🆓 무료';
    resultEl.innerHTML = `<span style="color:#059669;">✅ 연결 성공! 플랜: <strong>${planLabel}</strong> 로 저장되었습니다.</span>`;
    updateGeminiButtonStates();
    setTimeout(closeGeminiModal, 1400);

  } catch (err) {
    const code = err.message;

    if (code === 'RATE_LIMIT') {
      const plan = GeminiKeyManager.getPlan();
      resultEl.innerHTML = `
        <span style="color:#d97706;">
          ⏳ <strong>요청 한도 초과(429)</strong><br>
          키는 저장되었습니다. ${plan === 'paid' ? '유료' : '무료'} 티어는 분당 ${plan === 'paid' ? '1,000회' : '15회'} 한도입니다.<br>
          1분 후 AI 분석 버튼으로 바로 사용하세요.
        </span>`;
      updateGeminiButtonStates();

    } else if (code === 'INVALID_API_KEY') {
      GeminiKeyManager.clear();
      resultEl.innerHTML = '<span style="color:#dc2626;">🔑 유효하지 않은 API 키입니다 (403). <a href="https://aistudio.google.com/apikey" target="_blank">AI Studio</a>에서 키를 재확인하세요.</span>';

    } else {
      resultEl.innerHTML = `<span style="color:#dc2626;">❌ ${code}</span>`;
    }
  }
}

function clearGeminiKey() {
  GeminiKeyManager.clear();
  GeminiKeyManager.clearPlan();
  document.getElementById('geminiKeyInput').value = '';
  document.getElementById('geminiKeyTestResult').innerHTML =
    '<span style="color:#6b7280;">API 키가 초기화되었습니다.</span>';
  _selectPlan('free', false); // UI만 무료로 리셋
  updateGeminiButtonStates();
}

/**
 * 페이지 내 모든 AI 분석 버튼 상태를 키 유무에 따라 업데이트
 */
function updateGeminiButtonStates() {
  const hasKey = GeminiKeyManager.isSet();
  document.querySelectorAll('.gai-trigger-btn').forEach(btn => {
    btn.disabled = false;
    btn.title = hasKey ? 'AI 인사이트 생성' : 'API 키를 먼저 설정하세요';
  });
  document.querySelectorAll('.gai-key-status').forEach(el => {
    el.textContent = hasKey ? '✅ API 키 설정됨' : '🔑 API 키 미설정';
    el.style.color = hasKey ? '#059669' : '#d97706';
  });
  // 플랜 배지 업데이트
  _updatePlanBadges(GeminiKeyManager.getPlan());
}

/**
 * 페이지 내 플랜 배지 텍스트/색상 갱신
 */
function _updatePlanBadges(plan) {
  const isPaid  = (plan === 'paid');
  const label   = isPaid ? '💎 유료 Pro' : '🆓 무료';
  const color   = isPaid ? '#7c3aed' : '#d97706';
  const bg      = isPaid ? '#f5f3ff' : '#fffbeb';
  document.querySelectorAll('.gai-plan-badge').forEach(el => {
    el.textContent     = label;
    el.style.color     = color;
    el.style.background = bg;
  });
}
