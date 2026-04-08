/**
 * Pepp Heroes – Core Data Store
 * 소재명 기준 분석 데이터 (가정 Total Score / Rank 기반)
 */

// ── 소재 이미지 URL 매핑 (원본 CSV의 링크 컬럼)
const CREATIVE_URLS = {
  "A-Character-Adventure01A-DA": [
    "https://tpc.googlesyndication.com/simgad/7852267225455295083",
    "https://tpc.googlesyndication.com/simgad/13260462268912176542"
  ],
  "A-Character-Adventure02A-DA": [
    "https://tpc.googlesyndication.com/simgad/7571534943945847205",
    "https://tpc.googlesyndication.com/simgad/11186665980784424187",
    "https://tpc.googlesyndication.com/simgad/4700820855523046748"
  ],
  "A-Character-Adventure03A-DA": [
    "https://tpc.googlesyndication.com/simgad/10208753457933375751",
    "https://tpc.googlesyndication.com/simgad/7801812518978402727"
  ],
  "A-Character-Adventure04A-DA": [
    "https://tpc.googlesyndication.com/simgad/11190732183298883065",
    "https://tpc.googlesyndication.com/simgad/4078122247307565443"
  ],
  "A-Character-Adventure05A-DA": [
    "https://tpc.googlesyndication.com/simgad/14620542589526622535",
    "https://tpc.googlesyndication.com/simgad/13772335840655466460"
  ],
  "A-Character-Comics01A-DA": [
    "https://tpc.googlesyndication.com/simgad/3049438568803176011",
    "https://tpc.googlesyndication.com/simgad/4695384483296336434"
  ],
  "A-Character-Keyart01A-DA": [
    "https://tpc.googlesyndication.com/simgad/7229897833742420635",
    "https://tpc.googlesyndication.com/simgad/3824621935165149692"
  ],
  "A-Character-Keyart02A-DA": [
    "https://tpc.googlesyndication.com/simgad/12671710964202932656",
    "https://tpc.googlesyndication.com/simgad/15775815948051445986"
  ],
  "A-Character-Life01A-DA": [
    "https://tpc.googlesyndication.com/simgad/4842260928888903016",
    "https://tpc.googlesyndication.com/simgad/1365671312776743899"
  ],
  "A-Character-Life02A-DA": [
    "https://tpc.googlesyndication.com/simgad/8044325649697956804"
  ],
  "A-Character-100usd01A-DA": [
    "https://tpc.googlesyndication.com/simgad/128038747177600361",
    "https://tpc.googlesyndication.com/simgad/10042032527036690642"
  ],
  "A-Mob-Adventure01A-DA": [
    "https://tpc.googlesyndication.com/simgad/2612131296540636395",
    "https://tpc.googlesyndication.com/simgad/12434929736001671929"
  ],
  "A-Mob-Adventure02A-DA": [
    "https://tpc.googlesyndication.com/simgad/6175395671832009540"
  ],
  /*
   * VID 소재 – Google Ads 영상 소재는 정지 이미지 URL이 별도 제공되지 않습니다.
   * CSV 업로드 시 '링크' 컬럼에 영상 URL을 포함하면 자동으로 반영됩니다.
   * 아래 항목들은 링크 컬럼 데이터가 있을 경우 업로드 시 덮어씌워집니다.
   *
   * "A-Charater-Collection01B-UA": [],
   * "A-Charater-Collection01A-UA": [],
   * "A-Character-Collection01B-UA": [],
   * "A-Character-Collection01A-UA": [],
   * "A-Character-Combat01B-UA": [],
   * "A-Character-Combat01A-UA": [],
   * "A-Hooking-Reward02A-FK": [],
   * "A-Hooking-Reward03A-UA": [],
   * "A-Mob-Adventure01A-UA": []
   */
};

// ── 승리 태그 영향도 데이터
const WINNING_TAGS = [
  { tag: "Collection01B", impact: 20.4, support: 2 },
  { tag: "Hugo", impact: 17.1, support: 3 },
  { tag: "캐릭터", impact: 15.0, support: 23 },
  { tag: "유닛 외형", impact: 15.0, support: 21 },
  { tag: "수집욕", impact: 14.7, support: 8 },
  { tag: "소유욕", impact: 14.7, support: 8 },
  { tag: "2D 일러스트", impact: 14.7, support: 4 },
  { tag: "Vinessa", impact: 14.3, support: 4 },
  { tag: "질문", impact: 12.5, support: 5 },
  { tag: "DIY 픽업 시스템", impact: 12.5, support: 5 },
  { tag: "선택형", impact: 12.5, support: 5 },
  { tag: "경쾌함", impact: 11.0, support: 5 },
  { tag: "전략성", impact: 10.8, support: 7 },
  { tag: "용병 모집", impact: 9.7, support: 8 }
];

// ── 패배 태그 영향도 데이터
const LOSING_TAGS = [
  { tag: "휴식과 힐링", impact: -21.4, support: 3 },
  { tag: "장애물 및 도전", impact: -17.5, support: 3 },
  { tag: "8인 실시간 전투", impact: -13.4, support: 7 },
  { tag: "SD", impact: -12.5, support: 4 },
  { tag: "치비 캐릭터", impact: -12.5, support: 3 },
  { tag: "렐릭 퀘스트", impact: -9.9, support: 5 },
  { tag: "Mob", impact: -8.7, support: 4 },
  { tag: "렐릭 탐험 어드벤처", impact: -8.4, support: 9 },
  { tag: "자연", impact: -8.4, support: 6 },
  { tag: "야외 미학", impact: -8.4, support: 4 },
  { tag: "탐험 및 발견", impact: -8.1, support: 5 },
  { tag: "실패", impact: -6.5, support: 2 }
];

// ── 군집 인사이트 정의
const CLUSTER_INSIGHTS = {
  "캐릭터 수집 매력형": {
    id: "c1",
    name: "캐릭터 수집 매력형",
    description: "캐릭터 외형·키아트·비주얼 임팩트 중심의 소재군. 인지도 높은 캐릭터 자산을 전면에 배치하여 브랜드 노출 효과가 강함.",
    count: 13,
    avgScore: 32.7,
    topTags: ["캐릭터", "유닛 외형", "비주얼 임팩트", "아트 퀄리티", "텍스트 오버레이", "2.5D 입체 그래픽", "마그 탐험대"],
    weakTags: ["8인 실시간 전투", "렐릭 탐험 어드벤처", "탐험 및 발견"],
    successCause: "캐릭터 비주얼 자체의 완성도와 인지 매력이 높을 때 상위권 진입 가능 (Adventure02A Score 59)",
    failCause: "메시지 부재 시 급락. 수집/획득 동기 없이 비주얼만 강조하면 설득력이 떨어짐 (Adventure03A Score 3)",
    improvement: "획득 이유·후킹·수집 논리를 소재에 추가. '이 캐릭터를 왜 지금 모아야 하는가'를 명확히 제시해야 함",
    bestCreative: "A-Character-Adventure02A-DA",
    worstCreative: "A-Character-Adventure03A-DA"
  },
  "캐릭터 수집 매력형 2": {
    id: "c2",
    name: "캐릭터 수집 매력형 2",
    description: "수집욕·소유욕·질문/선택형 후킹·UI 이해도 요소를 포함한 소재군. 단순 비주얼 노출을 넘어 '선택하고 모으는 경험'을 빠르게 전달함.",
    count: 10,
    avgScore: 41.9,
    topTags: ["질문", "선택형", "DIY 픽업 시스템", "수집욕", "소유욕", "히어로 수집 육성", "수집 및 도감", "심플", "클린 UI"],
    weakTags: ["비주얼 임팩트 단독", "2.5D 월드 강조"],
    successCause: "선택/픽업 구조를 통해 유저가 '직접 고른다'는 능동적 경험을 상상하게 만들어 전환 동기 극대화",
    failCause: "같은 수집 계열이라도 전달 구조가 약하면 점수 하락. Collection01A-UA(Score 22) vs Collection01B-UA(Score 56) 대조",
    improvement: "질문형 오프닝 → 선택/픽업 구조 제시 → 캐릭터 외형 강조 → 수집/소유 욕구 마무리 순서 유지. 구조 일관성이 핵심",
    bestCreative: "A-Charater-Collection01B-UA",
    worstCreative: "A-Character-Collection01A-UA"
  }
};

// ── 메인 소재 데이터 (기본값 – CSV 업로드 시 덮어씌워짐)
const DEFAULT_CREATIVES = [
  {
    name: "A-Character-Adventure02A-DA",
    type: "BNR",
    score: 59,
    rank: 1,
    grade: "최우수",
    cluster: "캐릭터 수집 매력형",
    fileCount: 3,
    tags: ["캐릭터", "유닛 외형", "비주얼 임팩트", "아트 퀄리티", "릴리즈 예고", "수집형RPG", "용병 모집(Gacha)", "렐릭 퀘스트", "마그 탐험대", "샤일린(Shylin)", "렐릭 탐험 어드벤처", "수집 및 도감", "텍스트 오버레이", "자연"]
  },
  {
    name: "A-Charater-Collection01B-UA",
    type: "VID",
    score: 56,
    rank: 2,
    grade: "최우수",
    cluster: "캐릭터 수집 매력형 2",
    fileCount: 2,
    tags: ["질문", "선택형", "캐릭터", "유닛 외형", "경쾌함", "아트 퀄리티", "전략성", "용병 모집", "DIY 픽업 시스템", "마그 탐험대", "Hugo", "히어로 수집 육성", "수집 및 도감", "텍스트 오버레이"]
  },
  {
    name: "A-Character-Keyart02A-DA",
    type: "BNR",
    score: 55,
    rank: 3,
    grade: "최우수",
    cluster: "캐릭터 수집 매력형 2",
    fileCount: 3,
    tags: ["캐릭터", "유닛 외형", "비주얼 임팩트", "아트 퀄리티", "수집형 RPG", "8인 실시간 전투", "마그 탐험대", "플레이어 캐릭터(PC)", "주요 영웅 6종", "히어로 수집 육성", "수집 및 도감", "텍스트 오버레이", "심플", "클린 UI"]
  },
  {
    name: "A-Charater-Collection01A-UA",
    type: "VID",
    score: 54,
    rank: 4,
    grade: "최우수",
    cluster: "캐릭터 수집 매력형 2",
    fileCount: 2,
    tags: ["질문", "선택형", "캐릭터", "유닛 외형", "경쾌함", "아트 퀄리티", "전략성", "용병 모집", "DIY 픽업 시스템", "마그 탐험대", "Vinessa", "히어로 수집 육성", "수집 및 도감", "텍스트 오버레이"]
  },
  {
    name: "A-Character-Collection01B-UA",
    type: "VID",
    score: 53,
    rank: 5,
    grade: "최우수",
    cluster: "캐릭터 수집 매력형 2",
    fileCount: 1,
    tags: ["캐릭터", "질문", "선택형", "유닛 외형", "경쾌함", "수집형RPG", "전략성", "용병 모집(Gacha)", "DIY 픽업 시스템", "마그 탐험대", "휴고", "카르벨", "모나드", "히어로 수집 육성"]
  },
  {
    name: "A-Mob-Adventure01A-DA",
    type: "BNR",
    score: 51,
    rank: 6,
    grade: "최우수",
    cluster: "캐릭터 수집 매력형",
    fileCount: 3,
    tags: ["캐릭터", "유닛 외형", "비주얼 임팩트", "아트 퀄리티", "수집형RPG", "8인 실시간 전투", "8종 직업 및 4종 클래스 체계", "고블린", "렐릭 탐험 어드벤처", "몬스터 군단 중심의 구도", "전투 및 액션", "탐험 및 발견", "텍스트 오버레이", "자연"]
  },
  {
    name: "A-Character-Adventure01A-DA",
    type: "BNR",
    score: 49,
    rank: 7,
    grade: "우수",
    cluster: "캐릭터 수집 매력형",
    fileCount: 3,
    tags: ["캐릭터", "비주얼 임팩트", "유닛 외형", "아트 퀄리티", "수집형RPG", "5인 분대 전투", "수집형 RPG", "마그 탐험대", "고블린", "카르벨(Karbel)", "렐릭 탐험 어드벤처", "2.5D 입체 월드 강조", "전투 및 액션", "탐험 및 발견"]
  },
  {
    name: "A-Character-Combat01B-UA",
    type: "VID",
    score: 47,
    rank: 8,
    grade: "우수",
    cluster: "캐릭터 수집 매력형",
    fileCount: 3,
    tags: ["비주얼 임팩트", "캐릭터", "유닛 외형", "긴박함", "전략성", "아트 퀄리티", "용병 모집", "8인 실시간 전투", "마그 탐험대", "Hugo", "Monad", "Karbel", "히어로 수집 육성", "전투 및 액션"]
  },
  {
    name: "A-Character-Combat01A-UA",
    type: "VID",
    score: 44,
    rank: 9,
    grade: "우수",
    cluster: "캐릭터 수집 매력형",
    fileCount: 3,
    tags: ["캐릭터", "비주얼 임팩트", "유닛 외형", "긴박함", "아트 퀄리티", "수집형RPG", "전략성", "용병 모집", "스킬 컷신 연출", "마그 탐험대", "Vinessa", "Sophia", "Berneta", "렐릭 탐험 어드벤처"]
  },
  {
    name: "A-Character-Keyart01A-DA",
    type: "BNR",
    score: 39,
    rank: 10,
    grade: "우수",
    cluster: "캐릭터 수집 매력형",
    fileCount: 3,
    tags: ["캐릭터", "유닛 외형", "비주얼 임팩트", "아트 퀄리티", "수집형RPG", "수집형 RPG", "분대 조합", "마그 탐험대", "샤일린(Shylin)", "메인 플레이어(PC)", "렐릭 탐험 어드벤처", "수집 및 도감", "텍스트 오버레이", "자연"]
  },
  {
    name: "A-Charater-Collection01A-DA",
    type: "BNR",
    score: 36,
    rank: 11,
    grade: "우수",
    cluster: "캐릭터 수집 매력형 2",
    fileCount: 2,
    tags: ["캐릭터", "유닛 외형", "비주얼 임팩트", "아트 퀄리티", "수집형RPG", "수집형 RPG", "용병 모집(Gacha)", "마그 탐험대", "다수의 SD 영웅", "히어로 수집 육성", "수집 및 도감", "텍스트 오버레이", "심플", "클린 UI"]
  },
  {
    name: "A-Character-Adventure05A-DA",
    type: "BNR",
    score: 34,
    rank: 12,
    grade: "우수",
    cluster: "캐릭터 수집 매력형",
    fileCount: 3,
    tags: ["캐릭터", "유닛 외형", "비주얼 임팩트", "아트 퀄리티", "수집형RPG", "8인 실시간 전투", "수집형 RPG", "렐릭 퀘스트", "마그 탐험대", "고블린", "샤일린(Shylin)", "카르벨(Karbel)", "렐릭 탐험 어드벤처", "2.5D 독보적 그래픽 강조"]
  },
  {
    name: "A-Character-Life01A-DA",
    type: "BNR",
    score: 33,
    rank: 13,
    grade: "보통",
    cluster: "캐릭터 수집 매력형",
    fileCount: 3,
    tags: ["8인 실시간 전투", "캐릭터", "유닛 외형", "비주얼 임팩트", "아트 퀄리티", "수집형RPG", "8종 직업 및 4종 클래스 체계", "렐릭 퀘스트", "마그 탐험대", "카르벨(Karbel)", "렐릭 탐험 어드벤처", "히어로 수집 육성", "수집 및 도감", "탐험 및 발견"]
  },
  {
    name: "A-Hooking-Reward02A-FK",
    type: "VID",
    score: 33,
    rank: 13,
    grade: "보통",
    cluster: "캐릭터 수집 매력형",
    fileCount: 2,
    tags: ["실패", "분노 유도", "압도적 보상", "긴박함", "보상", "용병 모집", "우호도 시스템", "마그 탐험대", "카르벨(Karbel)", "히어로 수집 육성", "페이크 플레이(구출 미니게임) 형식 활용", "퍼즐 및 논리", "손가락 지시선", "텍스트 오버레이"]
  },
  {
    name: "A-Character-100usd01A-DA",
    type: "BNR",
    score: 32,
    rank: 15,
    grade: "보통",
    cluster: "캐릭터 수집 매력형 2",
    fileCount: 3,
    tags: ["압도적 보상", "캐릭터", "유닛 외형", "보상", "릴리즈 예고", "용병 모집(Gacha)", "사전예약 혜택", "마그 탐험대", "카르벨(Karbel)", "히어로 수집 육성", "수집 및 도감", "텍스트 오버레이", "클로즈업 및 줌", "심플"]
  },
  {
    name: "A-Character-Adventure04A-DA",
    type: "BNR",
    score: 28,
    rank: 16,
    grade: "보통",
    cluster: "캐릭터 수집 매력형",
    fileCount: 3,
    tags: ["8인 실시간 전투", "비주얼 임팩트", "캐릭터", "유닛 외형", "아트 퀄리티", "수집형RPG", "릴리즈 예고", "수집형 RPG", "마그 탐험대", "고블린", "카르벨(Karbel)", "샤일린(Shylin)", "히어로 수집 육성", "전투 및 액션"]
  },
  {
    name: "A-Hooking-Reward03A-UA",
    type: "VID",
    score: 27,
    rank: 17,
    grade: "보통",
    cluster: "캐릭터 수집 매력형 2",
    fileCount: 2,
    tags: ["압도적 보상", "실패", "분노 유도", "경쾌함", "보상", "용병 모집", "마그 탐험대", "Karbel", "히어로 수집 육성", "$100 가치 혜택 강조", "수집 및 도감", "손가락 지시선", "텍스트 오버레이", "심플"]
  },
  {
    name: "A-Character-Comics01A-DA",
    type: "BNR",
    score: 25,
    rank: 18,
    grade: "미흡",
    cluster: "캐릭터 수집 매력형",
    fileCount: 3,
    tags: ["캐릭터", "8인 실시간 전투", "비주얼 임팩트", "유닛 외형", "아트 퀄리티", "수집형RPG", "용병 모집(Gacha)", "마그 탐험대", "카르벨(Karbel)", "히어로 수집 육성", "렐릭 탐험 어드벤처", "코믹스 스타일 레이아웃", "수집 및 도감", "전투 및 액션"]
  },
  {
    name: "A-Character-Collection01A-UA",
    type: "VID",
    score: 22,
    rank: 19,
    grade: "미흡",
    cluster: "캐릭터 수집 매력형 2",
    fileCount: 1,
    tags: ["캐릭터", "질문", "선택형", "유닛 외형", "경쾌함", "수집형RPG", "전략성", "용병 모집(Gacha)", "DIY 픽업 시스템", "마그 탐험대", "비네사", "소피아", "베르네타", "히어로 수집 육성"]
  },
  {
    name: "A-Mob-Adventure01A-UA",
    type: "VID",
    score: 18,
    rank: 20,
    grade: "미흡",
    cluster: "캐릭터 수집 매력형",
    fileCount: 3,
    tags: ["비주얼 임팩트", "성장 비포애프터", "긴박함", "편의성", "전략성", "AFK 기능", "8인 실시간 전투", "고블린", "카르벨", "렐릭 탐험 어드벤처", "스마트폰 UI 팝업 연출", "시뮬레이션 및 관리", "장애물 및 도전", "텍스트 오버레이"]
  },
  {
    name: "A-Mob-Adventure02A-DA",
    type: "BNR",
    score: 16,
    rank: 21,
    grade: "미흡",
    cluster: "캐릭터 수집 매력형",
    fileCount: 3,
    tags: ["비주얼 임팩트", "아트 퀄리티", "수집형RPG", "5인 분대 전투", "거대 보스 레이드", "마그 탐험대", "고블린", "렐릭 탐험 어드벤처", "2.5D 입체 월드 강조", "장애물 및 도전", "전투 및 액션", "텍스트 오버레이", "자연", "야외 미학"]
  },
  {
    name: "A-Character-Life02A-DA",
    type: "BNR",
    score: 12,
    rank: 22,
    grade: "미흡",
    cluster: "캐릭터 수집 매력형",
    fileCount: 3,
    tags: ["캐릭터", "유닛 외형", "비주얼 임팩트", "아트 퀄리티", "수집형RPG", "수집형 RPG", "8인 실시간 전투", "렐릭 퀘스트", "현상금 수배", "마그 탐험대", "SD 히어로즈", "렐릭 탐험 어드벤처", "탐험 및 발견", "텍스트 오버레이"]
  },
  {
    name: "A-Character-Adventure03A-DA",
    type: "BNR",
    score: 3,
    rank: 23,
    grade: "미흡",
    cluster: "캐릭터 수집 매력형",
    fileCount: 2,
    tags: ["캐릭터", "유닛 외형", "비주얼 임팩트", "아트 퀄리티", "수집형 RPG", "8인 실시간 전투", "렐릭 퀘스트", "유물 시스템(Relic)", "마그 탐험대", "인간형 영웅 소대", "렐릭 탐험 어드벤처", "히어로 수집 육성", "수집 및 도감", "탐험 및 발견"]
  }
];

// ── 데이터 스토어 (localStorage 연동)
const STORAGE_KEY = 'pepph_creatives_v2';

function loadCreatives() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    }
  } catch(e) {}
  return DEFAULT_CREATIVES.map(c => ({ ...c }));
}

function saveCreatives(data) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch(e) {
    console.warn('localStorage 저장 실패:', e);
  }
}

function resetCreatives() {
  localStorage.removeItem(STORAGE_KEY);
  return DEFAULT_CREATIVES.map(c => ({ ...c }));
}

// ── 점수 기반 색상 helper
function scoreColor(score) {
  if (score >= 50) return '#5c6ef8';
  if (score >= 35) return '#26c281';
  if (score >= 20) return '#ffd234';
  return '#f44336';
}
function scoreClass(score) {
  if (score >= 50) return 'high';
  if (score >= 35) return 'mid';
  return 'low';
}

// ══════════════════════════════════════════
// 파이프라인 → 대시보드 연동 레이어
// 파이프라인에서 저장한 최신 차수 데이터를 읽어
// WINNING_TAGS / LOSING_TAGS / CLUSTER_INSIGHTS / creatives 를 덮어쓴다.
// ══════════════════════════════════════════

const PL_ROUNDS_KEY = 'ph_pipeline_rounds_v2'; // pipeline-data.js 와 동일한 키

/**
 * 파이프라인 최신 차수 데이터 로드
 * @returns {object|null}  최신 round 객체, 없으면 null
 */
function loadLatestPipelineRound() {
  try {
    const raw = localStorage.getItem(PL_ROUNDS_KEY);
    if (!raw) return null;
    const rounds = JSON.parse(raw);
    if (!Array.isArray(rounds) || !rounds.length) return null;
    return rounds[rounds.length - 1];
  } catch { return null; }
}

/**
 * 파이프라인 round → 대시보드 소재 배열로 변환
 * pipeline creative 구조: { name, type, conversions, cost, impressions, score, grade, cluster, tags, ipm, cpa }
 * dashboard creative 구조: { name, type, score, rank, grade, cluster, fileCount, tags }
 */
function pipelineCreativesToDashboard(plCreatives) {
  if (!plCreatives || !plCreatives.length) return [];
  // score 내림차순 rank 배정
  const sorted = [...plCreatives].sort((a, b) => b.score - a.score);
  return sorted.map((c, i) => ({
    name:      c.name,
    type:      c.type,
    score:     c.score,
    rank:      i + 1,
    grade:     c.grade,
    cluster:   c.cluster,
    fileCount: 1,
    tags:      (c.tags || []).filter(t => !t.startsWith('[MI]')), // [MI] 태그는 대시보드 노출 제외
    ipm:       c.ipm,
    cpa:       c.cpa,
    conversions: c.conversions,
    cost:      c.cost,
    impressions: c.impressions,
  }));
}

/**
 * 파이프라인 round.clusters → 대시보드 CLUSTER_INSIGHTS 형태로 변환
 */
function pipelineClustersToDashboard(plClusters, allCreatives) {
  if (!plClusters || !plClusters.length) return null;
  const result = {};
  plClusters.forEach(cl => {
    const members = allCreatives.filter(c => c.cluster === cl.name);
    const sorted  = [...members].sort((a, b) => b.score - a.score);
    result[cl.name] = {
      id:          cl.id || cl.name,
      name:        cl.name,
      description: cl.description || '',
      count:       cl.creativeCount || members.length,
      avgScore:    cl.avgScore,
      topTags:     (cl.topTags || []).slice(0, 8),
      weakTags:    [],                          // 파이프라인 데이터에 없으면 빈 배열
      successCause: '',
      failCause:   '',
      improvement: '',
      bestCreative:  sorted[0]?.name || '',
      worstCreative: sorted[sorted.length - 1]?.name || '',
    };
  });
  return result;
}

/**
 * 파이프라인 데이터를 대시보드에 적용한다.
 * 성공 시 true, 파이프라인 데이터 없으면 false 반환.
 */
function applyPipelineDataToDashboard() {
  const round = loadLatestPipelineRound();
  if (!round) return false;

  // 1) 소재 데이터 교체
  if (round.creatives && round.creatives.length) {
    window.AppData.creatives = pipelineCreativesToDashboard(round.creatives);
  }

  // 2) 승리·패배 태그 교체
  if (round.winningTags && round.winningTags.length) {
    WINNING_TAGS.length = 0;
    round.winningTags.forEach(t => WINNING_TAGS.push(t));
  }
  if (round.losingTags && round.losingTags.length) {
    LOSING_TAGS.length = 0;
    round.losingTags.forEach(t => LOSING_TAGS.push(t));
  }

  // 3) 군집 인사이트 교체
  if (round.clusters && round.clusters.length) {
    const newInsights = pipelineClustersToDashboard(
      round.clusters, window.AppData.creatives
    );
    if (newInsights) {
      Object.keys(CLUSTER_INSIGHTS).forEach(k => delete CLUSTER_INSIGHTS[k]);
      Object.assign(CLUSTER_INSIGHTS, newInsights);
    }
  }

  // 4) 태그 세트 갱신 (WIN_TAG_SET / LOSE_TAG_SET)
  WIN_TAG_SET.clear();
  LOSE_TAG_SET.clear();
  WINNING_TAGS.forEach(t => WIN_TAG_SET.add(t.tag));
  LOSING_TAGS.forEach(t => LOSE_TAG_SET.add(t.tag));

  // 5) 연동 메타 반환 (UI 배너용)
  return {
    roundName:  round.name,
    createdAt:  round.createdAt,
    count:      (round.creatives || []).length,
    clusters:   (round.clusters  || []).length,
    avgScore:   round.avgScore,
    winningFormula: round.winningFormula || '',
    exitPattern:    round.exitPattern    || '',
  };
}

// ── 태그 승리/패배 여부
const WIN_TAG_SET  = new Set(WINNING_TAGS.map(t => t.tag));
const LOSE_TAG_SET = new Set(LOSING_TAGS.map(t => t.tag));

function tagClass(tag) {
  if (WIN_TAG_SET.has(tag)) return 'win';
  if (LOSE_TAG_SET.has(tag)) return 'lose';
  return '';
}

// ── 전역 상태
window.AppData = {
  creatives: loadCreatives(),
  save() { saveCreatives(this.creatives); },
  reset() { this.creatives = resetCreatives(); }
};

// ── 통계 계산
function calcStats(data) {
  const vid = data.filter(c => c.type === 'VID');
  const bnr = data.filter(c => c.type === 'BNR');
  const avg = arr => arr.length ? (arr.reduce((s,c) => s + c.score, 0) / arr.length).toFixed(1) : 0;
  return {
    total: data.length,
    topScore: Math.max(...data.map(c => c.score)),
    avgScore: avg(data),
    vidAvg: avg(vid),
    bnrAvg: avg(bnr),
    vidCount: vid.length,
    bnrCount: bnr.length
  };
}
