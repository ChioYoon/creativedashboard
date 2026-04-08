/**
 * Pepp Heroes – Pipeline Engine v3
 * CSV 파싱 / 데이터 검증 / Total Score 산출 / 군집화 분석
 *
 * ★ 주요 변경사항 (v3)
 *  - 태그 컬럼: 하드코딩 화이트리스트 → CSV 헤더 자동 전수 탐지
 *  - marketer_insight: 자유 문장에서 의미 키워드를 추출해 [MI]접두사 태그로 변환
 *  - 퍼포먼스 수치 컬럼(소재명·유형·전환·비용 등)과 태그 컬럼 자동 분리
 */

// ══════════════════════════════════════════
// 0. 컬럼 분류 상수
// ══════════════════════════════════════════

/** 절대로 태그로 취급하지 않을 퍼포먼스/메타 컬럼 */
const NON_TAG_COLS = new Set([
  // ── 필수 퍼포먼스 컬럼
  '소재명','유형','전환','비용','노출수','클릭수',
  'name','type','conversion','cost','impression','click','ctr','ipm','cpa',
  // ── 링크/URL 계열
  '링크','link','url','image_url','video_url','썸네일',
  '앱 확장 소재',                         // 실제 CSV의 첫 번째 컬럼 (파일명;URL 형식)
  '앱 확장 소재 유형',                     // '가로형 이미지', 'YouTube 동영상' 등
  // ── ID/순번/날짜 계열
  'id','no','index','순번','date','날짜','기간','period',
  '일','일자',                             // 날짜 컬럼
  '투입일',                                // 소재 투입일
  // ── 캠페인/광고그룹 계열
  'campaign','캠페인','ad_set','adset','광고세트','광고그룹',
  // ── 사이즈/포맷 메타
  '사이즈','size','format','포맷','사이즈명',
  // ── 지역/언어 메타
  '언어','language','lang','지역','region','국가','country',
  '시기',                                  // A/B 테스트 시기 구분자
  // ── 비용/수익 계열
  '통화 코드','통화코드','통화','currency','revenue','매출','Revenue',
  // ── 파일명/식별자 계열
  '파일명','filename','file_name',
  // ── marketer_insight 계열은 NON_TAG_COLS에서 제외! (INSIGHT_COL_PATTERNS에서 별도 처리)
  // → plDetectTagColumns에서 insight 컬럼으로 분류 후 키워드 추출
  'remark','비고','note',
  // ── 실제 UA CSV 추가 메타 컬럼
  '유형 (BNR/VID)',                        // 정규화 전 원본 컬럼명
  'audio_elements_bgm',                    // 오디오 on/off 불린값
  'audio_elements_sfx_emphasized',
  'audio_elements_narration',
  'audio_elements_cv',
  'text_analysis_extracted_copy',          // 추출된 카피 (긴 텍스트)
  'title_specific_special_note',           // 특이사항 메모
]);
// ※ USP, Concept 컬럼은 의도적으로 NON_TAG_COLS에 포함하지 않음
//   실제 CSV에서 USP='Character'/'Hooking'/'Mob', Concept='Adventure'/'Combat' 등
//   소재 전략 분류 정보로 군집화에 매우 유용한 태그 신호임.

/** marketer_insight 계열 컬럼명 패턴 */
const INSIGHT_COL_PATTERNS = [
  /marketer[\s_-]?insight/i,
  /마케터[\s_]?인사이트/,
  /insight[\s_]?memo/i,
  /담당자[\s_]?인사이트/,
];

// ══════════════════════════════════════════
// 1. CSV 파싱
// ══════════════════════════════════════════
function plParseCSV(text) {
  const lines = text.trim().split(/\r?\n/);
  if (lines.length < 2) return null;
  const headers = plParseCSVLine(lines[0]);
  const rows = [];
  for (let i = 1; i < lines.length; i++) {
    if (!lines[i].trim()) continue;
    const vals = plParseCSVLine(lines[i]);
    const obj = {};
    headers.forEach((h, idx) => { obj[h.trim()] = (vals[idx] || '').trim(); });
    rows.push(obj);
  }
  const raw = { headers: headers.map(h => h.trim()), rows };
  // ★ 컬럼 정규화 자동 적용 (실제 UA CSV 헤더 → 파이프라인 표준 헤더)
  return plNormalizeColumns(raw);
}

function plParseCSVLine(line) {
  const result = []; let cur = ''; let inQ = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') { if (inQ && line[i+1] === '"') { cur += '"'; i++; } else inQ = !inQ; }
    else if (ch === ',' && !inQ) { result.push(cur); cur = ''; }
    else cur += ch;
  }
  result.push(cur);
  return result;
}

// ══════════════════════════════════════════
// 1-B. 실제 CSV 컬럼 정규화 (헤더 자동 매핑)
// ══════════════════════════════════════════
/**
 * 실제 PH UA CSV의 컬럼명 → 파이프라인 내부 표준 컬럼명으로 정규화
 *
 * 실제 CSV 헤더 예시:
 *   앱 확장 소재, 앱 확장 소재 유형, 캠페인, 광고그룹, 일, 전환, 통화 코드,
 *   비용, 노출수, 클릭수, Revenue, 유형 (BNR/VID), 사이즈, 투입일, 시기,
 *   USP, Concept, 언어, 파일명, 소재명, 링크, hooking_strategy, ...
 *
 * 내부 표준 컬럼 → 실제 CSV 컬럼 매핑 규칙:
 *   소재명  ← '파일명' (BNR/VID) 또는 '소재명' (TXT 폴백)
 *   유형    ← '유형 (BNR/VID)' 또는 '유형'
 *   전환    ← '전환' (이미 일치)
 *   비용    ← '비용' (이미 일치)
 *   노출수  ← '노출수' (이미 일치)
 *   클릭수  ← '클릭수' (이미 일치)
 */
function plNormalizeColumns(parsed) {
  const { headers, rows } = parsed;

  // 헤더 매핑 테이블 (우선순위 순서: 앞쪽이 먼저 매칭)
  const HEADER_MAP = [
    // 유형 컬럼: '유형 (BNR/VID)' 또는 '유형'
    { target: '유형', sources: ['유형', '유형 (BNR/VID)', 'type', '소재유형'] },
    // 전환
    { target: '전환', sources: ['전환', 'conversions', 'conversion', 'installs'] },
    // 비용
    { target: '비용', sources: ['비용', 'cost', 'spend'] },
    // 노출수
    { target: '노출수', sources: ['노출수', 'impressions', 'impression', 'impr'] },
    // 클릭수
    { target: '클릭수', sources: ['클릭수', 'clicks', 'click'] },
  ];

  // 적용할 컬럼 리네이밍 맵 구성
  const renameMap = {};  // 원본 컬럼명 → 내부 표준명
  HEADER_MAP.forEach(({ target, sources }) => {
    if (headers.includes(target)) return; // 이미 표준명이면 패스
    for (const src of sources) {
      if (headers.includes(src)) {
        renameMap[src] = target;
        break;
      }
    }
  });

  // 헤더 정규화
  const newHeaders = headers.map(h => renameMap[h] || h);

  // 소재명 정규화: BNR/VID는 '파일명' 우선, 없으면 '소재명'
  // TXT는 '소재명' 사용
  const typeCol  = renameMap['유형 (BNR/VID)'] ? '유형 (BNR/VID)' :
                   renameMap['유형']             ? renameMap['유형'] :
                   headers.includes('유형')      ? '유형' : '유형 (BNR/VID)';

  const hasFilename = headers.includes('파일명');

  // rows 정규화
  const newRows = rows.map(r => {
    const newR = {};

    // 컬럼명 리네이밍 적용
    Object.keys(r).forEach(k => {
      const mapped = renameMap[k] || k;
      newR[mapped] = r[k];
    });

    // 파일명과 소재명을 모두 보존
    // - '파일명' 컬럼이 있으면 유지
    // - '소재명' 컬럼이 있으면 유지
    // - 둘 다 없으면 빈 값
    if (newR['파일명']) newR['파일명'] = String(newR['파일명']).trim();
    if (newR['소재명']) newR['소재명'] = String(newR['소재명']).trim();
    
    // TXT 행의 경우 파일명이 없을 수 있으므로, 소재명만 있으면 OK
    // BNR/VID는 일반적으로 둘 다 있을 것으로 기대

    // 숫자 컬럼 정규화 (쉼표 제거)
    ['전환', '비용', '노출수', '클릭수'].forEach(col => {
      if (newR[col]) newR[col] = String(newR[col]).replace(/,/g, '').trim();
    });

    return newR;
  });

  // 필수 컬럼이 헤더에 없으면 추가
  if (!newHeaders.includes('소재명')) {
    newHeaders.splice(0, 0, '소재명');
  }
  if (!newHeaders.includes('파일명')) {
    newHeaders.splice(1, 0, '파일명');
  }

  return { headers: newHeaders, rows: newRows, _renameMap: renameMap };
}

// ── 태그 문자열 → 배열 파싱
function plParseTags(raw) {
  if (!raw) return [];
  const cleaned = raw.replace(/^\[|\]$/g, '').replace(/'/g, '').replace(/"/g, '');
  return cleaned.split(',').map(t => t.trim()).filter(t => t.length >= 2);
}

// ══════════════════════════════════════════
// 2. 컬럼 자동 분류 (태그 / 인사이트 / 무시)
// ══════════════════════════════════════════

/**
 * CSV 헤더 전체를 분석해 세 가지 컬럼 그룹을 반환한다.
 *
 * @returns {tagCols}     – 쉼표 구분 태그가 담긴 컬럼
 * @returns {insightCols} – marketer_insight 계열 자유문장 컬럼
 */
/**
 * 컬럼명 기반 메타컬럼 여부 판단 (NON_TAG_COLS에 없더라도 패턴으로 제외)
 * 실제 CSV에서 자주 등장하는 비태그 패턴을 추가로 필터링한다.
 */
const META_COL_PATTERNS = [
  /^(앱[\s_]?확장[\s_]?소재)/i,         // '앱 확장 소재', '앱 확장 소재 유형'
  /소재[\s_]?유형$/,                      // '앱 확장 소재 유형' 등 유형 끝나는 메타
  /(캠페인|광고그룹|광고[\s_]?세트)/,
  /(통화[\s_]?코드|currency)/i,
  /(revenue|매출|수익)/i,
  /(파일[\s_]?명|filename)/i,
  /^(일|일자|날짜|기간|투입일|시기)$/,
  /^(사이즈|size|format|포맷)$/i,
  /^(언어|language|lang|지역|국가|country|region)$/i,
  /^(usp|concept)$/i,
  /^(no|id|index|순번)$/i,
  /^(link|url|링크)$/i,
  /(image_url|video_url|썸네일)/i,
  /^audio_elements_/i,                   // 오디오 on/off 불린 컬럼
  /^text_analysis_extracted/i,           // 추출된 카피 전문
  /_special_note$/i,                     // 특이사항 메모
  /^(title_specific_special)/i,
];

function plDetectTagColumns(headers, rows) {
  const tagCols     = [];
  const insightCols = [];

  // BNR/VID 행만 샘플링 (TXT는 태그 없음)
  const tagRows = rows.filter(r => ['BNR','VID'].includes((r['유형']||'').toUpperCase()));
  const sampleRows = (tagRows.length > 0 ? tagRows : rows).slice(0, Math.min(rows.length, 40));

  headers.forEach(col => {
    const colLower = col.toLowerCase().trim();

    // 1) NON_TAG_COLS 직접 매칭 (대소문자 무관)
    if (NON_TAG_COLS.has(col) || NON_TAG_COLS.has(colLower)) return;

    // 2) 메타컬럼 패턴 매칭 → 제외
    if (META_COL_PATTERNS.some(p => p.test(col))) return;

    // 3) insight 계열 → 컬럼명 패턴으로 먼저 분류 (데이터 샘플 수 무관)
    if (INSIGHT_COL_PATTERNS.some(p => p.test(col))) {
      insightCols.push(col);
      return;
    }
    // 3-b) 컬럼명에 'insight' 또는 '인사이트' 포함 시 추가 탐지
    if (/insight|인사이트|memo|메모/i.test(col)) {
      insightCols.push(col);
      return;
    }

    // 4) 데이터 샘플링 기반 판단
    //    - BNR/VID 행의 20% 이상에서 값이 있어야 함
    //    - 순수 숫자·URL·날짜 형식은 제외
    //    - 매우 긴 자유 문장(평균 80자 초과)은 태그 컬럼이 아닌 인사이트 컬럼으로 분류
    const nonEmpty = sampleRows.filter(r => r[col] && r[col].trim()).length;
    if (nonEmpty < sampleRows.length * 0.15) return; // 85% 이상 비어 있으면 제외

    const filledVals = sampleRows.filter(r => r[col] && r[col].trim()).map(r => r[col].trim());

    // 순수 수치 컬럼 제외
    const hasNumericOnly = filledVals.every(v => /^[\d.,\s%+-]+$/.test(v));
    if (hasNumericOnly) return;

    // URL 포함 컬럼 제외 (파일명;URL 형식)
    const hasUrl = filledVals.some(v => /https?:\/\//i.test(v));
    if (hasUrl) return;

    // 날짜 형식 컬럼 제외
    const hasDateOnly = filledVals.every(v => /^\d{4}[-./]\d{1,2}[-./]\d{1,2}$/.test(v));
    if (hasDateOnly) return;

    // 매우 긴 자유 문장 → 인사이트 컬럼으로 분류 (자동 키워드 추출 대상)
    const avgLen = filledVals.reduce((s, v) => s + v.length, 0) / filledVals.length;
    if (avgLen > 60) {
      insightCols.push(col);
      return;
    }

    // TRUE/FALSE 불린 값 컬럼 제외 (오디오 on/off 등)
    const hasBoolOnly = filledVals.every(v => /^(true|false|TRUE|FALSE|예|아니오|yes|no)$/i.test(v));
    if (hasBoolOnly) return;

    // '없음' 단독 값이 대부분인 컬럼 제외 (narrative, cv 등 미기입 컬럼)
    const hasNoneOnly = filledVals.every(v => /^(없음|none|null|n\/a|-|—|0)$/i.test(v));
    if (hasNoneOnly) return;

    // 고유값이 매우 적고 모두 짧은 단일 단어인 경우 태그로 수용 (경쾌함, 긴박함 등 감성 태그)
    // 단, 고유값이 1개뿐이고 너무 흔하면 군집 구분력 없으므로 별도 판단 없이 포함
    tagCols.push(col);
  });

  return { tagCols, insightCols };
}

// ══════════════════════════════════════════
// 3. marketer_insight 키워드 추출
// ══════════════════════════════════════════

/**
 * 자유 문장(한국어/영어 혼용)에서 의미 있는 키워드를 추출한다.
 *
 * 처리 방식:
 *  a) 쉼표·슬래시·마침표로 1차 분리 → 짧은 구(phrase) 후보
 *  b) 조사·어미·불용어 제거
 *  c) 너무 짧거나(1자) 너무 흔한 단어 제거
 *  d) 결과에 접두사 "[MI]" 부착 → 태그와 구분 가능
 */
const INSIGHT_STOPWORDS = new Set([
  // 한국어 조사·어미
  '의','을','를','이','가','은','는','에','에서','으로','로','와','과','도','만','까지','부터',
  '하고','하여','하는','한','된','될','되어','있는','있음','없는','없음','하다','있다','없다',
  '되다','같다','보다','위해','통해','대한','위한','따른','같이','함께','에게','에서는','으로는',
  // 한국어 불용어 – 마케팅/분석 용어 (대폭 확장)
  '소재','분석','결과','확인','필요','진행','예정','추가','변경','수정','검토','반영',
  '광고','캠페인','집행','운영','성과','지표','개선','관련','해당','기타','전략','방향',
  '요소','부분','측면','차원','단계','수준','정도','상태','현황','상황','조건',
  '내용','항목','사항','사례','경우','문제','이슈','포인트','키포인트',
  '테스트','실험','검증','분석','평가','측정','확인','파악','판단','인식',
  '데이터','수치','지표','결과','성과','효과','효율','영향','기여','도움',
  '크리에이티브','배너','동영상','영상','이미지','비주얼','텍스트','카피','문구','메시지',
  '유저','사용자','타겟','고객','유입','전환','클릭','노출','도달',
  '예상','예측','전망','기대','추정','가능','가능성','확률','우려','리스크',
  // 시간/위치/정도 관련
  '이번','지난','다음','현재','향후','이후','이전','아직','특히','주로','매우','굉장히',
  '초반','중반','후반','초기','중기','말기','시점','기간','때','동안',
  '정도','수준','단계','차원','측면','부분','일부','전체','대부분',
  // 일반 형용사/부사 (의미 없는 수식어)
  '높은','낮은','좋은','나쁜','큰','작은','많은','적은','강한','약한','빠른','느린',
  '높음','낮음','좋음','나쁨','큼','작음','많음','적음','강함','약함','빠름','느림',
  '강조','집중','중심','위주','기반','활용','적용','사용','이용','제공',
  '효과','효율','영향','기여','도움','역할','기능','특징','특성','성격',
  '증가','감소','상승','하락','개선','악화','변화','차이','비교','대비','대조',
  '구성','구조','형태','방식','스타일','유형','종류','타입','패턴','방법',
  // 메타 정보 (마케터 의도/타겟 심리/개선 방향 등 분석 프레임)
  '마케터','의도','전략','방향','심리','타겟','개선','확장','보완','권장',
  '최적화','극대화','최소화','강화','완화','조정','변경','수정','추가','삭제',
  '시','때','경우','조건','상황','상태','정도','수준','단계','차원',
  '대상','목적','목표','이유','원인','결과','영향','효과','의미','가치',
  // 분석 문장 구조 키워드
  '전환율','cvr','ctr','cpa','ipm','score','점수','성과','지표','수치','데이터',
  '소재','크리에이티브','배너','동영상','이미지','텍스트','카피',
  '테스트','비교','분석','확인','검증','평가','측정','집계',
  // 분석 접속사 및 추측 표현
  '통해','통한','따라','따른','의한','위한','위해','대한','관한','때문','덕분',
  '또한','그리고','하지만','그러나','따라서','그래서','즉','다시말해','예를들어',
  '것으로','것이','것을','것에','것은','것이다','것으로보임','것으로예상','것으로판단',
  '추정됨','판단됨','보임','것같음','듯함','듯이','것처럼','양상',
  // 보조동사 및 접미사
  '하기','하며','하면','하여','함에','함으로','함과','함께','하기위해','하기위한',
  '되기','되며','되면','되어','됨에','됨으로','됨과','되기위해','되기위한',
  // 무의미한 수량/정도 표현
  '정도의','수준의','차원의','단계의','측면의','부분의','일부의','전체의','대부분의',
  '한','몇','여러','다양한','다수의','소수의','일부','전부','모든','전체',
  // 영어 불용어 (확장)
  'the','a','an','is','are','was','were','be','been','being','have','has','had',
  'and','or','but','in','on','at','to','for','of','with','by','from','into','through',
  'this','that','these','those','it','its','we','our','you','your','they','their',
  'ad','ads','creative','creatives','performance','result','type','content','material',
  'high','low','good','bad','more','less','much','many','very','so','such','too',
  'can','will','should','would','could','may','might','must','shall',
  'when','where','how','why','what','which','who','whom','whose',
  'all','any','some','each','every','most','few','many','other','another',
  'increase','decrease','improve','change','effect','impact','result','outcome',
  // UA/마케팅 메타 용어 (영어)
  'user','target','campaign','banner','video','image','conversion','click','impression',
  'ctr','cvr','cpa','roi','kpi','metric','data','analysis','test','optimize',
]);

function plExtractInsightKeywords(text) {
  if (!text || !text.trim()) return [];

  // 0단계: 메타 정보 구조 및 분석 프레임 제거
  //   예: "[마케터 의도] ..." → 제거
  //   예: "[타겟 심리] ..." → 제거
  text = text.replace(/\[마케터[^\]]*\]/g, '')
             .replace(/\[타겟[^\]]*\]/g, '')
             .replace(/\[개선[^\]]*\]/g, '')
             .replace(/\[.*?의도\]/g, '')
             .replace(/\[.*?심리\]/g, '')
             .replace(/\[.*?방향\]/g, '')
             .replace(/\[.*?전략\]/g, '')
             .replace(/전환율\s*\d+[%\.\d]*\s*[상승하락증가감소예상기대확인]*/g, '')
             .replace(/CVR\s*\d+[%\.\d]*\s*[상승하락증가감소예상기대확인]*/gi, '')
             .replace(/CPA\s*[\d,]+원?\s*[상승하락증가감소예상기대확인]*/gi, '')
             .replace(/IPM\s*\d+[%\.\d]*\s*[상승하락증가감소예상기대확인]*/gi, '')
             .trim();

  // 1단계: 문장 분리 (쉼표·마침표·슬래시·줄바꿈·특수기호)
  const phrases = text
    .split(/[,./·\n;|]+/)
    .map(p => p.trim())
    .filter(p => p.length >= 4);  // 최소 4자 이상 (더 엄격하게)

  const keywords = new Set();

  phrases.forEach(phrase => {
    // 2단계: 구 자체가 짧으면 그대로 후보 (단, 품질 검증 강화)
    if (phrase.length >= 4 && phrase.length <= 30) {
      const cleaned = phrase
        .replace(/[()【】\[\]「」『』""''<>]/g, '')   // 괄호 제거
        .replace(/[!?…~\-–—]+/g, '')                   // 특수문자 제거
        .trim();

      if (cleaned.length >= 4 && cleaned.length <= 30 && isValidInsightKeyword(cleaned)) {
        keywords.add(cleaned);
      }
    }

    // 3단계: 긴 구는 공백 기준으로 토큰 분리 (단, 유의미한 명사구만)
    if (phrase.length > 30) {
      const tokens = phrase.split(/\s+/).map(t =>
        t.replace(/[()【】\[\]「」『』""''<>!?…~\-–—]+/g, '').trim()
      ).filter(t => t.length >= 2);

      // 2-gram/3-gram 복합 명사구만 추출
      for (let i = 0; i < tokens.length - 1; i++) {
        const bigram = `${tokens[i]} ${tokens[i+1]}`;
        if (bigram.length >= 6 && bigram.length <= 25 && isValidInsightKeyword(bigram)) {
          keywords.add(bigram);
        }
        if (i < tokens.length - 2) {
          const trigram = `${tokens[i]} ${tokens[i+1]} ${tokens[i+2]}`;
          if (trigram.length >= 10 && trigram.length <= 35 && isValidInsightKeyword(trigram)) {
            keywords.add(trigram);
          }
        }
      }
    }
  });

  // 4단계: 최종 필터링 + [MI] 접두사 부착
  const finalKeywords = [...keywords]
    .filter(k => isValidInsightKeyword(k))
    .filter(k => {
      if (/(예상|판단|확인|분석|보임|것으로|됨$|됨에|됨으로)$/i.test(k)) return false;
      if (/^(전환율|cvr|ctr|cpa|ipm|지표|수치|점수|score)$/i.test(k)) return false;
      const tokens = k.split(/\s+/);
      const allStop = tokens.every(t => INSIGHT_STOPWORDS.has(t) || INSIGHT_STOPWORDS.has(t.toLowerCase()));
      if (allStop) return false;
      return true;
    })
    .sort((a, b) => b.length - a.length)
    .slice(0, 5);  // 소재당 최대 5개

  return finalKeywords.map(k => `[MI] ${k}`);
}

/**
 * 인사이트 키워드 품질 검증
 * - 불용어 제외
 * - 의미 있는 명사구만 허용
 * - 너무 짧거나 숫자 위주 제외
 */
function isValidInsightKeyword(phrase) {
  if (!phrase || phrase.length < 4) return false;
  const p = phrase.trim();
  const pLower = p.toLowerCase();

  // 불용어 체크
  if (INSIGHT_STOPWORDS.has(p) || INSIGHT_STOPWORDS.has(pLower)) return false;

  // 숫자만 있거나 숫자가 40% 이상
  if (/^[\d\s%.,+-]+$/.test(p)) return false;
  const digitRatio = (p.match(/\d/g) || []).length / p.length;
  if (digitRatio > 0.4) return false;

  // 너무 짧은 단일 단어 (4자 이하)
  if (p.length <= 4 && !/\s/.test(p)) return false;

  // URL 패턴 제외
  if (/^(https?:\/\/|www\.|\.com|\.kr)/i.test(p)) return false;

  // 일반적인 형용사/부사로만 구성
  const GENERIC_MODIFIERS = ['높은','낮은','좋은','나쁜','강한','약한','큰','작은','많은','적은',
                              '높음','낮음','좋음','나쁨','강함','약함','큼','작음','많음','적음',
                              '효과','영향','인상','느낌','분위기','스타일','방식','패턴','형태'];
  const tokens = p.split(/\s+/);
  
  if (tokens.length === 2 && GENERIC_MODIFIERS.some(m => tokens.includes(m))) return false;
  
  if (tokens.length >= 3) {
    const stopCount = tokens.filter(t => 
      INSIGHT_STOPWORDS.has(t) || 
      INSIGHT_STOPWORDS.has(t.toLowerCase()) ||
      GENERIC_MODIFIERS.includes(t)
    ).length;
    if (stopCount >= tokens.length * 0.6) return false;
  }

  const allStop = tokens.every(t => INSIGHT_STOPWORDS.has(t) || INSIGHT_STOPWORDS.has(t.toLowerCase()));
  if (allStop) return false;

  // 특수문자만 있는 경우
  if (/^[^\w가-힣]+$/.test(p)) return false;
  
  // 한글/영문 알파벳이 최소 60% 이상 포함되어야 함
  const korEngCount = (p.match(/[가-힣a-zA-Z]/g) || []).length;
  if (korEngCount < p.length * 0.6) return false;

  return true;
}

// ══════════════════════════════════════════
// 4. 데이터 검증
// ══════════════════════════════════════════
const REQUIRED_COLS = ['소재명', '유형', '전환', '비용', '노출수'];

function plValidateData(parsed) {
  const { headers, rows } = parsed;

  // 4-1. 필수 컬럼 검증
  const missingRequired = REQUIRED_COLS.filter(c => !headers.includes(c));

  // 4-2. 태그·인사이트 컬럼 자동 탐지
  const { tagCols, insightCols } = plDetectTagColumns(headers, rows);
  const allTagSources = [...tagCols, ...insightCols];

  const colResult = {
    missingRequired,
    tagCols,
    insightCols,
    score: missingRequired.length === 0 ? 'pass' : 'fail'
  };

  // 4-3. 데이터 품질
  const issues = [];
  const vidBnrRows  = rows.filter(r => ['BNR','VID'].includes((r['유형']||'').toUpperCase()));
  const txtRows     = rows.filter(r => (r['유형']||'').toUpperCase() === 'TXT');
  const unknownType = rows.filter(r => !['BNR','VID','TXT'].includes((r['유형']||'').toUpperCase()));
  const zeroConv    = vidBnrRows.filter(r => Number(r['전환']||0) === 0);
  // noName: BNR/VID 행 기준만 체크 (TXT는 소재명이 광고 텍스트이므로 분리)
  const noName      = vidBnrRows.filter(r => !r['소재명'] || !r['소재명'].trim());
  const dupNames    = (() => {
    const seen = {}; const dups = new Set();
    vidBnrRows.forEach(r => { const n = r['소재명']; if (n && seen[n]) dups.add(n); seen[n] = true; });
    return [...dups];
  })();
  const negVal = vidBnrRows.filter(r =>
    Number(r['비용']||0) < 0 || Number(r['노출수']||0) < 0
  );

  if (noName.length)      issues.push({ type:'warn',  msg:`소재명 누락 ${noName.length}건 – 분석 제외됩니다.` });
  if (dupNames.length)    issues.push({ type:'warn',  msg:`중복 소재명 ${dupNames.length}개 – 동일 소재 재집행으로 간주. 집계 주의.` });
  if (unknownType.length) issues.push({ type:'error', msg:`유형 불명 ${unknownType.length}건 (BNR/VID/TXT 외) – 수동 확인 필요.` });
  if (negVal.length)      issues.push({ type:'error', msg:`비용/노출수 음수값 ${negVal.length}건 – 데이터 오류 의심.` });
  if (zeroConv.length)    issues.push({ type:'info',  msg:`전환 0인 소재 ${zeroConv.length}건 – Score 최하위로 산출됩니다.` });

  const dataResult = {
    total:rows.length, vidBnr:vidBnrRows.length, txt:txtRows.length,
    unknown:unknownType.length, dupCount:dupNames.length, dupNames,
    zeroConv:zeroConv.length, issues,
    score: (negVal.length === 0 && unknownType.length === 0) ? 'pass' : 'warn'
  };

  // 4-4. 태그 품질
  const noTag = vidBnrRows.filter(r => {
    const allTags = allTagSources.map(c => r[c]||'').join(',').trim();
    return !allTags || allTags.replace(/,/g,'').trim() === '';
  });
  const avgTagCount = (() => {
    const counts = vidBnrRows.map(r => {
      const combined = tagCols.map(c => r[c]||'').join(',');
      return plParseTags(combined).length;
    });
    return counts.length ? (counts.reduce((a,b)=>a+b,0)/counts.length).toFixed(1) : 0;
  })();

  const tagResult = {
    availTagCols: tagCols,
    insightCols,
    noTag: noTag.length, avgTagCount,
    score: noTag.length > vidBnrRows.length * 0.3 ? 'warn' : 'pass'
  };

  return { colResult, dataResult, tagResult, validRows: vidBnrRows };
}

// ══════════════════════════════════════════
// 5. Total Score 산출
// ══════════════════════════════════════════
function plCalcScores(rows, params, headers) {
  const { wConv, wCpa, wIpm } = params;
  const wSum = wConv + wCpa + wIpm || 100;

  // ★ 태그·인사이트 컬럼 자동 탐지 (헤더 전수 스캔)
  const { tagCols, insightCols } = plDetectTagColumns(headers, rows);

  const creatives = rows.map(r => {
    const name   = r['소재명'] || '';
    const type   = (r['유형']||'BNR').toUpperCase();
    const conv   = Math.max(0, Number(r['전환'] || 0));
    const cost   = Math.max(0, Number(r['비용'] || 0));
    const impr   = Math.max(1, Number(r['노출수'] || 1));
    const clicks = Math.max(0, Number(r['클릭수'] || 0));
    const ctr    = clicks / impr * 100;
    const ipm    = conv / impr * 1000;
    const cpa    = cost > 0 && conv > 0 ? cost / conv : (conv === 0 ? 99999 : 0);

    // ① 탐지된 모든 태그 컬럼 합산
    const rawTags    = tagCols.map(c => r[c]||'').join(',');
    const parsedTags = plParseTags(rawTags);

    // ② marketer_insight 계열 → 키워드 추출 후 [MI] 태그로 변환
    const insightText = insightCols.map(c => r[c]||'').join('. ');
    const insightTags = insightText.trim() ? plExtractInsightKeywords(insightText) : [];

    // ③ 합산 (중복 제거)
    const allTags = [...new Set([...parsedTags, ...insightTags])];

    return {
      name, type, conversions:conv, cost, impressions:impr, clicks,
      ctr:+ctr.toFixed(2), ipm:+ipm.toFixed(2), cpa:+cpa.toFixed(0),
      tags: allTags,
      tagSources: {                    // 디버깅·UI 표시용
        fromTagCols:   parsedTags,
        fromInsight:   insightTags,
      },
      raw:r, score:0, grade:'', cluster:''
    };
  }).filter(c => c.name);

  if (!creatives.length) return [];

  // 정규화 (min-max, 0~100)
  const normalize = (vals, invert = false) => {
    const min = Math.min(...vals), max = Math.max(...vals);
    if (max === min) return vals.map(() => 50);
    return vals.map(v => {
      const n = (v - min) / (max - min) * 100;
      return invert ? 100 - n : n;
    });
  };

  const convNorm = normalize(creatives.map(c => c.conversions));
  const cpaNorm  = normalize(creatives.map(c => c.cpa), true);
  const ipmNorm  = normalize(creatives.map(c => c.ipm));

  creatives.forEach((c, i) => {
    c.score = +((convNorm[i]*wConv + cpaNorm[i]*wCpa + ipmNorm[i]*wIpm) / wSum).toFixed(1);
  });

  // 등급 배정
  const { q1, q2, q3 } = calcQuartiles(creatives.map(c => c.score));
  creatives.forEach(c => {
    c.grade = scoreToGrade(c.score, q1, q2, q3);
  });

  return creatives;
}

// ══════════════════════════════════════════
// 6. 동적 태그 군집화 엔진 v4 (Jaccard 유사도 기반)
//    Step1: 태그 빈도 + 동시출현 분석
//    Step2: 소재간 Jaccard 유사도 그룹화
//    Step3: 데이터 중심 군집 명명
//    Step4: BNR vs VID 입체적 분석
// ══════════════════════════════════════════

/**
 * 최소 군집 수 보장 래퍼
 *
 * ★ 핵심 원리: 군집 수를 늘리려면 Union-Find 병합을 "덜" 해야 한다.
 *   → coThreshold(병합 임계값)를 높이거나, NOISE_HIGH(상한)를 낮추거나,
 *     minCluster(최소 소재 수)를 낮춰야 한다.
 *   ※ minSupport를 낮추거나 coOccur를 낮추면 오히려 더 뭉쳐져 역효과.
 *
 * 재시도 전략 (attempt별):
 *   1회: coBoost +0.3 (Union 병합 임계값 상향 → 덜 합쳐짐)
 *   2회: noisePct -0.10 (상한 필터 강화 → 공통 태그 더 많이 제거)
 *   3회: coBoost +0.3 추가
 *   4회: noisePct -0.10 추가
 *   5회: minCluster -1 (작은 군집도 독립 인정)
 */
function plRunClusteringWithMinGuarantee(creatives, params, prevInsights) {
  const { useMinClusters, minClusters } = params;

  if (!useMinClusters || !minClusters || minClusters <= 1) {
    return plRunClustering(creatives, params, prevInsights);
  }

  const MAX_RETRY = 5;
  let attempt   = 0;
  let result    = [];
  let curParams = { ...params, _coBoost: 0, _noiseTighten: 0 };

  while (attempt < MAX_RETRY) {
    result = plRunClustering(creatives, curParams, prevInsights);
    const realCount = result.filter(cl => cl.name !== '기타 / 단독 소재').length;

    if (realCount >= minClusters) break;

    attempt++;
    if (attempt >= MAX_RETRY) break;

    // 각 재시도마다 "분리력 강화" 방향으로 파라미터 완화
    if (attempt === 1 || attempt === 3) {
      // coThreshold 높이기 → Union 병합이 줄어 군집 수 증가
      curParams = { ...curParams, _coBoost: (curParams._coBoost || 0) + 0.3 };
    } else if (attempt === 2 || attempt === 4) {
      // 노이즈 상한을 낮춰 공통 태그를 더 제거 → 차별 태그만 남아 분리력 증가
      curParams = { ...curParams, _noiseTighten: (curParams._noiseTighten || 0) + 0.10 };
    } else {
      // 마지막: minCluster 완화로 작은 군집도 독립 군집으로 인정
      curParams = { ...curParams, minCluster: Math.max(1, curParams.minCluster - 1) };
    }
  }

  result._retryCount  = attempt;
  result._finalParams = curParams;
  return result;
}

function plRunClustering(creatives, params, prevInsights) {
  const { minCluster, minSupport, coOccur } = params;
  // 재시도 래퍼가 전달하는 보조 파라미터
  const coBoost     = params._coBoost     || 0;  // Union 병합 임계값 추가 상향분
  const noiseTighten = params._noiseTighten || 0; // 노이즈 상한 추가 하향분 (0.0~0.3)

  const n = creatives.length;
  if (n < 2) return [];

  // 6-1. 전체 태그 빈도 계산
  const tagFreq = {};
  creatives.forEach(c => {
    c.tags.forEach(t => { tagFreq[t] = (tagFreq[t]||0) + 1; });
  });

  // 6-2. 노이즈 필터링
  //  ★ 핵심: 상한 noisePct를 낮출수록 공통 태그가 더 많이 제거되어 군집 분리력 증가
  //    기본값: n <= 15 → 55%, else → minSupport/100 + 0.10 (최대 55%)
  //    (구 버전은 0.85/0.80으로 너무 느슨해 공통 태그가 그대로 남아 Union 과다 발생)
  const baseNoisePct = n <= 15
    ? 0.55
    : Math.min(minSupport / 100 + 0.10, 0.55);
  const noisePct   = Math.max(0.20, baseNoisePct - noiseTighten);
  const NOISE_HIGH = n * noisePct;
  const NOISE_LOW  = 1;  // 1개 소재에만 등장 → 구분력 없음

  // ★ [MI] 태그는 상한 필터 적용하지 않음 (마케터 인사이트는 보편적이어도 의미 있음)
  const discriminativeTags = Object.entries(tagFreq)
    .filter(([tag, cnt]) => {
      if (cnt <= NOISE_LOW) return false;             // 하한 필터 (공통)
      if (tag.startsWith('[MI]')) return cnt >= 1;   // MI 태그: 하한만 적용
      return cnt < NOISE_HIGH;                        // 일반 태그: 상한+하한
    })
    .sort((a, b) => b[1] - a[1])
    .map(([tag]) => tag);

  // 폴백: 탐지된 차별 태그가 부족하면 2회 이상 등장 태그 전부 사용
  const clusteringTags = discriminativeTags.length >= 3
    ? discriminativeTags
    : Object.entries(tagFreq).filter(([, cnt]) => cnt >= 2).map(([t]) => t);

  // 6-3. 동시출현 행렬 (가중치 적용)
  const coMatrix = {};
  const coKey = (a, b) => [a, b].sort().join('|||');

  creatives.forEach(c => {
    const dt = c.tags.filter(t => clusteringTags.includes(t));
    for (let i = 0; i < dt.length; i++) {
      for (let j = i + 1; j < dt.length; j++) {
        const k = coKey(dt[i], dt[j]);
        // [MI] 태그가 포함된 쌍은 가중치 1.5배 적용
        const weight = (dt[i].startsWith('[MI]') || dt[j].startsWith('[MI]')) ? 1.5 : 1;
        coMatrix[k] = (coMatrix[k]||0) + weight;
      }
    }
  });

  // 6-4. Union-Find로 태그 그룹 생성
  //  ★ 핵심: coThreshold를 높일수록 병합이 줄어 군집 수 증가
  //    기본값: n * 0.20 (소재 20% 이상에서 공동 등장해야만 같은 군집)
  //    (구 버전 n * 0.05는 너무 낮아 모든 태그가 하나로 합쳐짐)
  const parent = {};
  clusteringTags.forEach(t => { parent[t] = t; });
  function find(x) { if (parent[x] !== x) parent[x] = find(parent[x]); return parent[x]; }
  function union(x, y) { parent[find(x)] = find(y); }

  const baseCoThreshold = n <= 10 ? n * 0.40 : Math.max(n * 0.15, 3);
  const coThreshold = baseCoThreshold + coBoost * n * 0.05; // 재시도 시 임계값 상향
  Object.entries(coMatrix).forEach(([key, cnt]) => {
    if (cnt >= coThreshold) {
      const [a, b] = key.split('|||');
      union(a, b);
    }
  });

  // 6-5. 태그 루트별 그룹화
  const tagGroups = {};
  clusteringTags.forEach(t => {
    const root = find(t);
    if (!tagGroups[root]) tagGroups[root] = [];
    tagGroups[root].push(t);
  });

  // 6-6. 소재 → 군집 매핑
  creatives.forEach(c => {
    const myTags = c.tags.filter(t => clusteringTags.includes(t));
    let bestGroup = null, bestScore = -1;

    Object.entries(tagGroups).forEach(([root, groupTags]) => {
      // [MI] 태그 매칭은 1.5배 가중
      let score = 0;
      myTags.forEach(t => {
        if (groupTags.includes(t)) {
          score += t.startsWith('[MI]') ? 1.5 : 1;
        }
      });
      const threshold = Math.max(0.5, coOccur - 1);
      if (score > threshold && score > bestScore) {
        bestScore = score;
        bestGroup = root;
      }
    });
    c._clusterRoot = bestGroup || '__misc__';
  });

  // 6-7. 최소 소재 수 미만 → 기타 처리
  const clusterMap = {};
  creatives.forEach(c => {
    if (!clusterMap[c._clusterRoot]) clusterMap[c._clusterRoot] = [];
    clusterMap[c._clusterRoot].push(c);
  });

  const validClusters = {}, miscCreatives = [];
  Object.entries(clusterMap).forEach(([root, list]) => {
    if (root === '__misc__' || list.length < minCluster) {
      miscCreatives.push(...list);
    } else {
      validClusters[root] = list;
    }
  });
  if (miscCreatives.length) validClusters['__misc__'] = miscCreatives;

  // 6-8. 군집 메타 산출 + 이름 결정
  const prevClusters = prevInsights ? (prevInsights.clusters || []) : [];
  const usedNames = [];

  const clusters = Object.entries(validClusters).map(([root, list], idx) => {
    const avgScore = +(list.reduce((s, c) => s + c.score, 0) / list.length).toFixed(1);

    // TF-IDF 방식으로 군집 특징 태그 추출 ([MI] 태그 별도 표시용으로 분리)
    const freq = {};
    list.forEach(c => c.tags.forEach(t => { freq[t] = (freq[t]||0) + 1; }));

    const allTopTags = Object.entries(freq)
      .map(([t, cnt]) => ({
        tag: t,
        tfidf: (cnt / list.length) / ((tagFreq[t] || 1) / n),
        isMI: t.startsWith('[MI]'),
      }))
      .sort((a, b) => b.tfidf - a.tfidf);

    const topTags    = allTopTags.filter(x => !x.isMI).slice(0, 10).map(x => x.tag);
    const topMITags  = allTopTags.filter(x => x.isMI).slice(0, 5).map(x => x.tag);

    const vidCount = list.filter(c => c.type === 'VID').length;
    const bnrCount = list.filter(c => c.type === 'BNR').length;
    const topCreative   = list.reduce((a, b) => a.score > b.score ? a : b, list[0]);
    const worstCreative = list.reduce((a, b) => a.score < b.score ? a : b, list[0]);

    // 이전 차수 군집 유사도 비교
    let name = '', isNew = true, prevRef = null;
    if (root !== '__misc__' && prevClusters.length) {
      let maxSim = 0;
      prevClusters.forEach(pc => {
        const sim = topTags.filter(t => (pc.topTags||[]).includes(t)).length;
        if (sim > maxSim) { maxSim = sim; prevRef = pc; }
      });
      if (maxSim >= 3) { name = prevRef.name; isNew = false; }
    }

    // 이름 자동 생성 (일반 태그 기준 – [MI] 태그는 제외)
    if (!name) {
      if (root === '__misc__') {
        name = '기타 / 단독 소재';
      } else {
        const NOISE_NAME_TAGS = ['캐릭터','비주얼 임팩트','텍스트 오버레이','마그 탐험대',
                                  '아트 퀄리티','유닛 외형','수집형RPG','수집형 RPG'];
        const nameTokens = topTags.filter(t => !NOISE_NAME_TAGS.includes(t)).slice(0, 2);
        name = nameTokens.length >= 1
          ? nameTokens.join(' · ') + '형'
          : (topTags[0] || `군집 ${idx + 1}`) + '형';
        const dup = usedNames.filter(n => n === name).length;
        if (dup > 0) name += ` ${dup + 1}`;
      }
    }

    const description = generateClusterDescription(
      topTags, topMITags, avgScore, list.length, vidCount, bnrCount
    );

    usedNames.push(name);
    list.forEach(c => { c.cluster = name; });

    return {
      id: `cluster_${idx + 1}`, name, topTags, topMITags, avgScore,
      creativeCount: list.length, vidCount, bnrCount,
      topCreative, worstCreative, description,
      isNew, prevRef: prevRef?.name || null, creatives: list,
    };
  });

  clusters.sort((a, b) => b.avgScore - a.avgScore);
  return clusters;
}

// 군집 설명 자동 생성 (marketer_insight 반영)
function generateClusterDescription(topTags, topMITags, avgScore, count, vid, bnr) {
  const high = avgScore >= 60, mid = avgScore >= 40;
  const tagSample = topTags.slice(0, 3).join(', ');
  const perf      = high ? '상위 성과' : mid ? '중간 성과' : '하위 성과';
  const typeDesc  = vid > bnr ? `VID 중심(${vid}/${count})` : `BNR 중심(${bnr}/${count})`;
  const miNote    = topMITags.length
    ? ` 마케터 인사이트: ${topMITags.slice(0,2).map(t=>t.replace('[MI] ','')).join(', ')}.`
    : '';
  return `[${perf}] ${tagSample} 위주의 소재군. ${typeDesc}. 평균 Score ${avgScore}.${miNote}`;
}

// ══════════════════════════════════════════
// 7. 태그 영향도 분석
// ══════════════════════════════════════════
function plCalcTagImpact(creatives) {
  const tagScores = {};
  creatives.forEach(c => {
    c.tags.forEach(t => {
      if (!tagScores[t]) tagScores[t] = { scores:[], count:0 };
      tagScores[t].scores.push(c.score);
      tagScores[t].count++;
    });
  });
  const globalAvg = creatives.reduce((s, c) => s + c.score, 0) / creatives.length;

  const impacts = Object.entries(tagScores)
    .filter(([, v]) => v.count >= 2)
    .map(([tag, v]) => {
      const tagAvg = v.scores.reduce((a, b) => a + b, 0) / v.scores.length;
      const impact = +(tagAvg - globalAvg).toFixed(1);
      const isMI   = tag.startsWith('[MI]');
      return { tag, impact, count:v.count, tagAvg:+tagAvg.toFixed(1), isMI };
    })
    .sort((a, b) => b.impact - a.impact);

  return { impacts, globalAvg: +globalAvg.toFixed(1) };
}

// ══════════════════════════════════════════
// 8. 차수 간 차이 분석
// ══════════════════════════════════════════
function plDiffRounds(curClusters, curTagImpacts, prevRound) {
  if (!prevRound) return null;
  if (!curClusters || !curClusters.length) return null;

  const prevClusters = prevRound.clusters  || [];
  const prevWinTags  = prevRound.winningTags || [];
  const prevLoseTags = prevRound.losingTags  || [];

  const clusterDiff = [];
  curClusters.forEach(cc => {
    const prev  = prevClusters.find(p => p.name === cc.name);
    if (!prev) {
      clusterDiff.push({ type:'new', name:cc.name,
        desc:`신규 군집 생성됨. 이번 평균 Score ${cc.avgScore}점 · 소재 ${cc.creativeCount}개.` });
    } else {
      const delta = +(cc.avgScore - prev.avgScore).toFixed(1);
      const type  = delta >= 5 ? 'up' : delta <= -5 ? 'down' : 'stable';
      const countDelta = cc.creativeCount - (prev.creativeCount || 0);
      clusterDiff.push({ type, name:cc.name,
        desc:`Score ${delta>=0?'+':''}${delta}점 (이전 ${prev.avgScore} → 현재 ${cc.avgScore}). 소재 수 ${countDelta>=0?'+':''}${countDelta}개.` });
    }
  });
  prevClusters.forEach(pc => {
    if (!curClusters.find(cc => cc.name === pc.name)) {
      clusterDiff.push({ type:'removed', name:pc.name,
        desc:`이번 차수에 없어짐 (이전 Score ${pc.avgScore} · 소재 ${pc.creativeCount||'?'}개).` });
    }
  });

  const tagDiff = [];
  if (curTagImpacts && curTagImpacts.impacts) {
    const curWinTags  = curTagImpacts.impacts.filter(t => t.impact > 0).slice(0, 10);
    const curLoseTags = curTagImpacts.impacts.filter(t => t.impact < 0).slice(-10).reverse();
    curWinTags.forEach(ct => {
      const prev = prevWinTags.find(p => p.tag === ct.tag);
      const type = !prev ? 'new_win' : (ct.impact > prev.impact ? 'improved' : 'stable');
      tagDiff.push({ tag:ct.tag, type, impact:ct.impact, prevImpact:prev?prev.impact:null });
    });
    curLoseTags.forEach(ct => {
      const prev = prevLoseTags.find(p => p.tag === ct.tag);
      tagDiff.push({ tag:ct.tag, type:!prev?'new_lose':'stable_lose',
        impact:ct.impact, prevImpact:prev?prev.impact:null });
    });
  }

  return { clusterDiff, tagDiff };
}
