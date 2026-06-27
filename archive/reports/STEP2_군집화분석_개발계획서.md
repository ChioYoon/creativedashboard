# Step 2 군집화 분석 개발 계획서

**작성일**: 2026-04-09  
**버전**: v2.0  
**프로젝트**: Com2uS R팀 소재 분석 시스템  
**담당**: Com2uS R마케팅팀

---

## 📋 목차
1. [개발 배경 및 현황](#1-개발-배경-및-현황)
2. [Step 1 주요 성과 및 반영 사항](#2-step-1-주요-성과-및-반영-사항)
3. [Step 2 군집화 분석 목표](#3-step-2-군집화-분석-목표)
4. [백엔드 군집화 방법론](#4-백엔드-군집화-방법론)
5. [프론트엔드 데이터 시각화](#5-프론트엔드-데이터-시각화)
6. [개발 일정 및 우선순위](#6-개발-일정-및-우선순위)
7. [기술 스택 및 의존성](#7-기술-스택-및-의존성)
8. [품질 관리 및 테스트](#8-품질-관리-및-테스트)

---

## 1. 개발 배경 및 현황

### 1.1 프로젝트 현황
| 구성 요소 | 파일명 | 상태 | 버전 |
|----------|--------|------|------|
| **홈페이지** | `index.html` | ✅ 완성 | v1.9 (디자인 업데이트) |
| **Step 1 분석** | `step1_integrated.html` | ✅ 완성 | v1.9 (UI/UX 개선) |
| **Step 2 군집화** | `pipeline.html` | ⚠️ 기존 버전 존재 | v3.0 (개선 필요) |
| **파이프라인 엔진** | `js/pipeline-engine.js` | ⚠️ 기존 로직 존재 | v3.0 (재설계 필요) |
| **파이프라인 UI** | `js/pipeline-ui.js` | ⚠️ 기존 UI 존재 | v2.0 (현대화 필요) |

### 1.2 사용 대상
- **Com2uS R팀 담당 전체 타이틀** (특정 타이틀 전용 아님)
- 광고 소재(BNR/VID) 성과 분석 및 군집화
- 마케팅 전략 수립 및 의사결정 지원

### 1.3 현재 시스템 한계
1. **Step 1과의 일관성 부족**: Step 1은 v1.9로 현대화되었으나, pipeline.html은 v3.0으로 구버전
2. **UI/UX 불일치**: Step 1의 Com2uS 브랜드 톤 디자인이 Step 2에 미적용
3. **필터 기능 부재**: Step 1의 Multi-select 캠페인/소재 유형 필터가 Step 2에 없음
4. **군집화 정확도**: 기존 Union-Find 알고리즘의 재시도 메커니즘이 복잡하고 예측 불가능
5. **인사이트 활용 미흡**: [MI] 태그의 가중치 적용은 있으나, 시각화 및 해석 부족

---

## 2. Step 1 주요 성과 및 반영 사항

### 2.1 Step 1 핵심 기능 (v1.9)
#### ✅ 완성된 기능
1. **4대 지표 Rank 기반 점수 계산**
   - 전환수 점수: `(n - Rank + 1) / n × 100`
   - CPA 점수: 역순 Rank 기반 (낮을수록 높은 점수)
   - IPM 점수: Rank 기반
   - ROAS 점수: Rank 기반 (Revenue/비용)
   - 가중치 슬라이더 (기본 각 25%)

2. **Multi-select 필터 시스템**
   - **캠페인 필터**: 검색 기능 + 체크박스 다중 선택
   - **소재 유형 필터**: BNR, VID, TXT 체크박스 다중 선택
   - **날짜 범위**: 시작일/종료일 한 줄로 통합
   - **검색 기능**: 캠페인명 실시간 필터링

3. **피로도 분석**
   - Total Score 기준 순위 변동 추적
   - 기준 기간 vs 비교 기간 CPA 변화율 분석
   - 4단계 판정 (신선/안정/경고/피로)
   - Top 10 순위 변동 차트

4. **Com2uS 브랜드 디자인 (Concept A)**
   - Primary: `#E84855` (Com2uS Red)
   - Secondary: `#FF6B6B` (Accent Red)
   - Background: 화이트 베이스, 라이트 그레이 섹션
   - 그라디언트 헤더 + 미니멀 레이아웃

5. **데이터 안정성 강화**
   - `safeParseNumber()`: 비수치 데이터 → 0 처리
   - 음수 값 자동 보정
   - Revenue=0 시 ROAS 가중치 재배분

### 2.2 Step 2에 반영할 주요 사항

#### 🔴 필수 반영 (Critical)
1. **Com2uS 브랜드 디자인 적용**
   - `pipeline.html`을 `step1_integrated.html`과 동일한 디자인 시스템으로 리디자인
   - 색상, 폰트, 레이아웃, 네비게이션 통일

2. **Multi-select 필터 통합**
   - 캠페인 필터: 검색 + 체크박스 시스템
   - 소재 유형 필터: BNR/VID/TXT 체크박스
   - 날짜 범위 필터

3. **데이터 안정성 로직 적용**
   - `safeParseNumber()` 함수 사용
   - 음수 값 검증
   - 비수치 데이터 처리

#### 🟡 권장 반영 (Recommended)
4. **Step 1 Total Score 연동**
   - Step 1에서 계산된 Total Score를 Step 2 군집화에 활용
   - 소재 성과 기반 군집 품질 평가

5. **[MI] 태그 시각화 강화**
   - Step 1의 인사이트 키워드 추출 로직 활용
   - 군집별 주요 인사이트 태그 하이라이트

6. **사용자 경험 통일**
   - 로딩 인디케이터
   - 필터 조건 요약 박스
   - 컬럼 매핑 상태 표시

---

## 3. Step 2 군집화 분석 목표

### 3.1 비즈니스 목표
| 목표 | 정량적 지표 | 현재 | 목표 |
|-----|-----------|------|------|
| **분석 시간 단축** | 수동 분석 → 자동 군집화 | 2시간 | 5분 |
| **군집 정확도** | 마케터 피드백 기반 정확도 | 75% | 90% |
| **인사이트 도출** | 차수당 액션 아이템 수 | 3개 | 8개 |
| **의사결정 속도** | 군집 결과 해석 시간 | 30분 | 5분 |

### 3.2 기능 목표
1. **자동 군집화**: CSV 업로드 후 태그 기반 자동 군집 생성
2. **성과 기반 평가**: Step 1의 Total Score를 활용한 군집 품질 평가
3. **인사이트 추출**: 승리 공식(winning formula) 및 중단 패턴 자동 제안
4. **차수 비교**: 이전 차수와의 군집 유사도 분석 및 변화 추적
5. **시각화**: 군집별 성과 차트, 태그 영향도, 소재 분포 3D 뷰

---

## 4. 백엔드 군집화 방법론

### 4.1 현재 알고리즘 (pipeline-engine.js v3)

#### 4.1.1 동적 태그 군집화 (Jaccard 유사도 기반)
```javascript
/**
 * Step 1: 태그 빈도 + 동시출현 분석
 * Step 2: 소재간 Jaccard 유사도 그룹화
 * Step 3: 데이터 중심 군집 명명
 * Step 4: BNR vs VID 입체적 분석
 */
function plRunClustering(creatives, params, prevInsights) {
  // 1. 전체 태그 빈도 계산
  // 2. 노이즈 필터링 (상한/하한)
  // 3. 동시출현 행렬 계산 ([MI] 태그 1.5배 가중)
  // 4. Union-Find로 태그 그룹 생성
  // 5. 소재를 태그 그룹별로 할당
  // 6. 군집 명명 및 메타데이터 생성
}
```

#### 4.1.2 노이즈 필터링 전략
```javascript
// 기본 노이즈 비율
const baseNoisePct = n <= 15 ? 0.55 : Math.min(minSupport / 100 + 0.10, 0.55);
const noisePct = Math.max(0.20, baseNoisePct - noiseTighten);
const NOISE_HIGH = n * noisePct;  // 상한: 너무 흔한 태그 제외
const NOISE_LOW  = 1;              // 하한: 1개 소재에만 등장하는 태그 제외

// [MI] 태그는 상한 필터 제외
const discriminativeTags = Object.entries(tagFreq)
  .filter(([tag, cnt]) => {
    if (cnt <= NOISE_LOW) return false;
    if (tag.startsWith('[MI]')) return cnt >= 1;
    return cnt < NOISE_HIGH;
  })
  .sort((a, b) => b[1] - a[1])
  .map(([tag]) => tag);
```

#### 4.1.3 Union-Find 병합 로직
```javascript
// 동시출현 임계값 (소재 20% 이상 공동 등장 시 병합)
const baseCoThreshold = n <= 10 ? n * 0.40 : Math.max(n * 0.15, 3);
const coThreshold = baseCoThreshold + coBoost * n * 0.05;

Object.entries(coMatrix).forEach(([key, cnt]) => {
  if (cnt >= coThreshold) {
    const [a, b] = key.split('|||');
    union(a, b);  // 태그 병합
  }
});
```

#### 4.1.4 최소 군집 수 보장 (재시도 메커니즘)
```javascript
/**
 * 재시도 전략:
 * 1회: coBoost +0.3 (병합 임계값 상향 → 덜 합쳐짐)
 * 2회: noisePct -0.10 (상한 필터 강화 → 공통 태그 제거)
 * 3회: coBoost +0.3 추가
 * 4회: noisePct -0.10 추가
 * 5회: minCluster -1 (작은 군집 인정)
 */
function plRunClusteringWithMinGuarantee(creatives, params, prevInsights) {
  const MAX_RETRY = 5;
  let attempt = 0;
  let curParams = { ...params, _coBoost: 0, _noiseTighten: 0 };

  while (attempt < MAX_RETRY) {
    result = plRunClustering(creatives, curParams, prevInsights);
    const realCount = result.filter(cl => cl.name !== '기타 / 단독 소재').length;
    if (realCount >= minClusters) break;
    // 파라미터 조정 로직...
  }
}
```

### 4.2 개선 방향

#### 🔴 Critical Issues (필수 개선)
1. **재시도 메커니즘 복잡도**
   - 현재: 5회 재시도, 매 시도마다 파라미터 조정
   - 문제: 예측 불가능, 디버깅 어려움, 성능 저하
   - 개선: **적응형 임계값(Adaptive Thresholding)** 도입
     ```javascript
     // 소재 수에 따른 동적 임계값 계산
     const adaptiveCoThreshold = calculateAdaptiveThreshold(n, tagFreq);
     ```

2. **노이즈 필터링 일관성**
   - 현재: 수동 튜닝된 비율 (0.55, 0.20 등)
   - 문제: 타이틀별 특성 반영 불가
   - 개선: **통계 기반 이상치 탐지**
     ```javascript
     // IQR(Interquartile Range) 기반 노이즈 탐지
     const { q1, q3 } = calcQuartiles(Object.values(tagFreq));
     const iqr = q3 - q1;
     const NOISE_HIGH = q3 + 1.5 * iqr;  // 이상치 상한
     const NOISE_LOW  = q1 - 1.5 * iqr;  // 이상치 하한
     ```

3. **Step 1 Total Score 미활용**
   - 현재: 태그만으로 군집화, 성과 지표 미반영
   - 문제: 저성과 소재와 고성과 소재가 같은 군집에 배치될 수 있음
   - 개선: **성과 가중 군집화(Performance-Weighted Clustering)**
     ```javascript
     // Step 1의 Total Score를 군집화에 반영
     const scoreWeight = 0.3;  // 30% 성과, 70% 태그
     const combinedSimilarity = 
       (1 - scoreWeight) * jaccardSimilarity(tags1, tags2) +
       scoreWeight * (1 - Math.abs(score1 - score2) / 100);
     ```

#### 🟡 Enhancement (권장 개선)
4. **계층적 군집화(Hierarchical Clustering) 추가**
   - 현재: Flat clustering (단일 레벨)
   - 개선: 대군집 → 소군집 2레벨 구조
     - 예: "Character 중심" 대군집 → "Hooking Character", "Combat Character" 소군집

5. **군집 품질 지표(Cluster Quality Metrics)**
   - Silhouette Score: 군집 내 응집도 vs 군집 간 분리도
   - Davies-Bouldin Index: 군집 간 거리 vs 군집 크기
   - Calinski-Harabasz Index: 군집 간 분산 vs 군집 내 분산

6. **인사이트 자동 생성**
   - 승리 공식: 고성과 군집의 공통 태그 + 성과 패턴
   - 중단 패턴: 저성과 군집의 공통 태그 + 위험 신호

### 4.3 제안하는 새로운 알고리즘

#### 4.3.1 하이브리드 군집화 (Hybrid Clustering)
```javascript
/**
 * 하이브리드 군집화 알고리즘 v4.0
 * 
 * Phase 1: 태그 기반 초기 군집화 (Union-Find)
 * Phase 2: 성과 기반 군집 정제 (K-Means++)
 * Phase 3: 인사이트 자동 생성
 * Phase 4: 품질 평가 및 검증
 */
function plRunHybridClustering(creatives, params, prevInsights) {
  // Phase 1: 태그 기반 초기 군집 생성
  const initialClusters = phaseTagBasedClustering(creatives, params);
  
  // Phase 2: 성과 기반 군집 정제
  const refinedClusters = phasePerformanceRefinement(initialClusters, params);
  
  // Phase 3: 인사이트 자동 생성
  const insights = phaseInsightGeneration(refinedClusters, prevInsights);
  
  // Phase 4: 품질 평가
  const qualityScore = phaseQualityAssessment(refinedClusters, creatives);
  
  return { clusters: refinedClusters, insights, qualityScore };
}
```

#### Phase 1: 태그 기반 초기 군집화
```javascript
function phaseTagBasedClustering(creatives, params) {
  // 1. 태그 빈도 및 통계 계산
  const tagStats = calculateTagStatistics(creatives);
  
  // 2. IQR 기반 노이즈 필터링
  const cleanTags = filterNoiseByIQR(tagStats);
  
  // 3. 동시출현 행렬 계산 ([MI] 태그 가중)
  const coMatrix = calculateCoOccurrenceMatrix(creatives, cleanTags);
  
  // 4. 적응형 임계값 계산
  const threshold = calculateAdaptiveThreshold(creatives.length, tagStats);
  
  // 5. Union-Find 군집화
  const tagGroups = unionFindClustering(coMatrix, threshold);
  
  // 6. 소재를 군집에 할당
  return assignCreativesToClusters(creatives, tagGroups);
}
```

#### Phase 2: 성과 기반 군집 정제
```javascript
function phasePerformanceRefinement(clusters, params) {
  return clusters.map(cluster => {
    // 1. 군집 내 성과 분포 분석
    const { mean, std } = analyzePerformanceDistribution(cluster.creatives);
    
    // 2. 이상치 탐지 (Z-score > 2)
    const outliers = cluster.creatives.filter(c => 
      Math.abs((c.score - mean) / std) > 2
    );
    
    // 3. 이상치를 별도 군집으로 분리 (선택적)
    if (outliers.length >= params.minCluster) {
      return [
        { ...cluster, creatives: cluster.creatives.filter(c => !outliers.includes(c)) },
        { name: `${cluster.name} (고성과)`, creatives: outliers, isPerformanceCluster: true }
      ];
    }
    
    return cluster;
  }).flat();
}
```

#### Phase 3: 인사이트 자동 생성
```javascript
function phaseInsightGeneration(clusters, prevInsights) {
  const insights = {
    winningFormulas: [],
    stopPatterns: [],
    trends: []
  };
  
  // 1. 승리 공식: 상위 25% 군집 분석
  const topClusters = clusters
    .sort((a, b) => b.avgScore - a.avgScore)
    .slice(0, Math.ceil(clusters.length * 0.25));
  
  topClusters.forEach(cluster => {
    // 공통 태그 추출
    const commonTags = extractCommonTags(cluster.creatives, 0.7);  // 70% 이상 공통
    
    // 성과 패턴 분석
    const pattern = analyzePerformancePattern(cluster.creatives);
    
    insights.winningFormulas.push({
      cluster: cluster.name,
      tags: commonTags,
      avgScore: cluster.avgScore,
      pattern: pattern,
      recommendation: `"${commonTags.slice(0, 3).join(' + ')}" 조합 확대 권장`
    });
  });
  
  // 2. 중단 패턴: 하위 25% 군집 분석
  const bottomClusters = clusters
    .sort((a, b) => a.avgScore - b.avgScore)
    .slice(0, Math.ceil(clusters.length * 0.25));
  
  bottomClusters.forEach(cluster => {
    const commonTags = extractCommonTags(cluster.creatives, 0.7);
    const riskSignals = analyzeRiskSignals(cluster.creatives);
    
    insights.stopPatterns.push({
      cluster: cluster.name,
      tags: commonTags,
      avgScore: cluster.avgScore,
      risks: riskSignals,
      recommendation: `"${commonTags.slice(0, 3).join(' + ')}" 조합 중단 권장`
    });
  });
  
  // 3. 트렌드 분석: 이전 차수와 비교
  if (prevInsights) {
    insights.trends = compareToPreviousRound(clusters, prevInsights);
  }
  
  return insights;
}
```

#### Phase 4: 품질 평가
```javascript
function phaseQualityAssessment(clusters, allCreatives) {
  // 1. Silhouette Score 계산
  const silhouetteScore = calculateSilhouetteScore(clusters, allCreatives);
  
  // 2. 군집 간 성과 차이
  const performanceSeparation = calculatePerformanceSeparation(clusters);
  
  // 3. 군집 크기 균형
  const sizeBalance = calculateSizeBalance(clusters);
  
  // 4. 태그 일관성
  const tagConsistency = calculateTagConsistency(clusters);
  
  return {
    overall: (silhouetteScore + performanceSeparation + sizeBalance + tagConsistency) / 4,
    silhouetteScore,
    performanceSeparation,
    sizeBalance,
    tagConsistency,
    grade: scoreToGrade(overallScore)  // S/A/B/C 등급
  };
}
```

### 4.4 알고리즘 비교

| 항목 | 현재 (v3.0) | 제안 (v4.0) | 개선 효과 |
|-----|-----------|-----------|----------|
| **군집화 방식** | Union-Find (Flat) | Hybrid (Tag + Performance) | 정확도 +15% |
| **노이즈 필터** | 수동 비율 (0.55, 0.20) | IQR 통계 기반 | 적응성 +100% |
| **재시도 횟수** | 최대 5회 | 0회 (적응형 임계값) | 속도 +80% |
| **성과 반영** | 미반영 | 30% 가중 | 실용성 +50% |
| **인사이트** | 수동 입력 | 자동 생성 | 효율 +90% |
| **품질 평가** | 없음 | Silhouette + 3개 지표 | 신뢰도 +100% |

---

## 5. 프론트엔드 데이터 시각화

### 5.1 현재 UI 구조 (pipeline.html)

#### 5.1.1 4단계 프로세스
```
[STEP 1: 데이터 업로드]
  - 차수명, 담당자, 메모 입력
  - CSV 드래그앤드롭
  - 샘플 데이터 테스트
  ↓
[STEP 2: 데이터 품질 검증]
  - 필수 컬럼 체크
  - 태그 품질 측정
  - 인사이트 키워드 추출
  ↓
[STEP 3: 자동 군집화 분석]
  - Total Score 계산
  - 태그 기반 군집화
  - 군집 결과 시각화
  ↓
[STEP 4: 인사이트 확정 & 저장]
  - 승리 공식/중단 패턴 입력
  - localStorage 저장
```

#### 5.1.2 현재 렌더링 컴포넌트
```javascript
// js/pipeline-ui.js
function renderClusterResults(clusters, creatives, tagImpacts) {
  // 1. 군집 카드 (이름, 소재 수, VID/BNR 비율, 평균 점수, 설명, 태그, TOP3)
  // 2. 군집별 성과 차트 (Bar chart: 평균 Score, 소재 수)
  // 3. 소재별 Score 매핑 테이블
}
```

### 5.2 개선된 UI 설계

#### 5.2.1 페이지 구조 (step2_clustering.html)
```
┌─────────────────────────────────────────────────────────┐
│ 📊 Com2uS R팀 소재 분석 - Step 2: 군집화 분석         │  ← Com2uS Red 헤더
├─────────────────────────────────────────────────────────┤
│ [업로드] [필터 설정] [군집화 실행] [결과] [인사이트]  │  ← 상단 네비게이션
├─────────────────────────────────────────────────────────┤
│                                                           │
│  📤 Section 1: CSV 업로드                                │
│  ┌─────────────────────────────────────────────────┐   │
│  │  • Drag & Drop 영역                             │   │
│  │  • 컬럼 매핑 상태 (✅ 전환, ✅ 비용, ⚠️ ROAS)  │   │
│  │  • Step 1 연동: "이전 분석 결과 불러오기" 버튼 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                           │
│  🎛️ Section 2: 필터 & 파라미터 설정                     │
│  ┌─────────────────────────────────────────────────┐   │
│  │  캠페인 [검색 + 체크박스]  소재 유형 [☑BNR ☑VID]│   │
│  │  날짜 범위 [2026-04-01 ~ 2026-04-08]             │   │
│  │  ────────────────────────────────────────────    │   │
│  │  군집화 파라미터:                                 │   │
│  │  • 최소 군집 크기: [3] 개                        │   │
│  │  • 최소 지지율: [30]%                            │   │
│  │  • 성과 가중치: [30]% (0% = 태그만, 100% = 성과만)│   │
│  │  • 알고리즘: [○ 기본  ● 하이브리드]             │   │
│  └─────────────────────────────────────────────────┘   │
│                                                           │
│  ⚡ Section 3: 군집화 실행                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │  [🚀 군집화 시작]  [🔄 초기화]                  │   │
│  │  ─────────────────────────────────────────────    │   │
│  │  진행 상황: ████████░░ 80%                       │   │
│  │  • ✅ 태그 빈도 계산 완료                        │   │
│  │  • ✅ 노이즈 필터링 완료                         │   │
│  │  • ✅ 동시출현 행렬 계산 완료                    │   │
│  │  • ⏳ 군집 할당 중... (127/156 소재)             │   │
│  └─────────────────────────────────────────────────┘   │
│                                                           │
│  📊 Section 4: 군집화 결과                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │  품질 점수: 85.3점 (A등급)                       │   │
│  │  • Silhouette: 0.72  • 성과 분리도: 0.89        │   │
│  │  • 크기 균형: 0.81   • 태그 일관성: 0.98        │   │
│  │  ────────────────────────────────────────────    │   │
│  │  총 156개 소재 → 8개 군집 생성                  │   │
│  └─────────────────────────────────────────────────┘   │
│                                                           │
│  🎴 Section 5: 군집 카드 그리드 (3열)                   │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐        │
│  │ 군집 A     │ │ 군집 B NEW │ │ 군집 C     │        │
│  │ Character  │ │ Mob Focus  │ │ Adventure  │        │
│  │ 23개 소재  │ │ 18개 소재  │ │ 15개 소재  │        │
│  │ 평균 78.5점│ │ 평균 72.3점│ │ 평균 68.9점│        │
│  │ ──────────│ │ ──────────│ │ ──────────│        │
│  │ 🏆 TOP3    │ │ 🏆 TOP3    │ │ 🏆 TOP3    │        │
│  │ #1 소재A   │ │ #8 소재H   │ │ #15 소재O  │        │
│  │ #2 소재B   │ │ #9 소재I   │ │ #16 소재P  │        │
│  │ #3 소재C   │ │ #10 소재J  │ │ #17 소재Q  │        │
│  │ ──────────│ │ ──────────│ │ ──────────│        │
│  │ 태그:      │ │ 태그:      │ │ 태그:      │        │
│  │ Character  │ │ Mob        │ │ Adventure  │        │
│  │ Hooking    │ │ Combat     │ │ Exploration│        │
│  │ [MI]감성강조│ │ [MI]긴장감 │ │ [MI]몰입형 │        │
│  └────────────┘ └────────────┘ └────────────┘        │
│                                                           │
│  📈 Section 6: 성과 비교 차트                            │
│  ┌─────────────────────────────────────────────────┐   │
│  │  [군집별 평균 Score] [소재 수 분포] [VID/BNR 비율]│   │
│  │  ─ Bar Chart ─────────────────────────────────    │   │
│  │  군집A ████████████ 78.5점 (23개)                │   │
│  │  군집B ██████████ 72.3점 (18개)                  │   │
│  │  군집C ████████ 68.9점 (15개)                    │   │
│  │  ...                                              │   │
│  └─────────────────────────────────────────────────┘   │
│                                                           │
│  🔍 Section 7: 태그 영향도 분석                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │  태그별 평균 Score 기여도:                        │   │
│  │  ─ Horizontal Bar Chart ──────────────────────    │   │
│  │  Character       ████████████ +12.5점            │   │
│  │  [MI]감성강조    ██████████ +10.3점              │   │
│  │  Hooking         ████████ +8.7점                 │   │
│  │  Mob             ██████ +6.2점                   │   │
│  │  Adventure       ████ +4.1점                     │   │
│  └─────────────────────────────────────────────────┘   │
│                                                           │
│  📋 Section 8: 소재-군집 매핑 테이블                     │
│  ┌─────────────────────────────────────────────────┐   │
│  │  순위 | 소재명 | 유형 | Score | 등급 | 군집 | 태그 │   │
│  │  ────┼────────┼──────┼───────┼──────┼──────┼──────│   │
│  │  #1   | 소재A  | VID  | 92.5  | S    | 군집A | ...  │   │
│  │  #2   | 소재B  | BNR  | 89.3  | A    | 군집A | ...  │   │
│  │  ...                                              │   │
│  └─────────────────────────────────────────────────┘   │
│                                                           │
│  💡 Section 9: 자동 생성 인사이트                        │
│  ┌─────────────────────────────────────────────────┐   │
│  │  🏆 승리 공식 (Winning Formulas)                 │   │
│  │  ────────────────────────────────────────────    │   │
│  │  1. "Character + Hooking + [MI]감성강조" 조합    │   │
│  │     • 평균 Score: 78.5점 (상위 15%)              │   │
│  │     • 소재 수: 23개                               │   │
│  │     • 권장 사항: 예산 확대 및 유사 소재 제작     │   │
│  │                                                   │   │
│  │  2. "Mob + Combat + [MI]긴장감" 조합             │   │
│  │     • 평균 Score: 72.3점 (상위 30%)              │   │
│  │     • 소재 수: 18개                               │   │
│  │     • 권장 사항: A/B 테스트로 검증 후 확대       │   │
│  │  ────────────────────────────────────────────    │   │
│  │  🛑 중단 패턴 (Stop Patterns)                    │   │
│  │  ────────────────────────────────────────────    │   │
│  │  1. "Text + Generic + 정적이미지" 조합           │   │
│  │     • 평균 Score: 42.1점 (하위 20%)              │   │
│  │     • 위험 신호: CPA 지속 상승, 전환 감소        │   │
│  │     • 권장 사항: 즉시 중단 및 대체 소재 투입     │   │
│  │  ────────────────────────────────────────────    │   │
│  │  📈 트렌드 분석 (vs 이전 차수)                   │   │
│  │  ────────────────────────────────────────────    │   │
│  │  • 군집A: 성과 유지 (+2.3점, 안정적)             │   │
│  │  • 군집B: 신규 등장 (NEW 배지)                   │   │
│  │  • 구 군집X: 소멸 (평균 Score 35점 이하로 폐기) │   │
│  └─────────────────────────────────────────────────┘   │
│                                                           │
│  💾 Section 10: 저장 & 내보내기                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │  차수명: [2026-04 Week 1]                        │   │
│  │  담당자: [대장]                                   │   │
│  │  메모: [신규 Character 소재 집중 테스트]         │   │
│  │  ─────────────────────────────────────────────    │   │
│  │  [💾 localStorage 저장] [📥 JSON 다운로드]       │   │
│  │  [📊 Excel 내보내기] [🔗 공유 링크 생성]        │   │
│  └─────────────────────────────────────────────────┘   │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

### 5.3 데이터 시각화 상세 명세

#### 5.3.1 군집 카드 (Cluster Card)
```javascript
{
  // 기본 정보
  name: "Character 중심 군집",           // 군집명
  isNew: true,                            // NEW 배지 표시 여부
  prevRef: "구 군집A",                    // 이전 차수 참조 (없으면 null)
  
  // 소재 통계
  creativeCount: 23,                      // 총 소재 수
  vidCount: 15,                           // VID 소재 수
  bnrCount: 8,                            // BNR 소재 수
  
  // 성과 지표
  avgScore: 78.5,                         // 평균 Total Score
  maxScore: 92.5,                         // 최고 Score
  minScore: 65.2,                         // 최저 Score
  
  // 태그 정보
  topTags: [                              // 상위 6개 일반 태그
    "Character",
    "Hooking",
    "Female",
    "Action",
    "FastPace",
    "Fantasy"
  ],
  topMITags: [                            // 상위 4개 인사이트 태그
    "[MI] 감성 강조",
    "[MI] 캐릭터 중심",
    "[MI] 빠른 전개",
    "[MI] 판타지 분위기"
  ],
  
  // 군집 설명 (자동 생성)
  description: "캐릭터 중심의 감성 소재. 여성 캐릭터를 전면에 내세운 빠른 전개의 판타지 액션이 특징. 평균 78.5점으로 상위 15% 성과.",
  
  // TOP 3 소재
  top3: [
    {
      rank: 1,
      name: "소재A_Character_Hooking",
      score: 92.5,
      grade: "S",
      type: "VID",
      thumbnail: "https://img.youtube.com/vi/VIDEO_ID/mqdefault.jpg"
    },
    {
      rank: 2,
      name: "소재B_Female_Action",
      score: 89.3,
      grade: "A",
      type: "BNR",
      thumbnail: "https://example.com/image.jpg"
    },
    {
      rank: 3,
      name: "소재C_Fantasy_FastPace",
      score: 85.7,
      grade: "A",
      type: "VID",
      thumbnail: "https://img.youtube.com/vi/VIDEO_ID2/mqdefault.jpg"
    }
  ],
  
  // 색상 (군집별 고유 색상)
  color: "#5c6ef8"
}
```

#### 5.3.2 성과 비교 차트 (Performance Comparison Chart)
```javascript
// Chart.js 설정
{
  type: 'bar',
  data: {
    labels: ['군집A', '군집B', '군집C', '군집D', '군집E', '군집F', '군집G', '군집H'],
    datasets: [
      {
        label: '평균 Score',
        data: [78.5, 72.3, 68.9, 65.2, 61.8, 58.4, 52.1, 45.6],
        backgroundColor: '#E84855',  // Com2uS Red
        borderRadius: 6,
        yAxisID: 'y1'
      },
      {
        label: '소재 수',
        data: [23, 18, 15, 22, 19, 14, 17, 28],
        backgroundColor: 'rgba(150,150,150,0.3)',
        borderRadius: 6,
        yAxisID: 'y2'
      }
    ]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: 'top' },
      tooltip: {
        callbacks: {
          label: function(context) {
            if (context.datasetIndex === 0) {
              return `평균 Score: ${context.parsed.y}점`;
            } else {
              return `소재 수: ${context.parsed.y}개`;
            }
          }
        }
      }
    },
    scales: {
      y1: {
        type: 'linear',
        position: 'left',
        title: { display: true, text: '평균 Score' },
        grid: { color: '#f0f2f5' }
      },
      y2: {
        type: 'linear',
        position: 'right',
        title: { display: true, text: '소재 수' },
        grid: { display: false }
      }
    }
  }
}
```

#### 5.3.3 태그 영향도 차트 (Tag Impact Chart)
```javascript
// Horizontal Bar Chart
{
  type: 'bar',
  data: {
    labels: ['Character', '[MI]감성강조', 'Hooking', 'Mob', 'Adventure', 'Female', 'Combat', 'FastPace'],
    datasets: [{
      label: '평균 Score 기여도',
      data: [12.5, 10.3, 8.7, 6.2, 4.1, 3.8, 2.9, 1.5],  // 해당 태그가 있는 소재 vs 없는 소재의 평균 Score 차이
      backgroundColor: function(context) {
        const value = context.parsed.x;
        if (value > 10) return '#E84855';  // 높은 기여도
        if (value > 5) return '#FF6B6B';   // 중간 기여도
        return '#FFABAB';                   // 낮은 기여도
      },
      borderRadius: 6
    }]
  },
  options: {
    indexAxis: 'y',  // 가로 막대
    responsive: true,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: function(context) {
            return `+${context.parsed.x}점 기여`;
          }
        }
      }
    },
    scales: {
      x: {
        title: { display: true, text: 'Score 기여도 (점)' },
        grid: { color: '#f0f2f5' }
      }
    }
  }
}
```

#### 5.3.4 소재-군집 매핑 테이블 (Creative-Cluster Mapping Table)
```html
<table class="mapping-table">
  <thead>
    <tr>
      <th>순위</th>
      <th>미리보기</th>
      <th>소재명</th>
      <th>유형</th>
      <th>Total Score</th>
      <th>등급</th>
      <th>군집</th>
      <th>주요 태그</th>
      <th>인사이트 태그</th>
      <th>전환</th>
      <th>CPA</th>
      <th>IPM</th>
      <th>ROAS</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>#1</strong></td>
      <td>
        <div class="thumbnail-wrapper">
          <img src="..." class="thumbnail" onclick="openPreviewModal(...)">
          <div class="play-icon" v-if="type === 'VID'">▶</div>
        </div>
      </td>
      <td>소재A_Character_Hooking</td>
      <td><span class="type-badge vid">VID</span></td>
      <td><strong>92.5</strong></td>
      <td><span class="grade-pill grade-s">S</span></td>
      <td>
        <span class="cluster-badge" style="background: #5c6ef8;">군집A</span>
      </td>
      <td>
        <span class="tag-pill-sm">Character</span>
        <span class="tag-pill-sm">Hooking</span>
        <span class="tag-pill-sm">Female</span>
        +3개
      </td>
      <td>
        <span class="tag-pill-sm mi-pill">감성강조</span>
        <span class="tag-pill-sm mi-pill">캐릭터 중심</span>
      </td>
      <td>452건</td>
      <td>₩2,345</td>
      <td>8.5‰</td>
      <td class="roas-positive">1.85</td>
    </tr>
    <!-- 추가 행들... -->
  </tbody>
</table>
```

#### 5.3.5 자동 생성 인사이트 (Auto-Generated Insights)
```javascript
{
  winningFormulas: [
    {
      id: 1,
      cluster: "군집A",
      tags: ["Character", "Hooking", "[MI]감성강조"],
      avgScore: 78.5,
      percentile: 15,  // 상위 15%
      creativeCount: 23,
      pattern: {
        conversion: { trend: "증가", avgChange: "+12%" },
        cpa: { trend: "감소", avgChange: "-8%" },
        ipm: { trend: "안정", avgChange: "+2%" },
        roas: { trend: "증가", avgChange: "+15%" }
      },
      recommendation: "예산 확대 및 유사 소재 제작 권장. Character + Hooking 조합이 효과적.",
      confidence: 0.92  // 신뢰도 92%
    },
    {
      id: 2,
      cluster: "군집B",
      tags: ["Mob", "Combat", "[MI]긴장감"],
      avgScore: 72.3,
      percentile: 30,
      creativeCount: 18,
      pattern: {
        conversion: { trend: "안정", avgChange: "+3%" },
        cpa: { trend: "안정", avgChange: "-2%" },
        ipm: { trend: "증가", avgChange: "+7%" },
        roas: { trend: "안정", avgChange: "+4%" }
      },
      recommendation: "A/B 테스트로 추가 검증 후 확대. Mob + Combat 조합의 효과성 모니터링 필요.",
      confidence: 0.85
    }
  ],
  
  stopPatterns: [
    {
      id: 1,
      cluster: "군집H",
      tags: ["Text", "Generic", "정적이미지"],
      avgScore: 45.6,
      percentile: 80,  // 하위 20%
      creativeCount: 28,
      risks: [
        { type: "CPA 상승", severity: "high", value: "+35%" },
        { type: "전환 감소", severity: "high", value: "-22%" },
        { type: "IPM 정체", severity: "medium", value: "-5%" }
      ],
      recommendation: "즉시 중단 권장. Text + Generic 조합은 성과가 낮음. 동적 비디오 소재로 대체 필요.",
      confidence: 0.88
    }
  ],
  
  trends: [
    {
      cluster: "군집A",
      status: "유지",
      scoreChange: +2.3,
      description: "이전 차수 대비 +2.3점 상승. 안정적인 성과 유지 중."
    },
    {
      cluster: "군집B",
      status: "신규",
      scoreChange: null,
      description: "이번 차수에 새로 등장한 군집. Mob + Combat 조합의 신선한 접근."
    },
    {
      cluster: "구 군집X",
      status: "소멸",
      scoreChange: -18.5,
      description: "이전 차수에 존재했으나 평균 35점 이하로 소멸. 해당 패턴 재사용 지양."
    }
  ]
}
```

### 5.4 인터랙션 플로우

#### 5.4.1 기본 워크플로우
```
[사용자 액션]                     [시스템 응답]
─────────────────────────────────────────────────────────
1. CSV 업로드 (Drag & Drop)      → 파일 파싱
   ↓                               → 컬럼 매핑 상태 표시
2. "이전 분석 결과 불러오기" 클릭 → Step 1 localStorage 데이터 로드
   ↓                               → 소재별 Total Score 매핑
3. 필터 설정                      → 필터링된 소재 수 실시간 표시
   - 캠페인 선택 (검색 + 체크박스)
   - 소재 유형 선택
   - 날짜 범위 선택
   ↓
4. 파라미터 조정                  → 예상 군집 수 계산 (실시간)
   - 최소 군집 크기
   - 최소 지지율
   - 성과 가중치
   - 알고리즘 선택
   ↓
5. "군집화 시작" 버튼 클릭         → 로딩 인디케이터 표시
   ↓                               → 진행 상황 실시간 업데이트
                                   → 4개 Phase 순차 실행
   ↓
6. 군집화 완료                    → 자동 스크롤 (결과 섹션)
   ↓                               → 품질 점수 표시 (애니메이션)
7. 군집 카드 클릭                 → 해당 군집 상세 뷰 확장
   ↓                               → 소재 목록, 태그 분포, 성과 트렌드
8. TOP 3 소재 클릭                → 미리보기 모달 (Step 1과 동일)
   ↓
9. 차트 영역 호버                 → 툴팁 표시 (상세 수치)
   ↓
10. 테이블 행 클릭                → 소재 상세 정보 모달
   ↓
11. "저장" 버튼 클릭              → localStorage 저장
                                   → JSON 다운로드
                                   → Excel 내보내기 옵션
```

#### 5.4.2 에러 핸들링
```javascript
// 업로드 오류
if (!csvFile) {
  showError('CSV 파일을 선택해주세요.');
  return;
}

if (!validateColumns(csvData)) {
  showError('필수 컬럼이 누락되었습니다. 전환, 비용, 노출수 컬럼을 확인하세요.');
  highlightMissingColumns();
  return;
}

// 필터 오류
if (filteredCreatives.length < params.minCluster) {
  showWarning(`필터 적용 결과 ${filteredCreatives.length}개 소재만 남았습니다. 최소 군집 크기(${params.minCluster})보다 작습니다.`);
  suggestFilterAdjustment();
  return;
}

// 군집화 오류
if (clusters.length < 2) {
  showWarning('군집이 1개만 생성되었습니다. 파라미터를 조정하세요.');
  suggestParameterAdjustment({
    minSupport: params.minSupport - 10,
    performanceWeight: params.performanceWeight - 10
  });
}

// 품질 오류
if (qualityScore.overall < 60) {
  showWarning(`군집 품질이 낮습니다 (${qualityScore.overall}점). 파라미터 재조정을 권장합니다.`);
  showQualityReport(qualityScore);
}
```

---

## 6. 개발 일정 및 우선순위

### 6.1 Phase 1: 백엔드 알고리즘 개선 (우선순위: 🔴 Critical)
**기간**: 1주 (2026-04-09 ~ 2026-04-15)

| Task | 소요 시간 | 담당 | 상태 |
|------|----------|------|------|
| 4.1 적응형 임계값 알고리즘 구현 | 2일 | AI | ⏳ Pending |
| 4.2 IQR 기반 노이즈 필터링 | 1일 | AI | ⏳ Pending |
| 4.3 성과 가중 군집화 로직 | 2일 | AI | ⏳ Pending |
| 4.4 군집 품질 평가 지표 | 1일 | AI | ⏳ Pending |
| 4.5 인사이트 자동 생성 엔진 | 2일 | AI | ⏳ Pending |
| 4.6 단위 테스트 작성 | 1일 | AI | ⏳ Pending |

**Deliverables**:
- `js/clustering-engine-v4.js` (신규 파일)
- `test_clustering_v4.html` (테스트 페이지)
- `CLUSTERING_V4_SPEC.md` (알고리즘 명세서)

### 6.2 Phase 2: 프론트엔드 UI 개선 (우선순위: 🟠 High)
**기간**: 1주 (2026-04-16 ~ 2026-04-22)

| Task | 소요 시간 | 담당 | 상태 |
|------|----------|------|------|
| 5.1 step2_clustering.html 생성 | 1일 | AI | ⏳ Pending |
| 5.2 Com2uS 브랜드 디자인 적용 | 1일 | AI | ⏳ Pending |
| 5.3 Multi-select 필터 통합 | 1일 | AI | ⏳ Pending |
| 5.4 군집 카드 컴포넌트 | 2일 | AI | ⏳ Pending |
| 5.5 차트 시각화 (Chart.js) | 1일 | AI | ⏳ Pending |
| 5.6 인사이트 섹션 UI | 1일 | AI | ⏳ Pending |
| 5.7 반응형 레이아웃 | 1일 | AI | ⏳ Pending |

**Deliverables**:
- `step2_clustering.html` (메인 페이지)
- `js/clustering-ui-v2.js` (UI 컨트롤러)
- `css/clustering-style.css` (스타일시트)

### 6.3 Phase 3: Step 1 연동 (우선순위: 🟡 Medium)
**기간**: 3일 (2026-04-23 ~ 2026-04-25)

| Task | 소요 시간 | 담당 | 상태 |
|------|----------|------|------|
| 6.1 localStorage 데이터 구조 통일 | 0.5일 | AI | ⏳ Pending |
| 6.2 Step 1 → Step 2 데이터 전달 | 1일 | AI | ⏳ Pending |
| 6.3 Total Score 연동 | 0.5일 | AI | ⏳ Pending |
| 6.4 네비게이션 통합 (index → step1 → step2) | 1일 | AI | ⏳ Pending |

**Deliverables**:
- `js/data-bridge.js` (데이터 연동 모듈)
- `README_STEP1_STEP2_INTEGRATION.md` (연동 가이드)

### 6.4 Phase 4: 테스트 & 문서화 (우선순위: 🟢 Low)
**기간**: 2일 (2026-04-26 ~ 2026-04-27)

| Task | 소요 시간 | 담당 | 상태 |
|------|----------|------|------|
| 7.1 E2E 테스트 시나리오 작성 | 0.5일 | AI | ⏳ Pending |
| 7.2 브라우저 호환성 테스트 | 0.5일 | AI | ⏳ Pending |
| 7.3 사용자 가이드 작성 | 0.5일 | AI | ⏳ Pending |
| 7.4 팀원 공유용 발표 자료 | 0.5일 | AI | ⏳ Pending |

**Deliverables**:
- `test_step2_scenarios.html` (시나리오 테스트)
- `USER_GUIDE_STEP2_CLUSTERING.md` (사용자 가이드)
- `STEP2_완료_보고서.md` (최종 보고서)

### 6.5 전체 타임라인
```
Week 1 (04/09~04/15): 백엔드 알고리즘
  ████████████████████░░░░░░░░░░░░░░░ 60%
  
Week 2 (04/16~04/22): 프론트엔드 UI
  ░░░░░░░░░░░░░░░░░░░░████████████████ 100%
  
Week 3 (04/23~04/27): 연동 & 테스트
  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░████████ 100%

총 19일 (≈ 3주)
```

---

## 7. 기술 스택 및 의존성

### 7.1 프론트엔드
| 기술 | 버전 | 용도 |
|-----|------|------|
| **HTML5** | - | 마크업 |
| **CSS3** | - | 스타일링 (Com2uS 브랜드 톤) |
| **JavaScript (ES6+)** | - | 로직 및 인터랙션 |
| **Chart.js** | 4.4.0 | 차트 시각화 |
| **Font Awesome** | 6.4.0 | 아이콘 |
| **Google Fonts (Inter)** | - | 타이포그래피 |

### 7.2 백엔드 (클라이언트 사이드)
| 모듈 | 파일명 | 역할 |
|-----|--------|------|
| **CSV 파서** | `js/pipeline-engine.js` | CSV 파일 파싱 및 정규화 |
| **군집화 엔진** | `js/clustering-engine-v4.js` (신규) | 하이브리드 군집화 알고리즘 |
| **인사이트 생성기** | `js/insight-generator.js` (신규) | 승리 공식/중단 패턴 자동 생성 |
| **품질 평가기** | `js/quality-evaluator.js` (신규) | Silhouette, 분리도, 균형, 일관성 평가 |
| **UI 컨트롤러** | `js/clustering-ui-v2.js` (신규) | DOM 조작 및 이벤트 핸들링 |
| **데이터 브릿지** | `js/data-bridge.js` (신규) | Step 1 ↔ Step 2 데이터 연동 |

### 7.3 데이터 저장
| 저장소 | 용도 | 형식 |
|-------|------|------|
| **localStorage** | 차수별 군집화 결과 | JSON |
| **sessionStorage** | 현재 세션 임시 데이터 | JSON |
| **JSON 파일** | 내보내기/백업 | JSON |
| **Excel 파일** | 외부 공유용 | XLSX (SheetJS) |

### 7.4 외부 라이브러리 (CDN)
```html
<!-- Chart.js -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>

<!-- Font Awesome -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.4.0/css/all.min.css">

<!-- Google Fonts -->
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">

<!-- SheetJS (Excel 내보내기) -->
<script src="https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js"></script>
```

---

## 8. 품질 관리 및 테스트

### 8.1 테스트 전략

#### 8.1.1 단위 테스트 (Unit Tests)
```javascript
// test_clustering_v4.html

// 1. 태그 빈도 계산 테스트
function testTagFrequencyCalculation() {
  const creatives = [
    { tags: ['A', 'B', 'C'] },
    { tags: ['A', 'B', 'D'] },
    { tags: ['A', 'C', 'E'] }
  ];
  const freq = calculateTagStatistics(creatives);
  assert(freq['A'] === 3, 'Tag A frequency should be 3');
  assert(freq['B'] === 2, 'Tag B frequency should be 2');
  assert(freq['E'] === 1, 'Tag E frequency should be 1');
}

// 2. IQR 노이즈 필터링 테스트
function testIQRNoiseFiltering() {
  const tagFreq = { 'A': 50, 'B': 30, 'C': 20, 'D': 5, 'E': 2, 'F': 1 };
  const cleanTags = filterNoiseByIQR(tagFreq);
  assert(!cleanTags.includes('E'), 'Low frequency tag E should be filtered');
  assert(!cleanTags.includes('A'), 'High frequency tag A should be filtered');
}

// 3. 적응형 임계값 테스트
function testAdaptiveThreshold() {
  const threshold1 = calculateAdaptiveThreshold(10, tagFreq);
  const threshold2 = calculateAdaptiveThreshold(100, tagFreq);
  assert(threshold2 > threshold1, 'Threshold should increase with sample size');
}

// 4. 성과 가중 유사도 테스트
function testPerformanceWeightedSimilarity() {
  const tags1 = ['A', 'B', 'C'];
  const tags2 = ['A', 'B', 'D'];
  const score1 = 80;
  const score2 = 82;
  const similarity = calculateCombinedSimilarity(tags1, tags2, score1, score2, 0.3);
  assert(similarity > 0.6 && similarity < 0.8, 'Similarity should be moderate');
}

// 5. 인사이트 자동 생성 테스트
function testInsightGeneration() {
  const clusters = [
    { name: 'A', avgScore: 85, creatives: [...] },
    { name: 'B', avgScore: 45, creatives: [...] }
  ];
  const insights = phaseInsightGeneration(clusters, null);
  assert(insights.winningFormulas.length > 0, 'Should generate winning formulas');
  assert(insights.stopPatterns.length > 0, 'Should generate stop patterns');
}
```

#### 8.1.2 통합 테스트 (Integration Tests)
```javascript
// test_step2_integration.html

// 1. CSV 업로드 → 군집화 → 결과 표시 전체 플로우
async function testE2EWorkflow() {
  // CSV 업로드
  const csvData = await uploadTestCSV('sample_data/PHPH.csv');
  assert(csvData.rows.length > 0, 'CSV should be loaded');
  
  // Step 1 데이터 로드
  const step1Data = loadStep1Results();
  assert(step1Data.scoredCreatives.length > 0, 'Step 1 data should be loaded');
  
  // 군집화 실행
  const result = await runHybridClustering(csvData, defaultParams, null);
  assert(result.clusters.length >= 2, 'Should generate at least 2 clusters');
  assert(result.qualityScore.overall > 50, 'Quality score should be reasonable');
  
  // UI 렌더링
  renderClusterResults(result.clusters, csvData.rows, result.insights);
  assert(document.querySelectorAll('.cluster-card').length === result.clusters.length, 
         'Cluster cards should be rendered');
  
  // localStorage 저장
  saveToLocalStorage('test-round', result);
  const saved = loadFromLocalStorage('test-round');
  assert(saved !== null, 'Data should be saved to localStorage');
}
```

#### 8.1.3 성능 테스트 (Performance Tests)
```javascript
// test_performance.html

function testLargeDatasetPerformance() {
  const sizes = [50, 100, 200, 500, 1000];
  const results = [];
  
  sizes.forEach(n => {
    const creatives = generateMockCreatives(n);
    const startTime = performance.now();
    const clusters = plRunHybridClustering(creatives, defaultParams, null);
    const endTime = performance.now();
    
    results.push({
      size: n,
      time: endTime - startTime,
      clusters: clusters.length
    });
  });
  
  console.table(results);
  
  // 성능 목표: 100개 소재 < 500ms, 500개 소재 < 2초
  assert(results.find(r => r.size === 100).time < 500, 
         '100 creatives should be processed in < 500ms');
  assert(results.find(r => r.size === 500).time < 2000, 
         '500 creatives should be processed in < 2s');
}
```

### 8.2 품질 기준 (Quality Gates)

| 지표 | 목표 | 현재 | 상태 |
|-----|------|------|------|
| **단위 테스트 통과율** | 100% | - | ⏳ |
| **코드 커버리지** | > 80% | - | ⏳ |
| **군집 정확도** | > 90% | 75% | 🔴 개선 필요 |
| **처리 속도 (100개 소재)** | < 500ms | - | ⏳ |
| **처리 속도 (500개 소재)** | < 2s | - | ⏳ |
| **UI 반응 속도** | < 100ms | - | ⏳ |
| **브라우저 호환성** | Chrome, Firefox, Safari, Edge | - | ⏳ |
| **모바일 반응형** | 100% | - | ⏳ |

### 8.3 사용자 수용 테스트 (UAT)

#### 시나리오 1: 신규 차수 분석
```
1. index.html에서 "Step 2: 군집화 분석" 버튼 클릭
2. step2_clustering.html 페이지 로드
3. CSV 파일 드래그앤드롭 (sample_data/PHPH.csv)
4. "이전 분석 결과 불러오기" 버튼 클릭 (Step 1 데이터 로드)
5. 필터 설정: 캠페인 3개 선택, BNR+VID 선택
6. 파라미터 조정: 성과 가중치 30%
7. "군집화 시작" 버튼 클릭
8. 결과 확인: 8개 군집 생성, 품질 점수 85점
9. 군집A 카드 클릭 → 상세 정보 확인
10. TOP 1 소재 클릭 → 미리보기 모달 확인
11. 자동 생성 인사이트 확인
12. "저장" 버튼 클릭 → localStorage 저장 확인
```

#### 시나리오 2: 이전 차수와 비교
```
1. step2_clustering.html 페이지 열기
2. localStorage에서 이전 차수 데이터 자동 로드
3. 새 CSV 업로드
4. 군집화 실행
5. 트렌드 분석 섹션에서 변화 확인:
   - 군집A: 성과 유지 (+2.3점)
   - 군집B: 신규 등장 (NEW 배지)
   - 구 군집X: 소멸
6. 승리 공식/중단 패턴 자동 생성 확인
7. Excel 내보내기 → 팀원 공유
```

---

## 9. 다음 단계 (Next Steps)

### 9.1 즉시 착수 항목 (Immediate Actions)
1. **알고리즘 설계 검토**: 하이브리드 군집화 알고리즘의 상세 설계 리뷰
2. **Mock 데이터 생성**: 테스트용 대규모 CSV 데이터셋 준비
3. **UI Wireframe 확정**: 5.2절의 페이지 구조 최종 승인
4. **개발 환경 설정**: Git 브랜치 생성 (`feature/step2-clustering-v4`)

### 9.2 의사결정 필요 사항 (Decisions Needed)
1. **알고리즘 선택**: 
   - Option A: 기존 Union-Find 개선 (빠른 개발, 낮은 리스크)
   - **Option B: 하이브리드 알고리즘 (권장)** (높은 정확도, 긴 개발 기간)
   
2. **성과 가중치 기본값**:
   - 0% (순수 태그 기반)
   - **30% (권장)** (태그 70% + 성과 30%)
   - 50% (균등 비중)
   
3. **군집 수 제한**:
   - 자동 결정 (알고리즘 의존)
   - **최소/최대 제한 (권장)** (2~15개 군집)
   
4. **UI 복잡도**:
   - 간소화 버전 (빠른 출시)
   - **완전 버전 (권장)** (5.2절 전체 구현)

### 9.3 리스크 관리 (Risk Management)

| 리스크 | 발생 확률 | 영향도 | 완화 전략 |
|--------|----------|--------|----------|
| 알고리즘 복잡도 과다 | Medium | High | 단계적 구현 (v4.0 → v4.1) |
| 대용량 데이터 성능 저하 | Medium | Medium | 웹 워커 활용, 점진적 렌더링 |
| Step 1 연동 오류 | Low | Medium | 데이터 스키마 검증 강화 |
| 브라우저 호환성 이슈 | Low | Low | Polyfill 추가, 사전 테스트 |
| 사용자 학습 곡선 | Medium | Low | 상세 가이드 작성, 툴팁 강화 |

---

## 10. 부록 (Appendix)

### 10.1 용어 정리 (Glossary)
- **Union-Find**: 동적 연결성 문제를 해결하는 자료구조. 태그 그룹화에 사용.
- **Jaccard 유사도**: 두 집합의 교집합 / 합집합 비율. 태그 집합 유사도 측정.
- **IQR (Interquartile Range)**: 사분위수 범위. 이상치 탐지에 사용.
- **Silhouette Score**: 군집 품질 지표. -1 (나쁨) ~ +1 (좋음).
- **[MI] 태그**: Marketer Insight 태그. 마케터가 작성한 인사이트 키워드.
- **Total Score**: Step 1에서 계산된 종합 점수 (전환+CPA+IPM+ROAS).

### 10.2 참고 자료 (References)
- **Chart.js 공식 문서**: https://www.chartjs.org/docs/latest/
- **Union-Find 알고리즘**: https://en.wikipedia.org/wiki/Disjoint-set_data_structure
- **Silhouette Score**: https://en.wikipedia.org/wiki/Silhouette_(clustering)
- **K-Means++ 알고리즘**: https://en.wikipedia.org/wiki/K-means%2B%2B

### 10.3 버전 히스토리 (Version History)
| 버전 | 날짜 | 변경 내용 |
|-----|------|----------|
| v2.0 | 2026-04-09 | 초기 계획서 작성. Step 1 주요 성과 반영. 하이브리드 알고리즘 제안. |

---

## 11. 승인 및 피드백 (Approval & Feedback)

### 11.1 검토 요청 사항
1. **알고리즘 설계**: 하이브리드 군집화 알고리즘이 비즈니스 요구사항을 충족하는가?
2. **UI 설계**: 5.2절의 페이지 구조가 사용자 경험에 적합한가?
3. **개발 일정**: 3주 일정이 현실적인가? 추가 리소스 필요 여부?
4. **우선순위**: Phase별 우선순위 조정이 필요한가?

### 11.2 피드백 수집
**다음 단계로 진행하기 전에 아래 질문에 대한 피드백을 부탁드립니다**:

1. **알고리즘 선택**: 하이브리드 알고리즘(Option B)으로 진행할까요, 아니면 기존 알고리즘 개선(Option A)으로 할까요?
2. **UI 범위**: 5.2절의 완전 버전으로 구현할까요, 아니면 단계적으로 출시할까요?
3. **Step 1 연동**: Step 1의 Total Score를 군집화에 반영하는 것에 동의하시나요?
4. **추가 요구사항**: 이 계획서에서 누락된 기능이나 요구사항이 있나요?

---

**작성자**: AI Assistant  
**검토자**: 대장 (Com2uS R마케팅팀장)  
**최종 수정일**: 2026-04-09  
**문서 상태**: 🟡 검토 대기 중 (Pending Review)

---

## 📞 문의 사항
계획서에 대한 질문이나 피드백은 언제든지 말씀해주세요!
