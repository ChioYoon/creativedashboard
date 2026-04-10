# Step 2 군집화 분석 - 상세 기술 설명서

**작성일**: 2026-04-10  
**버전**: v1.0  
**프로젝트**: Com2uS R팀 소재 분석 시스템

---

## 📋 목차

1. [하이브리드 알고리즘 상세 설명](#1-하이브리드-알고리즘-상세-설명)
2. [사용자 정의 컬럼 기반 군집화](#2-사용자-정의-컬럼-기반-군집화)
3. [인사이트 자동화 방법론](#3-인사이트-자동화-방법론)

---

## 1. 하이브리드 알고리즘 상세 설명

### 1.1 왜 "하이브리드"인가?

기존 알고리즘은 **"태그가 비슷하면 같은 군집"** 이라는 단일 기준만 사용합니다.  
하이브리드는 **"태그도 비슷하고, 성과도 비슷한 소재끼리 묶는다"** 는 복합 기준을 사용합니다.

```
[기존 방식: 태그만]           [하이브리드: 태그 + 성과]
                              
소재A: Character, Hooking     소재A: Character, Hooking | Score 85점  ←┐
소재B: Character, Mob    →    소재B: Character, Mob     | Score 82점  ←┼─ 군집1 (고성과)
소재C: Character, Hooking →   소재C: Character, Hooking | Score 78점  ←┘
소재D: Character, Mob         소재D: Character, Mob     | Score 35점  ←─ 군집2 (저성과, 분리!)
소재E: Character, Hooking     소재E: Character, Hooking | Score 31점  ←┘
     └─── 모두 같은 군집 ───┘   └─── 성과 차이로 2개 군집 ───────────┘
```

> **실무적 의미**: "같은 Character 소재인데 왜 이 소재만 성과가 나쁠까?" 라는 질문에  
> 하이브리드는 자동으로 "고성과 Character 군집" vs "저성과 Character 군집"으로 분리해줍니다.

---

### 1.2 4단계 Phase 흐름도

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  [INPUT]                                                                    │
│  소재 156개 (BNR+VID)                                                       │
│  - 소재명, 유형, 전환, CPA, IPM, ROAS (Step 1 Score 연동)                  │
│  - 태그 컬럼 (USP, Concept, hooking_strategy, character_object, 등)         │
│  - 마케터 인사이트 ([MI] 태그)                                               │
│                                                                             │
│         ↓                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ PHASE 1: 태그 기반 초기 군집화 (Union-Find + IQR 노이즈 필터링)       │  │
│  │                                                                      │  │
│  │  Step 1.1 태그 빈도 통계 계산                                         │  │
│  │  Step 1.2 IQR 기반 노이즈 태그 제거                                   │  │
│  │  Step 1.3 태그 동시출현 행렬 계산 ([MI] 1.5배 가중)                   │  │
│  │  Step 1.4 적응형 임계값 계산 (소재 수에 따른 자동 조정)               │  │
│  │  Step 1.5 Union-Find 태그 그룹화                                      │  │
│  │  Step 1.6 소재 → 초기 군집 할당                                       │  │
│  │                                                                      │  │
│  │  결과: 12개 초기 군집 생성                                            │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│         ↓                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ PHASE 2: 성과 기반 군집 정제 (Z-Score 이상치 분리)                    │  │
│  │                                                                      │  │
│  │  Step 2.1 각 군집의 성과 분포 분석 (평균, 표준편차)                   │  │
│  │  Step 2.2 이상치 탐지 (Z-Score > 2.0 = 평균 ± 2σ 벗어난 소재)        │  │
│  │  Step 2.3 이상치 소재 분리 (최소 크기 충족 시 새 군집 생성)            │  │
│  │  Step 2.4 최종 군집 수 검증 및 조정                                   │  │
│  │                                                                      │  │
│  │  결과: 12개 → 8개 정제된 군집 (크기 미달 군집 병합)                   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│         ↓                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ PHASE 3: 인사이트 자동 생성 (패턴 분석 + 이전 차수 비교)              │  │
│  │                                                                      │  │
│  │  Step 3.1 군집별 TF-IDF 태그 추출 (특징 태그 선별)                   │  │
│  │  Step 3.2 승리 공식 추출 (상위 25% 군집의 공통 패턴)                  │  │
│  │  Step 3.3 중단 패턴 추출 (하위 25% 군집의 위험 신호)                  │  │
│  │  Step 3.4 이전 차수 군집과 유사도 비교 (Jaccard 유사도)               │  │
│  │  Step 3.5 트렌드 분석 (성과 변화, 군집 생성/소멸)                     │  │
│  │                                                                      │  │
│  │  결과: 승리 공식 3개 + 중단 패턴 2개 + 트렌드 5개                     │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│         ↓                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ PHASE 4: 품질 평가 (Silhouette + 3개 지표 → 종합 등급)                │  │
│  │                                                                      │  │
│  │  Step 4.1 Silhouette Score (군집 내 응집도 vs 군집 간 분리도)          │  │
│  │  Step 4.2 성과 분리도 (군집 간 평균 Score 차이)                        │  │
│  │  Step 4.3 크기 균형도 (군집 간 소재 수 균형)                           │  │
│  │  Step 4.4 태그 일관성 (군집 내 태그 일치율)                            │  │
│  │  Step 4.5 종합 등급 산출 (S/A/B/C)                                    │  │
│  │                                                                      │  │
│  │  결과: 품질 점수 87.3점 (A등급)                                        │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│         ↓                                                                   │
│  [OUTPUT]                                                                   │
│  - 8개 군집 + 메타데이터                                                    │
│  - 승리 공식 3개 + 중단 패턴 2개                                            │
│  - 품질 등급 A (87.3점)                                                     │
│  - 이전 차수 대비 트렌드 5건                                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 1.3 Phase 1 상세: 태그 기반 초기 군집화

#### 1.3.1 Step 1.1~1.2: IQR 기반 노이즈 필터링

**기존 방식의 문제점**:
```
기존: 소재 수의 55% 이상 등장하는 태그 → 제거 (고정 비율)
문제: 소재가 100개일 때와 20개일 때 기준이 달라 일관성 없음
```

**IQR 방식 (개선)**:
```javascript
// 태그 빈도의 통계적 분포를 활용
const freqValues = Object.values(tagFreq).sort((a, b) => a - b);

// Q1 (25th percentile), Q3 (75th percentile) 계산
const q1 = freqValues[Math.floor(freqValues.length * 0.25)];
const q3 = freqValues[Math.floor(freqValues.length * 0.75)];
const iqr = q3 - q1;

// 이상치 기준 (Tukey's Fence)
const NOISE_UPPER = q3 + 1.5 * iqr;  // 너무 흔한 태그 제거
const NOISE_LOWER = q1 - 1.5 * iqr;  // 너무 희귀한 태그 제거 (보통 0 이하)

// [MI] 태그는 빈도 무관, 마케터 의도이므로 항상 포함
const discriminativeTags = Object.entries(tagFreq).filter(([tag, cnt]) => {
  if (tag.startsWith('[MI]')) return true;           // MI 태그: 항상 포함
  if (cnt <= Math.max(NOISE_LOWER, 1)) return false; // 너무 희귀: 제거
  if (cnt >= NOISE_UPPER) return false;              // 너무 흔함: 제거
  return true;                                       // 차별성 있는 태그: 보존
});
```

**시각적 설명**:
```
태그 빈도 분포:

빈도
 1개: [███] 독점태그 (태그A, 태그B, ...)      ← NOISE_LOWER 이하 → 제거
 3개: [█████] 소수태그
 8개: [████████████] ← Q1 (하위 25%)
15개: [███████████████████████] ← 중간값
25개: [████████████████████████████████] ← Q3 (상위 75%)
28개: [████████████████████████████████████] ← NOISE_UPPER
40개: [████████████████████████████████████████████████████] 공통태그 → 제거
55개: [████████████████████████████████████████████████████████████████████]

                [보존 구간: NOISE_LOWER ~ NOISE_UPPER]
                ↑ 이 범위의 태그만 군집화에 사용
```

#### 1.3.2 Step 1.3~1.4: 적응형 임계값 계산

**기존 문제**:
```
기존: 소재 수 × 0.15 (고정 비율) → 소재 20개 = 임계값 3, 소재 200개 = 임계값 30
문제: 소재가 200개면 거의 모든 태그가 병합되어 군집이 1~2개로 과합병
```

**적응형 임계값 (개선)**:
```javascript
function calculateAdaptiveThreshold(n, tagFreq) {
  // 1. 기본 임계값: 소재 수의 로그 스케일
  const baseThreshold = Math.max(2, Math.log2(n) * 1.5);
  
  // 2. 태그 다양성에 따른 조정
  const uniqueTagCount = Object.keys(tagFreq).length;
  const avgTagsPerCreative = Object.values(tagFreq).reduce((a, b) => a + b, 0) / n;
  const diversityFactor = Math.min(1.5, uniqueTagCount / (n * avgTagsPerCreative));
  
  // 3. 최종 임계값
  return baseThreshold * diversityFactor;
}

// 예시:
// n=20: baseThreshold = max(2, log2(20)*1.5) = max(2, 6.5) = 6.5
// n=100: baseThreshold = max(2, log2(100)*1.5) = max(2, 9.97) = 9.97
// n=200: baseThreshold = max(2, log2(200)*1.5) = max(2, 11.5) = 11.5
// → 소재 수가 많아져도 임계값이 선형이 아닌 로그 스케일로 천천히 증가
```

#### 1.3.3 Step 1.5~1.6: Union-Find 태그 그룹화

```
태그들의 동시출현 관계:

Character ─── Hooking   (함께 등장 빈도: 45회 ≥ 임계값 9.97 → 병합)
Character ─── Female    (함께 등장 빈도: 38회 ≥ 임계값 9.97 → 병합)
Mob       ─── Combat    (함께 등장 빈도: 29회 ≥ 임계값 9.97 → 병합)
Adventure ─── Fantasy   (함께 등장 빈도: 21회 ≥ 임계값 9.97 → 병합)
Character ─── Mob       (함께 등장 빈도: 5회  < 임계값 9.97 → 분리!!)
                                          ↑
                          이 때문에 Character 군집과 Mob 군집이 분리됨

결과 태그 그룹:
Group A: {Character, Hooking, Female, Action, FastPace}
Group B: {Mob, Combat, Strategy, Competitive}
Group C: {Adventure, Fantasy, Exploration, Story}
Group D: {기타 단독 태그들}

소재 → 군집 할당:
소재X (태그: Character, Hooking) → Group A (매칭 점수 2.0 > 임계값 0.5) → 군집A
소재Y (태그: Mob, Combat)        → Group B (매칭 점수 2.0 > 임계값 0.5) → 군집B
소재Z (태그: Character, Combat)  → Group A (Character 점수 1.0 > Mob 점수 0) → 군집A (주 소속)
```

---

### 1.4 Phase 2 상세: 성과 기반 군집 정제

#### 1.4.1 Z-Score 기반 이상치 탐지

```javascript
function phasePerformanceRefinement(clusters, minClusterSize) {
  const result = [];
  
  clusters.forEach(cluster => {
    const scores = cluster.creatives.map(c => c.totalScore);
    
    // 1. 성과 통계 계산
    const mean = scores.reduce((a, b) => a + b, 0) / scores.length;
    const std  = Math.sqrt(
      scores.map(s => (s - mean) ** 2).reduce((a, b) => a + b, 0) / scores.length
    );
    
    // 2. Z-Score로 이상치 탐지
    const highPerformers = cluster.creatives.filter(c => 
      (c.totalScore - mean) / std > 1.5    // 평균보다 1.5σ 이상 높음
    );
    const lowPerformers = cluster.creatives.filter(c => 
      (c.totalScore - mean) / std < -1.5   // 평균보다 1.5σ 이상 낮음
    );
    const normalPerformers = cluster.creatives.filter(c => {
      const z = (c.totalScore - mean) / std;
      return z >= -1.5 && z <= 1.5;
    });
    
    // 3. 분리 조건: 이상치가 최소 크기 이상일 때만 분리
    if (highPerformers.length >= minClusterSize && normalPerformers.length >= minClusterSize) {
      result.push(
        { ...cluster, name: cluster.name + ' (고성과)', creatives: highPerformers },
        { ...cluster, name: cluster.name + ' (일반)', creatives: normalPerformers }
      );
      if (lowPerformers.length >= minClusterSize) {
        result.push({ ...cluster, name: cluster.name + ' (저성과)', creatives: lowPerformers });
      }
    } else {
      result.push(cluster);  // 분리하지 않음
    }
  });
  
  return result;
}
```

**시각적 설명**:
```
군집A: Character 소재 23개
Score 분포: 31, 35, 42, 55, 62, 65, 68, 71, 74, 75, 76, 78, 79, 80, 81, 82, 83, 84, 85, 88, 89, 92, 95

평균: 72.8점, 표준편차: 16.3점

Z-Score 기준:
  > +1.5σ (72.8 + 24.5 = 97.3): 해당 없음
  +1.5σ ~ -1.5σ (48.3 ~ 97.3): 대부분의 소재 (19개)
  < -1.5σ (72.8 - 24.5 = 48.3): Score 31, 35, 42점 소재 3개

→ 저성과 소재 3개가 최소 크기(3개) 이상 → 별도 군집 분리 여부 결정
→ 최소 크기가 5개라면 → 분리하지 않고 유지 (3 < 5)
```

---

### 1.5 Phase 3 상세: 인사이트 자동 생성

**(다음 섹션 3에서 상세 설명)**

---

### 1.6 Phase 4 상세: 품질 평가

#### 1.6.1 4개 품질 지표

```javascript
function phaseQualityAssessment(clusters, allCreatives) {
  
  // ① Silhouette Score: 군집이 얼마나 잘 분리되어 있는가
  // 각 소재에 대해: a = 같은 군집 내 평균 거리, b = 가장 가까운 다른 군집까지 평균 거리
  // silhouette(i) = (b - a) / max(a, b)
  // 범위: -1 (최악) ~ +1 (최고), 0.5 이상이면 양호
  const silhouetteScore = calculateSilhouette(clusters);
  
  // ② 성과 분리도: 군집 간 평균 Score 차이
  // 군집별 평균 Score의 표준편차가 클수록 잘 분리됨
  const avgScores = clusters.map(c => c.avgScore);
  const scoreMean = avgScores.reduce((a, b) => a + b, 0) / avgScores.length;
  const scoreStd  = Math.sqrt(avgScores.map(s => (s - scoreMean)**2).reduce((a,b) => a+b, 0) / avgScores.length);
  const performanceSeparation = Math.min(100, scoreStd * 3);  // 0~100 정규화
  
  // ③ 크기 균형도: 군집 크기가 골고루 분포되어 있는가
  // 지니 계수(Gini Coefficient) 활용 - 0(완전균등) ~ 1(완전불균등)
  const sizes = clusters.map(c => c.creatives.length);
  const gini  = calculateGini(sizes);
  const sizeBalance = Math.round((1 - gini) * 100);  // 0~100 (100이 완전균등)
  
  // ④ 태그 일관성: 군집 내 소재들이 같은 태그를 공유하는가
  // 각 군집에서 과반수(>50%) 소재가 공유하는 태그 비율
  const tagConsistencyScores = clusters.map(cluster => {
    const tagFreq = {};
    cluster.creatives.forEach(c => c.tags.forEach(t => { tagFreq[t] = (tagFreq[t]||0) + 1; }));
    const sharedTags = Object.values(tagFreq).filter(cnt => cnt > cluster.creatives.length * 0.5).length;
    const totalTags  = Object.keys(tagFreq).length;
    return totalTags > 0 ? sharedTags / totalTags : 0;
  });
  const tagConsistency = Math.round(
    tagConsistencyScores.reduce((a, b) => a + b, 0) / tagConsistencyScores.length * 100
  );
  
  // 종합 점수 및 등급
  const overall = Math.round(
    silhouetteScore * 25 + performanceSeparation * 0.25 + sizeBalance * 0.25 + tagConsistency * 0.25
  );
  
  const grade = overall >= 85 ? 'S' : overall >= 70 ? 'A' : overall >= 55 ? 'B' : 'C';
  
  return { overall, grade, silhouetteScore, performanceSeparation, sizeBalance, tagConsistency };
}
```

**품질 등급 기준**:
```
S등급 (85점 이상): 군집이 매우 명확하게 구분됨. 결과 신뢰도 최고.
A등급 (70~84점): 군집 구분이 양호함. 실무 활용에 적합.
B등급 (55~69점): 일부 군집이 불명확. 파라미터 조정 권장.
C등급 (55점 미만): 군집 구분이 불명확. 데이터 재검토 필요.
```

---

## 2. 사용자 정의 컬럼 기반 군집화

### 2.1 현재 CSV 컬럼 구조 분석

실제 CSV(PHPH.csv)의 컬럼 구성:

```
[퍼포먼스 지표 컬럼 - 군집화에 사용 안함]
캠페인, 광고그룹, 일, 전환, 통화 코드, 비용, 노출수, 클릭수, Revenue

[소재 메타 컬럼 - 군집화에 사용 안함]
앱 확장 소재, 앱 확장 소재 유형, 유형, 사이즈, 투입일, 시기, 언어, 파일명, 소재명, 링크

[태그 컬럼 - 군집화 후보]
USP                    → "Character", "Hooking", "Mob" 등 광고 USP
Concept                → "Adventure", "Combat", "Fantasy" 등 컨셉
hooking_strategy       → "Emotion", "Challenge", "Tutorial" 등 후킹 전략
audio_elements_bgm     → true/false (BGM 포함 여부)
audio_elements_cv      → true/false (성우 포함 여부)
text_analysis_core_usp → 카피에서 추출된 핵심 USP
title_specific_system  → 게임 시스템 (PVP, Gacha, Guild 등)
title_specific_mechanic → 게임 메카닉 (Turn-based, Real-time 등)
title_specific_faction_race → 진영/종족 (Human, Elf, Dragon 등)
title_specific_identified_character → 등장 캐릭터명
title_specific_theme   → 테마 (Dark Fantasy, Cute, 등)
gameplay               → 게임플레이 방식
visual_technique       → 영상 기법 (Timelapse, Split-screen 등)
environment            → 배경 환경 (Forest, Castle, 등)
emotion                → 감정 코드 (Exciting, Calm, 등)
character_object       → 주요 오브젝트 (Hero, Monster, 등)
art_style              → 아트 스타일 (2D, 3D, Pixel 등)
marketer_insight       → 마케터 인사이트 (자유 텍스트 → [MI] 태그 변환)
```

### 2.2 사용자 정의 컬럼 선택 시스템

군집화에 어떤 컬럼을 사용할지 마케터가 직접 선택하고, 중요도(가중치)를 설정하는 시스템입니다.

#### 2.2.1 UI 설계: 컬럼 선택 패널

```
┌─────────────────────────────────────────────────────────────────┐
│  🎛️ 군집화 컬럼 설정                                            │
│  ─────────────────────────────────────────────────────────────── │
│  ℹ️ 군집화에 사용할 컬럼과 중요도(가중치)를 설정하세요.         │
│     가중치가 높을수록 해당 컬럼의 태그가 군집화에 더 큰 영향을  │
│     미칩니다.                                                    │
│  ─────────────────────────────────────────────────────────────── │
│                                                                   │
│  [전략/컨셉 분류]                                                │
│  ☑ USP               가중치 [████████░░] 80%  [고중요도]        │
│  ☑ Concept           가중치 [███████░░░] 70%  [고중요도]        │
│  ☑ hooking_strategy  가중치 [█████░░░░░] 50%  [중중요도]        │
│                                                                   │
│  [게임 시스템/메카닉]                                            │
│  ☑ title_specific_mechanic  가중치 [████░░░░░░] 40%  [중중요도] │
│  ☑ title_specific_system    가중치 [████░░░░░░] 40%  [중중요도] │
│  ☐ title_specific_faction_race  가중치 [██░░░░░░░░] 20%         │
│                                                                   │
│  [시각/스타일]                                                   │
│  ☑ visual_technique  가중치 [████░░░░░░] 40%  [중중요도]        │
│  ☑ art_style         가중치 [███░░░░░░░] 30%  [저중요도]        │
│  ☐ environment       가중치 [██░░░░░░░░] 20%                     │
│                                                                   │
│  [감성/캐릭터]                                                   │
│  ☑ emotion           가중치 [████░░░░░░] 40%  [중중요도]        │
│  ☑ character_object  가중치 [████░░░░░░] 40%  [중중요도]        │
│  ☐ title_specific_identified_character  가중치 [██░░] 20%        │
│                                                                   │
│  [오디오/텍스트]                                                 │
│  ☐ audio_elements_bgm  가중치 [██░░░░░░░░] 20%                  │
│  ☐ audio_elements_cv   가중치 [██░░░░░░░░] 20%                  │
│  ☑ text_analysis_core_usp  가중치 [███░░░░░░░] 30%  [저중요도]  │
│                                                                   │
│  [마케터 인사이트]                                               │
│  ☑ marketer_insight  가중치 [██████████] 100% [최고중요도] 🔒   │
│  (마케터 인사이트는 항상 포함, 가중치 최고 고정)                │
│                                                                   │
│  ─────────────────────────────────────────────────────────────── │
│  📊 현재 설정: 선택된 컬럼 9개 / 전체 16개                       │
│  예상 태그 수: ~180개 태그 (군집화에 사용될 차별 태그)           │
│  ─────────────────────────────────────────────────────────────── │
│  [🔄 기본값으로 초기화]  [💾 설정 저장]  [▶ 이 설정으로 군집화] │
└─────────────────────────────────────────────────────────────────┘
```

#### 2.2.2 컬럼 가중치 적용 로직

```javascript
/**
 * 사용자 정의 컬럼 + 가중치 기반 태그 추출
 * 
 * @param {Object} creative - 소재 데이터 (원본 CSV 행)
 * @param {Array}  columnConfig - 사용자가 선택한 컬럼 설정
 *   예: [
 *     { column: 'USP', weight: 0.8, enabled: true },
 *     { column: 'Concept', weight: 0.7, enabled: true },
 *     { column: 'hooking_strategy', weight: 0.5, enabled: true },
 *     { column: 'emotion', weight: 0.4, enabled: true },
 *     { column: 'marketer_insight', weight: 1.0, enabled: true, locked: true }
 *   ]
 */
function extractTagsWithWeights(creative, columnConfig) {
  const weightedTags = [];
  
  columnConfig.filter(col => col.enabled).forEach(({ column, weight }) => {
    const value = creative[column];
    if (!value || value.trim() === '') return;
    
    // 1. [MI] 태그 처리 (marketer_insight 컬럼)
    if (column === 'marketer_insight') {
      const miTags = extractMIKeywords(value);  // 키워드 추출 후 [MI] 접두사
      miTags.forEach(tag => weightedTags.push({ tag, weight: 1.5 }));  // 항상 1.5배
      return;
    }
    
    // 2. Boolean 컬럼 처리 (audio_elements_bgm 등)
    if (value === 'true' || value === 'TRUE' || value === '1') {
      weightedTags.push({ tag: `${column}:ON`, weight });
      return;
    }
    if (value === 'false' || value === 'FALSE' || value === '0') {
      return;  // false는 태그로 추가하지 않음 (의미 없음)
    }
    
    // 3. 다중값 컬럼 처리 (쉼표 또는 슬래시로 구분)
    const values = value.split(/[,\/]/).map(v => v.trim()).filter(v => v);
    values.forEach(v => {
      if (v) weightedTags.push({ tag: v, weight });
    });
  });
  
  return weightedTags;
}

/**
 * 가중치 적용 동시출현 행렬 계산
 */
function calculateWeightedCoMatrix(creatives, columnConfig, discriminativeTags) {
  const coMatrix = {};
  const coKey = (a, b) => [a, b].sort().join('|||');
  
  creatives.forEach(creative => {
    const weightedTags = extractTagsWithWeights(creative, columnConfig);
    
    // 차별 태그만 필터링
    const filteredTags = weightedTags.filter(wt => discriminativeTags.includes(wt.tag));
    
    for (let i = 0; i < filteredTags.length; i++) {
      for (let j = i + 1; j < filteredTags.length; j++) {
        const k = coKey(filteredTags[i].tag, filteredTags[j].tag);
        
        // ★ 가중치: 두 태그의 컬럼 가중치의 기하평균
        const combinedWeight = Math.sqrt(filteredTags[i].weight * filteredTags[j].weight);
        
        coMatrix[k] = (coMatrix[k] || 0) + combinedWeight;
      }
    }
  });
  
  return coMatrix;
}
```

#### 2.2.3 컬럼별 군집화 기여도 분석

군집화 후, 어느 컬럼이 실제로 군집 형성에 얼마나 기여했는지 보여줍니다.

```
📊 컬럼별 군집화 기여도 분석 결과:

컬럼              | 기여도    | 주요 역할
──────────────────┼──────────┼──────────────────────────────────────
USP              | ████████  | 군집A(Character) vs 군집B(Mob) 구분
Concept          | ███████   | 군집C(Adventure) vs 군집D(Combat) 구분
emotion          | █████     | 고성과/저성과 군집 내 세분화
hooking_strategy  | ████      | 군집 간 크로스 패턴 탐지
marketer_insight  | ████████ [MI] | 군집 명명 및 인사이트 핵심 근거
visual_technique  | ██        | 보조적 군집 구분
art_style        | █         | 영향 미미 (제거 검토)
audio_elements_bgm| ░░        | 영향 없음 (비활성화 권장)
```

### 2.3 3가지 군집화 모드

#### Mode 1: 태그 우선 (기본)
```
군집화 기준: 선택된 태그 컬럼 70% + 성과(Score) 30%
적합한 경우: 소재 특성(크리에이티브 전략)을 기준으로 그룹화하고 싶을 때
결과: "Character 군집", "Mob 군집", "Adventure 군집"
```

#### Mode 2: 성과 우선
```
군집화 기준: 선택된 태그 컬럼 30% + 성과(Score) 70%
적합한 경우: 성과 수준을 기준으로 그룹화하고 싶을 때
결과: "S급 고성과 군집(78점↑)", "A급 안정 군집(60~77점)", "B급 개선 필요 군집(60점↓)"
```

#### Mode 3: 단일 컬럼 집중
```
군집화 기준: 특정 1~2개 컬럼만 100% 가중치
적합한 경우: "USP 기준으로만 나눠봐", "emotion 기준으로만 나눠봐" 등
결과: 해당 컬럼의 값별로 명확하게 군집 형성
```

---

## 3. 인사이트 자동화 방법론

### 3.1 전체 인사이트 자동화 구조

```
                   ┌─────────────────────────────────────┐
                   │  인사이트 자동화 엔진                │
                   └─────────────────────────────────────┘
                                    │
           ┌────────────────────────┼──────────────────────┐
           ↓                        ↓                      ↓
  ┌─────────────────┐   ┌─────────────────────┐   ┌─────────────────┐
  │ A. 통계 기반    │   │ B. 패턴 매칭        │   │ C. 차수 비교    │
  │ 인사이트        │   │ 인사이트             │   │ 인사이트        │
  │                 │   │                     │   │                 │
  │ - 군집 성과 비교│   │ - 승리 공식 추출    │   │ - 트렌드 분석   │
  │ - 태그 영향도   │   │ - 중단 패턴 탐지    │   │ - 군집 변화     │
  │ - 분포 분석     │   │ - 최적 조합 제안    │   │ - 신규/소멸     │
  └─────────────────┘   └─────────────────────┘   └─────────────────┘
           │                        │                      │
           └────────────────────────┼──────────────────────┘
                                    ↓
                   ┌─────────────────────────────────────┐
                   │  자연어 인사이트 텍스트 생성         │
                   │  (템플릿 + 데이터 바인딩)            │
                   └─────────────────────────────────────┘
```

### 3.2 A. 통계 기반 인사이트

#### 3.2.1 태그 영향도 분석 (Tag Impact Analysis)

"특정 태그가 있는 소재의 평균 성과" vs "없는 소재의 평균 성과" 비교

```javascript
function analyzeTagImpact(allCreatives, targetTag) {
  const withTag    = allCreatives.filter(c => c.tags.includes(targetTag));
  const withoutTag = allCreatives.filter(c => !c.tags.includes(targetTag));
  
  if (withTag.length < 3) return null;  // 샘플 부족
  
  const avgScoreWith    = withTag.reduce((a, c) => a + c.totalScore, 0) / withTag.length;
  const avgScoreWithout = withoutTag.reduce((a, c) => a + c.totalScore, 0) / withoutTag.length;
  
  const impact = avgScoreWith - avgScoreWithout;  // 양수 = 긍정 영향
  
  // 통계적 유의성 (t-test 근사)
  const isSignificant = Math.abs(impact) > 5 && withTag.length >= 5;
  
  return {
    tag: targetTag,
    impact,                // 점수 기여도
    avgWithTag: avgScoreWith,
    avgWithoutTag: avgScoreWithout,
    sampleSize: withTag.length,
    isSignificant,
    direction: impact > 0 ? '긍정' : '부정',
    confidence: isSignificant ? '높음' : '낮음'
  };
}

// 전체 태그 영향도 순위
function rankTagsByImpact(allCreatives, allTags) {
  return allTags
    .map(tag => analyzeTagImpact(allCreatives, tag))
    .filter(r => r !== null && r.isSignificant)
    .sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact));
}
```

**결과 예시**:
```
태그 영향도 분석 결과:

긍정 영향 태그 (상위 5개):
1. [MI] 감성 강조     → +12.5점  (해당 소재: 23개, 신뢰도: 높음)
2. Character          → +10.3점  (해당 소재: 45개, 신뢰도: 높음)
3. Hooking            → + 8.7점  (해당 소재: 38개, 신뢰도: 높음)
4. FastPace           → + 6.2점  (해당 소재: 22개, 신뢰도: 중간)
5. [MI] 긴장감 고조   → + 5.8점  (해당 소재: 12개, 신뢰도: 중간)

부정 영향 태그 (하위 5개):
1. StaticImage        → -9.8점   (해당 소재: 31개, 신뢰도: 높음)
2. TextOnly           → -7.5점   (해당 소재: 18개, 신뢰도: 높음)
3. LongDuration       → -5.2점   (해당 소재: 14개, 신뢰도: 중간)
4. GenericCopy        → -4.8점   (해당 소재: 25개, 신뢰도: 중간)
5. NoCharacter        → -3.9점   (해당 소재: 9개, 신뢰도: 낮음)
```

#### 3.2.2 최적 태그 조합 분석

"태그 A + B + C" 조합의 성과가 단독 태그보다 얼마나 좋은가?

```javascript
function analyzeTagCombinations(allCreatives, topTags, maxComboSize = 3) {
  const combinations = [];
  
  // 2개 조합, 3개 조합 분석
  for (let size = 2; size <= maxComboSize; size++) {
    const combos = getCombinations(topTags.slice(0, 10), size);  // 상위 10개 태그에서
    
    combos.forEach(combo => {
      const withCombo = allCreatives.filter(c => 
        combo.every(tag => c.tags.includes(tag))
      );
      
      if (withCombo.length < 3) return;  // 샘플 부족
      
      const avgScore = withCombo.reduce((a, c) => a + c.totalScore, 0) / withCombo.length;
      
      combinations.push({
        tags: combo,
        avgScore,
        count: withCombo.length,
        // 상승효과: 조합 성과 - 개별 태그 성과의 평균
        synergyEffect: avgScore - combo.map(tag => {
          const impact = analyzeTagImpact(allCreatives, tag);
          return impact ? impact.avgWithTag : 50;
        }).reduce((a, b) => a + b, 0) / combo.length
      });
    });
  }
  
  return combinations.sort((a, b) => b.synergyEffect - a.synergyEffect).slice(0, 5);
}
```

**결과 예시**:
```
최적 태그 조합 TOP 5:

순위  조합                                    평균 Score  소재수  시너지 효과
─────────────────────────────────────────────────────────────────────────
1위   Character + Hooking + [MI]감성강조     85.3점      12개    +18.2점 ⭐ 추천
2위   Character + FastPace                   79.8점      18개    +12.5점 ⭐ 추천
3위   Mob + Combat + Strategy                74.2점      9개     +8.7점  👍 유망
4위   Hooking + emotion:Exciting             72.5점      14개    +6.3점  👍 유망
5위   Adventure + Fantasy + Story            68.9점      11개    +3.1점  ➡️ 관찰
```

### 3.3 B. 패턴 매칭 인사이트

#### 3.3.1 승리 공식 자동 추출 (Winning Formula)

```javascript
function extractWinningFormulas(clusters, allCreatives) {
  // 1. 상위 25% 군집 선별
  const sortedByScore = [...clusters].sort((a, b) => b.avgScore - a.avgScore);
  const topClusters   = sortedByScore.slice(0, Math.max(1, Math.ceil(sortedByScore.length * 0.25)));
  
  const formulas = topClusters.map(cluster => {
    // 2. TF-IDF로 해당 군집의 특징 태그 추출
    const clusterTagFreq = {};
    cluster.creatives.forEach(c => c.tags.forEach(t => {
      clusterTagFreq[t] = (clusterTagFreq[t] || 0) + 1;
    }));
    
    const globalTagFreq = {};
    allCreatives.forEach(c => c.tags.forEach(t => {
      globalTagFreq[t] = (globalTagFreq[t] || 0) + 1;
    }));
    
    // TF-IDF: 군집 내 빈도 높고, 전체 대비 군집 특유의 태그
    const tfidfTags = Object.entries(clusterTagFreq)
      .map(([tag, cnt]) => ({
        tag,
        tfidf: (cnt / cluster.creatives.length) /             // TF: 군집 내 빈도
               ((globalTagFreq[tag] || 1) / allCreatives.length), // IDF: 전체 희귀도
        coverage: cnt / cluster.creatives.length               // 군집 내 커버리지
      }))
      .filter(t => t.coverage >= 0.5)  // 군집 소재 50% 이상에 등장
      .sort((a, b) => b.tfidf - a.tfidf)
      .slice(0, 5);
    
    // 3. 성과 트렌드 분석
    const creativesSorted = [...cluster.creatives].sort((a, b) => a.date - b.date);
    const firstHalf  = creativesSorted.slice(0, Math.floor(creativesSorted.length / 2));
    const secondHalf = creativesSorted.slice(Math.floor(creativesSorted.length / 2));
    
    const firstHalfAvg  = firstHalf.reduce((s, c) => s + c.totalScore, 0) / firstHalf.length;
    const secondHalfAvg = secondHalf.reduce((s, c) => s + c.totalScore, 0) / secondHalf.length;
    const trend = secondHalfAvg - firstHalfAvg;
    
    // 4. 자동 추천 문구 생성
    const keyTags   = tfidfTags.slice(0, 3).map(t => t.tag.replace('[MI] ', ''));
    const trendText = trend > 5 ? '상승 추세' : trend < -5 ? '하락 추세' : '안정적';
    
    return {
      clusterName: cluster.name,
      avgScore:    cluster.avgScore,
      percentile:  Math.round((1 - sortedByScore.indexOf(cluster) / sortedByScore.length) * 100),
      keyTags:     tfidfTags,
      trend,
      trendText,
      
      // 자연어 추천 문구
      recommendation: generateWinFormText(cluster, tfidfTags, trend)
    };
  });
  
  return formulas;
}

// 자연어 텍스트 생성 (템플릿 기반)
function generateWinFormText(cluster, tags, trend) {
  const tagNames = tags.slice(0, 3).map(t => `"${t.tag.replace('[MI] ', '')}"`).join(' + ');
  const coverageText = Math.round(tags[0].coverage * 100);
  
  let trendAdvice = '';
  if (trend > 5)       trendAdvice = '성과가 상승 중이므로 예산 즉시 확대를 권장합니다.';
  else if (trend > 0)  trendAdvice = '안정적 성과를 보이고 있으므로 유지 및 점진적 확대를 권장합니다.';
  else if (trend > -5) trendAdvice = '성과가 다소 하락 중입니다. 동일 패턴의 변형 소재 테스트를 권장합니다.';
  else                 trendAdvice = '성과 하락세가 있습니다. 피로도 분석 후 리프레시 여부를 검토하세요.';
  
  return (
    `${cluster.name}의 핵심 패턴은 ${tagNames} 조합으로, ` +
    `군집 내 소재의 ${coverageText}%가 이 패턴을 공유합니다. ` +
    `평균 ${cluster.avgScore}점으로 전체 상위 ${100 - cluster.percentile}%에 해당합니다. ` +
    trendAdvice
  );
}
```

**출력 예시**:
```
🏆 승리 공식 #1: Character 군집 (평균 85.3점, 상위 12%)

핵심 태그 패턴:
  ① "Character"   TF-IDF: 4.2  커버리지: 96%
  ② "Hooking"     TF-IDF: 3.8  커버리지: 78%
  ③ [MI] 감성강조  TF-IDF: 3.1  커버리지: 65%

자동 생성 추천:
  "Character 군집의 핵심 패턴은 "Character" + "Hooking" + "감성강조" 조합으로,
   군집 내 소재의 96%가 이 패턴을 공유합니다.
   평균 85.3점으로 전체 상위 12%에 해당합니다.
   성과가 상승 중이므로 예산 즉시 확대를 권장합니다."
```

#### 3.3.2 중단 패턴 자동 탐지 (Stop Pattern)

```javascript
function detectStopPatterns(clusters, allCreatives) {
  // 1. 하위 25% 군집 + CPA 상승 소재 탐지
  const sortedByScore = [...clusters].sort((a, b) => a.avgScore - b.avgScore);
  const bottomClusters = sortedByScore.slice(0, Math.max(1, Math.ceil(sortedByScore.length * 0.25)));
  
  return bottomClusters.map(cluster => {
    // 2. 위험 신호 탐지
    const riskSignals = [];
    
    // CPA 상승 여부
    const avgCPA = cluster.creatives.reduce((s, c) => s + c.cpa, 0) / cluster.creatives.length;
    const globalAvgCPA = allCreatives.reduce((s, c) => s + c.cpa, 0) / allCreatives.length;
    if (avgCPA > globalAvgCPA * 1.3) {
      riskSignals.push({ type: 'CPA_HIGH', severity: 'high', 
                         message: `CPA가 평균 대비 ${Math.round((avgCPA/globalAvgCPA - 1)*100)}% 높음` });
    }
    
    // 전환 감소 여부
    const avgConv = cluster.creatives.reduce((s, c) => s + c.conversion, 0) / cluster.creatives.length;
    const globalAvgConv = allCreatives.reduce((s, c) => s + c.conversion, 0) / allCreatives.length;
    if (avgConv < globalAvgConv * 0.7) {
      riskSignals.push({ type: 'CONV_LOW', severity: 'high',
                         message: `전환수가 평균 대비 ${Math.round((1 - avgConv/globalAvgConv)*100)}% 낮음` });
    }
    
    // IPM 낮음 여부
    const avgIPM = cluster.creatives.reduce((s, c) => s + c.ipm, 0) / cluster.creatives.length;
    const globalAvgIPM = allCreatives.reduce((s, c) => s + c.ipm, 0) / allCreatives.length;
    if (avgIPM < globalAvgIPM * 0.8) {
      riskSignals.push({ type: 'IPM_LOW', severity: 'medium',
                         message: `IPM이 평균 대비 ${Math.round((1 - avgIPM/globalAvgIPM)*100)}% 낮음` });
    }
    
    // 3. 대체 제안 (상위 군집의 태그에서 힌트)
    const topCluster = [...clusters].sort((a, b) => b.avgScore - a.avgScore)[0];
    const suggestion = `${topCluster.topTags.slice(0, 2).join(' + ')} 패턴의 소재로 대체 검토`;
    
    return {
      clusterName: cluster.name,
      avgScore: cluster.avgScore,
      riskSignals,
      primaryRisk: riskSignals.sort((a, b) => 
        ['high','medium','low'].indexOf(a.severity) - ['high','medium','low'].indexOf(b.severity)
      )[0],
      recommendation: generateStopPatternText(cluster, riskSignals, suggestion)
    };
  });
}
```

**출력 예시**:
```
🛑 중단 패턴 #1: 정적 이미지 군집 (평균 38.2점, 하위 15%)

위험 신호:
  🔴 CPA HIGH: CPA가 평균 대비 78% 높음 (₩8,245 vs 전체 평균 ₩4,632)
  🔴 CONV LOW: 전환수가 평균 대비 54% 낮음 (2.3건 vs 전체 평균 5.1건)
  🟡 IPM LOW: IPM이 평균 대비 32% 낮음 (1.8‰ vs 전체 평균 2.7‰)

자동 생성 권장 사항:
  "정적 이미지 군집은 CPA가 평균 대비 78% 높고, 전환수가 54% 낮은
   심각한 저성과 패턴입니다. 즉시 예산 축소 및 Character + Hooking
   패턴의 소재로 대체를 권장합니다."
```

### 3.4 C. 차수 비교 인사이트 (Trend Analysis)

```javascript
function analyzeCrossRoundTrends(currentClusters, previousRoundData) {
  if (!previousRoundData) return [];
  
  const prevClusters = previousRoundData.clusters;
  const trends = [];
  
  currentClusters.forEach(currCluster => {
    // Jaccard 유사도로 이전 차수 군집과 매칭
    let bestMatch = null, bestSimilarity = 0;
    
    prevClusters.forEach(prevCluster => {
      const currTags = new Set(currCluster.topTags);
      const prevTags = new Set(prevCluster.topTags);
      const intersection = new Set([...currTags].filter(t => prevTags.has(t)));
      const union        = new Set([...currTags, ...prevTags]);
      const jaccard      = intersection.size / union.size;
      
      if (jaccard > bestSimilarity) {
        bestSimilarity = jaccard;
        bestMatch = prevCluster;
      }
    });
    
    if (bestMatch && bestSimilarity >= 0.4) {
      // 매칭 성공 → 성과 변화 분석
      const scoreDelta = currCluster.avgScore - bestMatch.avgScore;
      const cntDelta   = currCluster.creatives.length - bestMatch.creativeCount;
      
      let status, description;
      if (scoreDelta > 5)        { status = '성장'; description = `+${scoreDelta.toFixed(1)}점 상승`; }
      else if (scoreDelta > -5)  { status = '유지'; description = `${scoreDelta > 0 ? '+' : ''}${scoreDelta.toFixed(1)}점 (안정)`; }
      else if (scoreDelta > -15) { status = '하락'; description = `${scoreDelta.toFixed(1)}점 하락`; }
      else                       { status = '위험'; description = `${scoreDelta.toFixed(1)}점 급락! 피로도 의심`; }
      
      trends.push({
        clusterName: currCluster.name,
        prevClusterName: bestMatch.name,
        similarity: bestSimilarity,
        scoreDelta,
        cntDelta,
        status,
        description,
        isNew: false
      });
    } else {
      // 매칭 실패 → 신규 군집
      trends.push({
        clusterName: currCluster.name,
        prevClusterName: null,
        similarity: 0,
        scoreDelta: null,
        status: '신규',
        description: '이번 차수에 처음 등장한 군집',
        isNew: true
      });
    }
  });
  
  // 이전 차수에 있었지만 현재 없는 군집 → 소멸
  prevClusters.forEach(prevCluster => {
    const isMatched = trends.some(t => t.prevClusterName === prevCluster.name);
    if (!isMatched) {
      trends.push({
        clusterName: null,
        prevClusterName: prevCluster.name,
        status: '소멸',
        description: `이전 차수 존재 (평균 ${prevCluster.avgScore}점)했으나 이번 차수 미탐지`,
        isNew: false
      });
    }
  });
  
  return trends;
}
```

**출력 예시**:
```
📈 차수 비교 트렌드 (4월 1주 vs 4월 2주):

군집명              이전 차수   현재       변화      상태
──────────────────────────────────────────────────────────
Character 군집      78.2점     85.3점    +7.1점 ↑   🟢 성장
Mob 군집            72.1점     70.8점    -1.3점 →   🔵 유지
Adventure 군집      66.3점     62.1점    -4.2점 ↓   🟡 하락
(신규) Female 군집   -          71.5점    신규       🆕 NEW
(소멸) 정적이미지 군집 41.2점   -         소멸       💀 소멸

💡 자동 생성 요약:
"이번 차수 Character 군집이 +7.1점 성장하여 Top 성과를 기록했습니다.
 Female 테마 신규 군집이 등장하여 테스트 강화를 권장합니다.
 저성과 정적이미지 군집은 소멸되어 소재 교체 효과가 확인되었습니다."
```

### 3.5 자연어 인사이트 생성 시스템

모든 분석 결과를 마케터가 바로 읽고 이해할 수 있는 한국어 문장으로 자동 변환합니다.

```javascript
// 인사이트 템플릿 라이브러리
const INSIGHT_TEMPLATES = {
  
  // 군집 요약
  CLUSTER_SUMMARY: (data) => 
    `총 ${data.totalCreatives}개 소재가 ${data.clusterCount}개 군집으로 분류되었습니다. ` +
    `최고 성과 군집은 "${data.topCluster.name}"(평균 ${data.topCluster.avgScore}점)이며, ` +
    `${data.topCluster.creatives.length}개 소재로 구성되어 있습니다.`,
  
  // 태그 영향도 요약  
  TAG_IMPACT_SUMMARY: (data) =>
    `성과에 가장 긍정적인 태그는 "${data.topTag.tag}"으로, 해당 태그가 있는 소재는 ` +
    `없는 소재 대비 평균 ${data.topTag.impact.toFixed(1)}점 높은 성과를 보입니다.`,
  
  // 예산 배분 제안
  BUDGET_ALLOCATION: (data) =>
    `성과 기반 예산 배분 제안: ` +
    `${data.winClusters.map(c => `"${c.name}" ${Math.round(c.budgetShare*100)}%`).join(', ')}에 ` +
    `집중 투자하고, ` +
    `${data.stopClusters.map(c => `"${c.name}"`).join(', ')}은 예산 축소를 권장합니다.`,
  
  // 신규 소재 제작 가이드
  CREATIVE_GUIDE: (data) =>
    `다음 차수 신규 소재 제작 가이드: ` +
    `① ${data.topTags.slice(0, 2).map(t => t.tag).join(' + ')} 조합 우선 활용 ` +
    `② 평균 지속시간 ${data.avgDuration}초 내외 권장 ` +
    `③ ${data.dominantType} 소재 비중 확대 (현재 ${data.typeRatio}%)`,
  
  // 피로도 경고
  FATIGUE_WARNING: (cluster) =>
    `⚠️ "${cluster.name}" 군집 피로도 경고: ` +
    `최근 2주간 CPA ${cluster.cpaTrend > 0 ? '+' : ''}${cluster.cpaTrend.toFixed(0)}% 변화. ` +
    `즉각적인 소재 리프레시 또는 교체를 권장합니다.`,
    
  // 이전 차수 대비 총평
  ROUND_SUMMARY: (data) =>
    `이번 차수 총평: 전체 평균 Score ${data.avgScore}점` +
    `(이전 대비 ${data.avgScoreDelta > 0 ? '+' : ''}${data.avgScoreDelta.toFixed(1)}점). ` +
    `신규 군집 ${data.newClusters}개, 소멸 군집 ${data.extinctClusters}개. ` +
    `${data.overallAssessment}`,  // "전반적으로 개선됨" / "현상 유지" / "성과 저하"
};
```

### 3.6 전체 인사이트 출력 예시

```
╔══════════════════════════════════════════════════════════════════╗
║  📊 2026년 4월 2주차 소재 분석 - 자동 생성 인사이트 리포트        ║
╚══════════════════════════════════════════════════════════════════╝

【 종합 요약 】
  총 156개 소재가 8개 군집으로 분류되었습니다. 최고 성과 군집은
  "Character 군집"(평균 85.3점)이며 23개 소재로 구성됩니다.
  이번 차수 전체 평균 Score는 67.2점으로 이전 대비 +3.8점 개선되었습니다.

【 승리 공식 (즉시 확대) 】
  ✅ #1: "Character + Hooking + 감성강조" 조합 (23개 소재, 평균 85.3점)
         → 성과 상승 중. 예산 즉시 확대를 권장합니다.
         
  ✅ #2: "Mob + Combat" 조합 (18개 소재, 평균 72.3점)
         → 안정적 성과. 유사 소재 추가 제작을 권장합니다.

【 중단 패턴 (즉시 축소) 】
  🛑 #1: "정적이미지 + 텍스트 전용" 조합 (28개 소재, 평균 38.2점)
         → CPA 78% 높음, 전환 54% 낮음. 예산 즉시 축소 및 교체 필요.

【 차수 비교 트렌드 】
  🟢 성장: Character 군집 +7.1점
  🔵 유지: Mob 군집 -1.3점
  🆕 신규: Female 군집 (71.5점, 테스트 강화 권장)
  💀 소멸: 정적이미지 군집 (소재 교체 효과 확인)

【 태그 영향도 TOP 3 】
  1위: [MI]감성강조 → +12.5점 기여 (23개 소재)
  2위: Character    → +10.3점 기여 (45개 소재)
  3위: Hooking      → + 8.7점 기여 (38개 소재)

【 다음 차수 제작 가이드 】
  ① Character + Hooking 조합을 기본으로 새 소재 제작
  ② [MI]감성강조 키워드 반드시 마케터 인사이트에 기록
  ③ VID 소재 비중 60% 이상 유지 권장 (현재 58%)
  ④ 정적 이미지 소재 신규 제작 중단

【 군집 품질 평가 】
  종합 점수: 87.3점 (A등급)
  - Silhouette Score: 0.74 (양호)
  - 성과 분리도:      89점 (우수)
  - 크기 균형도:      82점 (양호)
  - 태그 일관성:      94점 (우수)
```

---

## 4. 요약: 핵심 차이점과 실무 적용 포인트

### 4.1 알고리즘 선택 가이드

| 상황 | 권장 모드 | 이유 |
|-----|----------|------|
| 크리에이티브 전략 수립 | 태그 우선 모드 | "어떤 패턴이 잘 되는가" 파악 |
| 예산 배분 결정 | 성과 우선 모드 | "얼마나 잘 되는가" 기준으로 분류 |
| 특정 요소 영향 분석 | 단일 컬럼 모드 | "USP별로만 나눠보기" |
| 정기 차수 보고서 | 하이브리드 (기본) | 전략 + 성과 통합 분석 |

### 4.2 컬럼 설정 권장 사항

**R팀 기본 설정 (권장)**:
```
필수: USP(80%), Concept(70%), marketer_insight(100%, 고정)
권장: hooking_strategy(50%), emotion(40%), character_object(40%)
선택: visual_technique(40%), art_style(30%), title_specific_mechanic(40%)
제외: audio_elements_*, title_specific_identified_character (영향 미미)
```

### 4.3 인사이트 자동화 한계와 마케터 역할

```
자동화 가능 영역 (80%)               마케터 필수 개입 영역 (20%)
──────────────────────────────────   ──────────────────────────────────
✅ 통계 계산                         ✋ 비즈니스 컨텍스트 해석
✅ 태그 영향도 순위                   ✋ 외부 요인 반영 (시즌, 경쟁사)
✅ 승리/중단 패턴 탐지               ✋ 예산 최종 의사결정
✅ 군집 성과 비교                     ✋ 크리에이티브 방향성 결정
✅ 트렌드 분석                       ✋ 새로운 가설 수립
✅ 텍스트 리포트 생성                 ✋ 소재 제작 지시서 작성
```

---

**문서 버전**: v1.0  
**작성일**: 2026-04-10  
**상태**: ✅ 완성
