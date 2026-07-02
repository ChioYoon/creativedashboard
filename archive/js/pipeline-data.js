/**
 * Pepp Heroes – Pipeline Data Store
 * localStorage 기반 차수 히스토리 관리
 */

// ── 스토리지 키
const PL_KEYS = {
  ROUNDS:    'ph_pipeline_rounds_v2',     // 전체 차수 배열
  CURRENT:   'ph_pipeline_current_v2',    // 현재 작업 중인 차수 임시 데이터
  INSIGHTS:  'ph_pipeline_insights_v2',   // 누적 인사이트 히스토리
};

// ── 차수 데이터 구조 정의
/**
 * Round = {
 *   id: string (타임스탬프),
 *   name: string,
 *   uploader: string,
 *   memo: string,
 *   createdAt: number,
 *   rawCount: number,           // 업로드된 전체 행 수
 *   validCount: number,         // 분석 대상(BNR+VID) 수
 *   params: { wConv, wCpa, wIpm, minCluster, minSupport, coOccur },
 *   creatives: Creative[],      // 분석 완료된 소재 배열
 *   clusters: Cluster[],        // 군집 배열
 *   winningTags: TagImpact[],
 *   losingTags: TagImpact[],
 *   winningFormula: string,
 *   exitPattern: string,
 *   insightMemos: InsightMemo[],
 *   avgScore: number,
 *   topScore: number,
 * }
 *
 * Creative = {
 *   name, type, conversions, cost, impressions, clicks,
 *   ctr, ipm, cpa, score, grade, cluster, tags[]
 * }
 *
 * Cluster = {
 *   id, name, creatives[], avgScore, topTags[], description
 * }
 *
 * InsightMemo = {
 *   id, type('유지'|'변경'|'신규'|'주의'), content, createdAt
 * }
 */

// ── 스토어 로드
function plLoadRounds() {
  try {
    const r = localStorage.getItem(PL_KEYS.ROUNDS);
    return r ? JSON.parse(r) : [];
  } catch { return []; }
}

function plSaveRounds(rounds) {
  localStorage.setItem(PL_KEYS.ROUNDS, JSON.stringify(rounds));
}

function plLoadCurrent() {
  try {
    const c = localStorage.getItem(PL_KEYS.CURRENT);
    return c ? JSON.parse(c) : null;
  } catch { return null; }
}

function plSaveCurrent(data) {
  localStorage.setItem(PL_KEYS.CURRENT, JSON.stringify(data));
}

function plClearCurrent() {
  localStorage.removeItem(PL_KEYS.CURRENT);
}

function plLoadInsights() {
  try {
    const i = localStorage.getItem(PL_KEYS.INSIGHTS);
    return i ? JSON.parse(i) : [];
  } catch { return []; }
}

function plSaveInsights(insights) {
  localStorage.setItem(PL_KEYS.INSIGHTS, JSON.stringify(insights));
}

// ── 현재 작업 세션
window.PipelineSession = {
  roundName: '',
  uploader: '',
  memo: '',
  rawRows: [],          // 원본 파싱 rows
  validRows: [],        // BNR+VID만 필터된 rows
  validationResult: null,
  params: { wConv:40, wCpa:35, wIpm:25, minCluster:3, minSupport:30, coOccur:2 },
  creatives: [],
  clusters: [],
  tagImpacts: [],
  insightMemos: [],
  winningFormula: '',
  exitPattern: '',
  prevRoundId: null,
};

// ── 이전 차수 인사이트 누적값 조회 (다음 군집화 참고용)
function plGetAccumulatedInsights() {
  const rounds = plLoadRounds();
  if (!rounds.length) return null;
  const latest = rounds[rounds.length - 1];
  return {
    winningTags:    latest.winningTags    || [],
    losingTags:     latest.losingTags     || [],
    clusters:       latest.clusters       || [],
    winningFormula: latest.winningFormula || '',
    exitPattern:    latest.exitPattern    || '',
    insightMemos:   latest.insightMemos   || [],
  };
}

// ── 샘플 소재 데이터 (실제 PH 사전예약 US_SEA 캠페인 기준 – 다중 태그 컬럼 구조)
const SAMPLE_CSV_DATA = `소재명,유형,전환,비용,노출수,클릭수,hooking_strategy,text_analysis_core_usp,title_specific_system,title_specific_mechanic,title_specific_faction_race,title_specific_identified_character,title_specific_theme,gameplay,visual_technique,environment,emotion,character_object,art_style,marketer_insight
A-Character-Adventure01A-DA,BNR,22,127881,2526,152,"비주얼 임팩트, 캐릭터/유닛 외형",,"5인 분대 전투, 수집형 RPG",,"마그 탐험대, 고블린",카르벨(Karbel),렐릭 탐험 어드벤처,2.5D 입체 월드 강조,"전투 및 액션, 탐험 및 발견",텍스트 오버레이,자연/야외 미학,"도전과 승부욕, 수집욕/소유욕","인간형 영웅, SD/치비 캐릭터, 거대 보스","2.5D 입체 그래픽, 2D 일러스트","와이드 뷰를 통해 거대 보스와의 대립 구도 노출, 레이드 콘텐츠 암시. 타겟 심리: 작지만 강력한 히어로 부대 전투의 스케일감. 보상 정보 추가 시 전환율 급증 예상."
A-Character-Adventure02A-DA,BNR,1,2199,79,4,"캐릭터/유닛 외형, 비주얼 임팩트","아트 퀄리티, 릴리즈 예고, 캐릭터, 수집형RPG",용병 모집(Gacha),렐릭 퀘스트,마그 탐험대,샤일린(Shylin),렐릭 탐험 어드벤처,,수집 및 도감,텍스트 오버레이,자연/야외 미학,"수집욕/소유욕, 참여와 임장감",,"2.5D 입체 그래픽, 2D 일러스트","메인 캐릭터 샤일린의 비주얼 전면 노출로 고퀄리티 수집형 RPG 인지. 양산형 RPG에 지친 유저에게 2.5D 신선한 미학적 만족감 제공. 캐릭터별 시너지 강조 소재로 확장 가능."
A-Character-Keyart01A-DA,BNR,1,7145,70,6,"캐릭터/유닛 외형, 비주얼 임팩트","아트 퀄리티, 수집형RPG",수집형 RPG,분대 조합,마그 탐험대,"샤일린(Shylin), 메인 플레이어(PC)",렐릭 탐험 어드벤처,,수집 및 도감,텍스트 오버레이,자연/야외 미학,수집욕/소유욕,인간형 영웅,"2.5D 입체 그래픽, 2D 일러스트","50여 종 영웅 중 핵심 캐릭터 앙상블 배치. 독보적인 2.5D 아트 퀄리티 직관 전달. 브랜딩 초기 단계에서 높은 CTR 기대."
A-Character-Keyart02A-DA,BNR,1,5076,66,9,"캐릭터/유닛 외형, 비주얼 임팩트","아트 퀄리티, 캐릭터",수집형 RPG,8인 실시간 전투,마그 탐험대,"플레이어 캐릭터(PC), 주요 영웅 6종",히어로 수집 육성,,수집 및 도감,텍스트 오버레이,심플/클린 UI,"수집욕/소유욕, 참여와 임장감","인간형 영웅, 군단/대규모 유닛","2.5D 입체 그래픽, 2D 일러스트","다양한 영웅 라인업 노출로 수집의 재미 직관 전달. 글로벌 시장 친숙 아트 스타일. '$100 Worth Rewards' 텍스트 결합 시 전환율 극대화 예상."
A-Character-Life01A-DA,BNR,1,3458,96,5,"캐릭터/유닛 외형, 비주얼 임팩트","아트 퀄리티, 전략성, 수집형RPG","8인 실시간 전투, 8종 직업 및 4종 클래스 체계","렐릭 퀘스트, 8인 실시간 전투",마그 탐험대,카르벨(Karbel),"렐릭 탐험 어드벤처, 히어로 수집 육성",,"수집 및 도감, 탐험 및 발견","텍스트 오버레이, 심플/클린 UI",자연/야외 미학,"휴식과 힐링, 수집욕/소유욕","SD/치비 캐릭터, 인간형 영웅","2.5D 입체 그래픽, 2D 일러스트","가로형 배너 최적화로 광활한 2.5D 월드 공간감 표현. 어드벤처 요소 집중 유저층 타겟팅. 리마케팅 시 효과적, 우측 여백에 히어로 수집 문구 삽입 권장."
A-Character-Keyart02B-DA,BNR,0,1230,15,2,"캐릭터/유닛 외형, 비주얼 임팩트","아트 퀄리티, 캐릭터",수집형 RPG,8인 실시간 전투,마그 탐험대,"플레이어 캐릭터(PC), 주요 영웅 6종",히어로 수집 육성,,수집 및 도감,텍스트 오버레이,심플/클린 UI,"수집욕/소유욕, 참여와 임장감","인간형 영웅, 군단/대규모 유닛","2.5D 입체 그래픽, 2D 일러스트","1:1 정방형 비율로 캐릭터 밀도 높여 풍성한 수집 볼륨 강조. 인스타그램/페이스북 피드 광고 준수한 효율 예상."
A-Mob-Adventure01A-DA,BNR,1,2791,75,8,"캐릭터/유닛 외형, 비주얼 임팩트","아트 퀄리티, 캐릭터, 수집형RPG",8인 실시간 전투,8종 직업 및 4종 클래스 체계,고블린,,렐릭 탐험 어드벤처,몬스터 군단 중심의 구도,"전투 및 액션, 탐험 및 발견",텍스트 오버레이,자연/야외 미학,"참여와 임장감, 수집욕/소유욕","SD/치비 캐릭터, 군단/대규모 유닛","2.5D 입체 그래픽, 2D 일러스트","영웅 중심 정형화된 광고 탈피, 몬스터 군단 전면 배치로 독보적 2.5D 아트 스타일 소구. 고관여 RPG 유저층에서 높은 CTR 예상."
A-Mob-Adventure01B-DA,BNR,0,2059,30,5,"캐릭터/유닛 외형, 비주얼 임팩트","아트 퀄리티, 캐릭터, 수집형RPG",8인 실시간 전투,8종 직업 및 4종 클래스 체계,고블린,,렐릭 탐험 어드벤처,몬스터 군단 중심의 구도,"전투 및 액션, 탐험 및 발견",텍스트 오버레이,자연/야외 미학,"참여와 임장감, 수집욕/소유욕","SD/치비 캐릭터, 군단/대규모 유닛","2.5D 입체 그래픽, 2D 일러스트","1:1 비율로 개별 캐릭터 디테일 강조, 3등신 SD 귀여움과 전투 긴장감 공존. SNS 피드에서 아트 퀄리티만으로 시선 정지 가능성."
A-Character-Collection01A-UA,VID,1,2543,86,6,"질문/선택형, 캐릭터/유닛 외형","캐릭터, 수집형RPG, 전략성",용병 모집(Gacha),DIY 픽업 시스템,마그 탐험대,"비네사, 소피아, 베르네타",히어로 수집 육성,캐릭터 선택 UI 강조,수집 및 도감,"텍스트 오버레이, 분할 화면",심플/클린 UI,수집욕/소유욕,"SD/치비 캐릭터, 인간형 영웅",2D 일러스트,"Choose your hero 직접적 카피로 능동적 참여 유도. 뽑기의 결과보다 과정과 선택의 재미 강조. 높은 클릭률로 초기 유저 획득 캠페인에 적합."
A-Character-Collection01B-UA,VID,2,3246,69,2,"질문/선택형, 캐릭터/유닛 외형","캐릭터, 수집형RPG, 전략성",용병 모집(Gacha),DIY 픽업 시스템,마그 탐험대,"휴고, 카르벨, 모나드",히어로 수집 육성,남성 캐릭터 위주 배치,수집 및 도감,"텍스트 오버레이, 분할 화면",심플/클린 UI,수집욕/소유욕,"SD/치비 캐릭터, 인간형 영웅",2D 일러스트,"Collection01A와 대조되는 캐릭터 구성으로 타겟 취향별 효율 교차 분석. 탱커와 딜러 중심 덱 구성 선호 유저 공략."
A-Character-Combat01A-UA,VID,1,3170,77,2,"비주얼 임팩트, 캐릭터/유닛 외형","아트 퀄리티, 캐릭터, 수집형RPG, 전략성",용병 모집,스킬 컷신 연출,마그 탐험대,"Vinessa, Sophia, Berneta",렐릭 탐험 어드벤처,캐릭터별 스킬 특징 강조,전투 및 액션,"텍스트 오버레이, 클로즈업 및 줌",자연/야외 미학,"도전과 승부욕, 수집욕/소유욕","인간형 영웅, SD/치비 캐릭터, 성장 지표","2.5D 입체 그래픽, 2D 일러스트","인게임 실제 전투 씬과 캐릭터 일러스트 교차 편집으로 시각적 몰입도 극대화. 캐릭터 스킬과 시너지 조합에 대한 전략적 호기심 자극."
A-Character-Combat01B-UA,VID,1,7846,75,4,"비주얼 임팩트, 캐릭터/유닛 외형","아트 퀄리티, 캐릭터, 수집형RPG, 전략성",용병 모집,스킬 컷신 연출,마그 탐험대,"Vinessa, Sophia, Berneta",렐릭 탐험 어드벤처,캐릭터별 스킬 특징 강조,전투 및 액션,"텍스트 오버레이, 클로즈업 및 줌",자연/야외 미학,"도전과 승부욕, 수집욕/소유욕","인간형 영웅, SD/치비 캐릭터, 성장 지표","2.5D 입체 그래픽, 2D 일러스트","SSR 비네사 독보적 비주얼 초반 3초 내 배치로 RPG 팬덤 시선 고정. 캐릭터 소유욕 강한 유저층 페인 포인트 해소. 캐릭터별 스킬 콤보 시리즈로 소재 확장 용이."
A-Character-Combat02A-UA,VID,0,6136,100,5,"비주얼 임팩트, 캐릭터/유닛 외형","전략성, 아트 퀄리티",용병 모집,8인 실시간 전투,마그 탐험대,"Hugo, Monad, Karbel",히어로 수집 육성,,전투 및 액션,"텍스트 오버레이, 클로즈업 및 줌",자연/야외 미학,"도전과 승부욕, 수집욕/소유욕","인간형 영웅, SD/치비 캐릭터, 성장 지표","2.5D 입체 그래픽, 2D 일러스트","16:9 뷰로 넓은 전장과 광역 스킬 이펙트 강조. 화려한 볼거리와 묵직한 타격감 추구 심리 공략. 유튜브 범퍼/인스트림에서 전투 선호 유저 높은 전환율 기대."
A-Character-Combat02B-UA,VID,0,5807,96,8,"비주얼 임팩트, 캐릭터/유닛 외형","전략성, 아트 퀄리티",용병 모집,8인 실시간 전투,마그 탐험대,"Hugo, Monad, Karbel",히어로 수집 육성,,전투 및 액션,"텍스트 오버레이, 클로즈업 및 줌",자연/야외 미학,"도전과 승부욕, 수집욕/소유욕","인간형 영웅, SD/치비 캐릭터, 성장 지표","2.5D 입체 그래픽, 2D 일러스트","소피아의 생존과 지원 능력 강조로 전략적 플레이 중시 유저 어필. 팀 시너지 중시 코어 유저 니즈 타격. 비네사 소재와 A/B 테스트로 타겟별 선호 캐릭터 최적화 가능."
A-Character-Combat02C-UA,VID,3,3952,77,8,"비주얼 임팩트, 캐릭터/유닛 외형","전략성, 아트 퀄리티",용병 모집,8인 실시간 전투,마그 탐험대,"Hugo, Monad, Karbel",히어로 수집 육성,,전투 및 액션,"텍스트 오버레이, 클로즈업 및 줌",자연/야외 미학,"도전과 승부욕, 수집욕/소유욕","인간형 영웅, SD/치비 캐릭터, 성장 지표","2.5D 입체 그래픽, 2D 일러스트","탱커, 마법사, 딜러 역할 명확히 보여주는 직관적 구성. 클래스 기반 파티 구성 니즈 충족. 역할군 조합의 재미 텍스트 보강 시 효율 증가 예상."
A-Charater-Collection01A-UA,VID,0,3633,100,0,"질문/선택형, 캐릭터/유닛 외형","아트 퀄리티, 전략성",용병 모집,DIY 픽업 시스템,마그 탐험대,Vinessa,히어로 수집 육성,,수집 및 도감,"텍스트 오버레이, 클로즈업 및 줌",심플/클린 UI,"수집욕/소유욕, 만족과 성취감","인간형 영웅, SD/치비 캐릭터","2.5D 입체 그래픽, 2D 일러스트","여성 마법사 캐릭터 선호 유저를 위한 픽 연출. 매력적인 원화와 인게임 갭 모에 자극. 미소녀 일러스트 선호 타겟에게 긍정적 지표 확보 예측."
A-Charater-Collection01B-UA,VID,5,5196,93,0,"질문/선택형, 캐릭터/유닛 외형","아트 퀄리티, 전략성",용병 모집,DIY 픽업 시스템,마그 탐험대,Vinessa,히어로 수집 육성,,수집 및 도감,"텍스트 오버레이, 클로즈업 및 줌",심플/클린 UI,"수집욕/소유욕, 만족과 성취감","인간형 영웅, SD/치비 캐릭터","2.5D 입체 그래픽, 2D 일러스트","세로형 피드에 맞춘 캐릭터 선택 화면 강조. 캐주얼하게 접근하기 좋은 디자인으로 허들 저하. 틱톡/쇼츠 타겟에게 즉각적인 설치 훅 제공."
A-Charater-Collection01C-UA,VID,3,4882,78,3,"질문/선택형, 캐릭터/유닛 외형","아트 퀄리티, 전략성",용병 모집,DIY 픽업 시스템,마그 탐험대,Hugo,히어로 수집 육성,,수집 및 도감,"텍스트 오버레이, 클로즈업 및 줌",심플/클린 UI,"수집욕/소유욕, 만족과 성취감","인간형 영웅, SD/치비 캐릭터","2.5D 입체 그래픽, 2D 일러스트","그리드 UI를 통해 풍부한 캐릭터 풀 어필. 수집 욕구 자극하며 게임 볼륨감 인식. 캐릭터 풀 강조 엔드카드 활용 시 높은 잔존율 기대."
A-Charater-Collection01D-UA,VID,0,3268,90,0,"질문/선택형, 캐릭터/유닛 외형","아트 퀄리티, 전략성",용병 모집,DIY 픽업 시스템,마그 탐험대,Hugo,히어로 수집 육성,캐릭터 픽(Pick) 연출,수집 및 도감,"텍스트 오버레이, 클로즈업 및 줌",심플/클린 UI,"수집욕/소유욕, 만족과 성취감","인간형 영웅, SD/치비 캐릭터","2.5D 입체 그래픽, 2D 일러스트","유저가 직접 영웅을 선택하는 듯한 인터랙티브한 경험 제공. 내가 직접 선택한 캐릭터 활약에 대한 기대감 부여. 다양한 영웅 선택지 반복 노출로 취향 저격 효과 유도."
A-Hooking-Reward01A-FK,VID,1,6026,95,6,"실패/분노 유도, 압도적 보상",보상,용병 모집,우호도 시스템,마그 탐험대,카르벨(Karbel),히어로 수집 육성,페이크 플레이(구출 미니게임) 형식 활용,퍼즐 및 논리,"손가락 지시선, 텍스트 오버레이",자연/야외 미학,"도전과 승부욕, 만족과 성취감","SD/치비 캐릭터, 재화/보물상자",2D 일러스트,"위기 상황 해결이라는 미션 부여로 본능적인 참여 유도. $100 가치 실질 보상 미끼로 전환 유도. 쉬운 조작 페인 포인트 해소, 런칭 캠페인 메인 소재로 적합."
A-Hooking-Reward01B-FK,VID,0,6064,82,5,"실패/분노 유도, 압도적 보상",보상,용병 모집,우호도 시스템,마그 탐험대,카르벨(Karbel),히어로 수집 육성,페이크 플레이(구출 미니게임) 형식 활용,퍼즐 및 논리,"손가락 지시선, 텍스트 오버레이",자연/야외 미학,"도전과 승부욕, 만족과 성취감","SD/치비 캐릭터, 재화/보물상자",2D 일러스트,"숏폼 환경 최적화 세로형 9:16 비율로 터치 인터랙션 극대화. 스와이프 멈추게 하는 직관적 구조로 즉각적인 도파민 충족 및 FOMO 자극. 카르벨 외 인기 캐릭터 활용 A/B 테스트 권장."
A-Hooking-Reward02A-UA,VID,1,4705,95,3,"압도적 보상, 실패/분노 유도",보상,용병 모집,,마그 탐험대,Karbel,히어로 수집 육성,$100 가치 혜택 강조,수집 및 도감,"손가락 지시선, 텍스트 오버레이",심플/클린 UI,"만족과 성취감, 수집욕/소유욕","재화/보물상자, SD/치비 캐릭터","2D 일러스트, 2.5D 입체 그래픽","보상을 놓칠 수 있다는 부정적 후킹과 시간 제한으로 강력한 클릭 동기 부여. $100 가치와 SR 등급 확정 명시로 기대 수익 구체화. CVR 매우 높을 것으로 예상."
A-Hooking-Reward02B-UA,VID,1,3953,82,1,"압도적 보상, 실패/분노 유도",보상,용병 모집,,마그 탐험대,Karbel,히어로 수집 육성,$100 가치 혜택 강조,수집 및 도감,"손가락 지시선, 텍스트 오버레이",심플/클린 UI,"만족과 성취감, 수집욕/소유욕","재화/보물상자, SD/치비 캐릭터","2D 일러스트, 2.5D 입체 그래픽","스킵 방지하는 도발적 문구와 카운트다운 타이머로 이탈률 최소화. 보상 상실에 대한 FOMO 심리 자극. UA 매체 보상형 인벤토리에서 압도적인 CVR 예상."
A-Mob-Adventure01A-UA,VID,0,1927,70,1,"비주얼 임팩트, 성장 비포애프터","편의성, 전략성",AFK 기능,8인 실시간 전투,고블린,카르벨,렐릭 탐험 어드벤처,스마트폰 UI 팝업 연출,"시뮬레이션 및 관리, 장애물 및 도전","텍스트 오버레이, 클로즈업 및 줌",자연/야외 미학,"도전과 승부욕, 만족과 성취감","SD/치비 캐릭터, 성장 지표, 군단/대규모 유닛",2.5D 입체 그래픽,"16:9 가로 화면 활용 영지와 고블린 대비 극대화. 쉬운 레벨업 카피로 진입 장벽 낮추고 성장 쾌감 강조. 거대 보스 레이드 연계 대규모 전투 소재로 확장 가능."
A-Mob-Adventure01B-UA,VID,1,3624,75,1,"비주얼 임팩트, 성장 비포애프터","편의성, 전략성",AFK 기능,8인 실시간 전투,고블린,카르벨,렐릭 탐험 어드벤처,스마트폰 UI 팝업 연출,"시뮬레이션 및 관리, 장애물 및 도전","텍스트 오버레이, 클로즈업 및 줌",자연/야외 미학,"도전과 승부욕, 참여와 임장감","SD/치비 캐릭터, 성장 지표, 군단/대규모 유닛",2.5D 입체 그래픽,"일상적인 평화가 깨지는 경고 연출로 시청자 아드레날린 자극, 영상 몰입도 향상. 쉬운 레벨업 카피로 진입 장벽 낮추고 성장 쾌감 강조. 거대 보스 레이드 연계 소재로 확장 가능."
A-Mob-Adventure01C-UA,VID,0,4502,77,1,"비주얼 임팩트, 성장 비포애프터","편의성, 전략성",AFK 기능,8인 실시간 전투,고블린,카르벨,렐릭 탐험 어드벤처,스마트폰 UI 팝업 연출,"시뮬레이션 및 관리, 장애물 및 도전","텍스트 오버레이, 클로즈업 및 줌",자연/야외 미학,"도전과 승부욕, 만족과 성취감","SD/치비 캐릭터, 성장 지표, 군단/대규모 유닛",2.5D 입체 그래픽,"틱톡/릴스 세로형 피드에 스마트폰 목업 UI 정중앙 배치. 평화로운 마을 습격 반전으로 초반 이탈 방지. 라이트/미드코어 RPG 유저들의 성장 스트레스 해소."`;


// ── 등급 산출
function scoreToGrade(score, q1, q2, q3) {
  if (score >= q3) return '최우수';
  if (score >= q2) return '우수';
  if (score >= q1) return '보통';
  return '미흡';
}

// ── 사분위수 계산
function calcQuartiles(scores) {
  const s = [...scores].sort((a,b) => a-b);
  const q = p => {
    const pos = (s.length - 1) * p;
    const lo = Math.floor(pos), hi = Math.ceil(pos);
    return s[lo] + (s[hi] - s[lo]) * (pos - lo);
  };
  return { q1: q(0.25), q2: q(0.5), q3: q(0.75) };
}
