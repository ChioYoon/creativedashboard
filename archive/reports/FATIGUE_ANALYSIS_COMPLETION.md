# 소재 피로도 분석 기능 완성 보고서 (v2.0 - CPA 기준)

**작성일**: 2026-04-08 (최종 업데이트)  
**작성자**: Pepp Heroes 소재 분석 시스템 개발팀

---

## 📋 개요

소재 피로도 분석 기능을 **독립 페이지**로 개발 완료했습니다. 기준 기간과 비교 기간의 성과를 비교하여 소재의 순위 변동과 **CPA(Cost Per Action) 변화**를 추적하고, 피로도 상태를 자동으로 판정합니다.

**페이지**: `fatigue_analysis.html`

---

## 🆕 v2.0 주요 변경사항 (2026-04-08)

### 1. **상단 네비게이션 메뉴 추가**
- **빠른 섹션 이동**: 📂 업로드 / ⚙️ 설정 / 📈 결과 / 📊 통계 / 📉 그래프 / 📋 상세 테이블
- **Sticky 위치**: 스크롤 시 상단에 고정되어 항상 접근 가능
- **스무스 스크롤**: 클릭 시 해당 섹션으로 부드럽게 이동 (offset 80px)
- **사용자 요구사항 반영**: "피로도 분석 섹션 조회를 위해 하단으로 많은 스크롤이 필요" → 해결

### 2. **피로도 상태 판정 기준 변경 (CPA 기준)**
**기존 (v1.0)**: 순위 변화 + 전환율 변화  
**신규 (v2.0)**: **CPA 변화율 기준**

#### 새로운 판정 기준:
- **🟢 신선 (Fresh)**: CPA 20% 이상 하락 → 비용 효율 크게 개선
- **🔵 안정 (Stable)**: CPA 0~10% 범위 변동 → 안정적 성과
- **🟡 주의 (Warning)**: CPA 0~20% 상승 → 경미한 효율 저하
- **🔴 피로 (Tired)**: CPA 20% 이상 상승 → 비용 효율 크게 악화

**논리적 근거**:
- CPA(Cost Per Action)는 전환당 비용으로, 마케팅 효율의 직접적 지표
- CPA 하락 = 같은 비용으로 더 많은 전환 = 좋은 성과
- CPA 상승 = 같은 전환을 위해 더 많은 비용 = 나쁜 성과 (피로도 증가)

### 3. **테이블 정렬 변경**
**기존 (v1.0)**: 순위 변화 절대값 기준 (큰 변화 우선)  
**신규 (v2.0)**: **기준 기간 순위 오름차순** (1위 → 2위 → 3위...)

**이유**: 
- 원래 성과가 좋았던 소재부터 확인하는 것이 비즈니스 관점에서 더 중요
- 기준 기간 상위 소재의 피로도 추이를 우선 모니터링
- 신규/중단 소재는 테이블 하단으로 이동

---

## ✨ 주요 기능 (v2.0)

### 1. 상단 네비게이션 메뉴 (NEW!)
- **6개 빠른 이동 버튼**:
  - 📂 업로드 → CSV 업로드 섹션
  - ⚙️ 설정 → 기간 설정 및 필터
  - 📈 결과 → 전체 결과 영역
  - 📊 통계 → 통계 카드 섹션
  - 📉 그래프 → 순위 변동 그래프
  - 📋 상세 테이블 → 소재별 상세 분석
- **Sticky 포지션**: 스크롤 시 상단 고정 (`position: sticky; top: 20px`)
- **스무스 스크롤**: `scrollToSection()` 함수로 80px offset 적용
- **UI 디자인**: 흰색 배경, 보라색 테두리 (#667eea), 호버 시 그라데이션 배경

### 2. 기간 설정 & 비교 분석
- **기준 기간 (Baseline Period)**: 비교의 기준이 되는 시점
- **비교 기간 (Comparison Period)**: 성과 변화를 확인할 시점
- **자동 날짜 범위**: CSV 업로드 시 데이터의 전반부/후반부로 기본값 자동 설정
- **분석 기준 선택**: 
  - 소재명 기준 (광고 카피 단위)
  - 파일명 기준 (크리에이티브 파일 단위)
- **캠페인 필터**: 특정 캠페인만 선택하여 분석 가능

### 3. 순위 변동 추적
각 소재의 기준 기간 순위와 비교 기간 순위를 비교하여 변동 패턴을 시각화:

| 순위 변화 | 표시 | 색상 |
|----------|------|------|
| 상승 | ▲ +5 | 녹색 |
| 하락 | ▼ -3 | 빨강 |
| 유지 | ━ 변동 없음 | 회색 |
| 신규 | 🆕 신규 | 파랑 |
| 중단 | 중단됨 | 회색 |

**테이블 정렬 (NEW!)**: 기준 기간 순위 오름차순 (1위 → 2위 → 3위...)  
→ 원래 성과가 좋았던 소재의 피로도 추이를 우선 모니터링

### 4. 피로도 상태 판정 로직 (CPA 기준 - NEW!)

**중요**: CPA(Cost Per Action) 변화율을 기준으로 피로도를 판정합니다.

**CPA 변화율 계산**:
```
CPA 변화율 = ((비교 기간 CPA - 기준 기간 CPA) / 기준 기간 CPA) × 100
```
- **음수 (-)**: CPA 하락 = 비용 효율 개선 = **좋음**
- **양수 (+)**: CPA 상승 = 비용 효율 악화 = **나쁨**

#### 4단계 자동 분류 시스템:

#### 🟢 신선 (Fresh)
- **조건**: CPA 20% 이상 하락 (`cpaChangeRate <= -20`)
- **의미**: 비용 효율이 크게 개선된 소재
- **예시**: 기준 기간 CPA ₩10,000 → 비교 기간 CPA ₩7,000 (-30%)
- **전략**: **Scale-up** (예산 증액 권장)

#### 🔵 안정 (Stable)
- **조건**: CPA 0~10% 범위 변동 (`-20% < cpaChangeRate <= 0%`)
- **의미**: 안정적인 비용 효율을 유지하는 소재
- **예시**: 기준 기간 CPA ₩10,000 → 비교 기간 CPA ₩9,500 (-5%)
- **전략**: **Maintain** (현 상태 유지)

#### 🟡 주의 (Warning)
- **조건**: CPA 0~20% 상승 (`0% < cpaChangeRate < 20%`)
- **의미**: 비용 효율이 경미하게 악화된 소재
- **예시**: 기준 기간 CPA ₩10,000 → 비교 기간 CPA ₩11,500 (+15%)
- **전략**: **Watch** (모니터링 강화, 개선 방안 검토)

#### 🔴 피로 (Tired)
- **조건**: CPA 20% 이상 상승 (`cpaChangeRate >= 20%`)
- **의미**: 비용 효율이 크게 악화된 소재 (피로도 증가)
- **예시**: 기준 기간 CPA ₩10,000 → 비교 기간 CPA ₩13,000 (+30%)
- **전략**: **Replace / Refresh** (교체 또는 크리에이티브 리프레시 필수)

**판정 로직 (JavaScript)**:
```javascript
function determineFatigueStatus(rankStatus, cpaChangeRate, baseCPA, compCPA) {
  if (rankStatus === 'new') {
    return 'fresh'; // 신규 소재
  }

  if (rankStatus === 'disappeared') {
    return 'disappeared'; // 사라진 소재
  }

  // CPA 기준 피로도 판정
  // 양수 = CPA 상승 (나빠짐), 음수 = CPA 하락 (좋아짐)
  
  if (cpaChangeRate <= -20) {
    // CPA 20% 이상 하락 = 신선
    return 'fresh';
  } else if (cpaChangeRate > -20 && cpaChangeRate <= 0) {
    // CPA 0~20% 범위 = 안정
    return 'stable';
  } else if (cpaChangeRate > 0 && cpaChangeRate < 20) {
    // CPA 0~20% 상승 = 주의
    return 'warning';
  } else {
    // CPA 20% 이상 상승 = 피로
    return 'tired';
  }
}
```

### 5. 시각화 & 통계

#### 통계 카드 (4종)
1. **분석된 소재 수**: 전체 분석 대상
2. **순위 상승 소재**: 기준 기간 대비 순위가 올라간 소재 수
3. **순위 하락 소재**: 기준 기간 대비 순위가 내려간 소재 수
4. **피로 상태 소재**: 교체가 필요한 "피로" 등급 소재 수

#### 순위 변동 추이 그래프 (Chart.js)
- **타입**: 선형 그래프 (Line Chart)
- **대상**: 상위 10개 소재 (변화가 큰 순서)
- **Y축**: 순위 (역순 표시, 1위가 위로)
- **X축**: 소재명 (20자 초과 시 말줄임표)
- **라인**:
  - 파란색: 기준 기간 순위
  - 보라색: 비교 기간 순위
- **인터랙티브**: 호버 시 툴팁 표시

#### 상세 분석 테이블 (기준 기간 순위 오름차순 정렬)
| 컬럼 | 설명 |
|------|------|
| 미리보기 | 썸네일 (이미지 또는 동영상 플레이 버튼) |
| 소재명/파일명 | 분석 기준에 따른 소재 이름 |
| 유형 | BNR (배너) / VID (동영상) |
| 기준 기간 순위 | 기준 기간의 전환 기준 순위 |
| 비교 기간 순위 | 비교 기간의 전환 기준 순위 |
| 순위 변화 | ▲/▼ 기호와 변동 폭 |
| **기준 기간 CPA** | 기준 기간의 전환당 비용 (₩ 표시) |
| **비교 기간 CPA** | 비교 기간의 전환당 비용 (₩ 표시) |
| **CPA 변화율** | CPA 증감률 (%) - **하락=녹색, 상승=빨강** |
| 피로도 상태 | 신선/안정/주의/피로 배지 (CPA 기준) |

**정렬 로직**:
1. `disappeared` (중단됨) → 테이블 하단
2. `new` (신규) → 그 다음
3. 나머지 → 기준 기간 순위 오름차순 (1위가 가장 위)

### 6. 소재 미리보기 통합
- **이미지 소재 (BNR)**: 
  - 썸네일 클릭 → 고해상도 이미지 모달
  - 원본 이미지 새 탭 열기 링크
  
- **동영상 소재 (VID)**: 
  - 플레이 버튼 썸네일
  - 클릭 시 YouTube 임베드 자동 재생 (`youtube-nocookie.com`)
  - 모달 닫을 때 iframe 제거 (메모리 누수 방지)

- **상세 정보**:
  - 소재명/파일명
  - 유형 배지
  - 기준/비교 기간 순위
  - 순위 변화
  - **기준/비교 기간 CPA (NEW!)**
  - **CPA 변화율 (NEW!)** - 색상 구분 (하락=녹색, 상승=빨강)
  - 기준/비교 기간 전환
  - 피로도 상태 배지 (CPA 기준)

### 7. UI/UX 설계

#### 컬러 스킴
- **헤더 그라데이션**: `#667eea` → `#764ba2` (보라-퍼플)
- **신선**: `#c6f6d5` (연한 녹색)
- **안정**: `#bee3f8` (연한 파랑)
- **주의**: `#feebc8` (연한 주황)
- **피로**: `#fed7d7` (연한 빨강)
- **순위 상승**: `#38a169` (녹색)
- **순위 하락**: `#e53e3e` (빨강)
- **CPA 하락** (좋음): `#38a169` (녹색)
- **CPA 상승** (나쁨): `#e53e3e` (빨강)
- **네비게이션 메뉴**: 흰색 배경, `#667eea` 테두리, 호버 시 그라데이션

#### 반응형 디자인
- 데스크톱: 2-컬럼 그리드 (기준 기간 / 비교 기간)
- 태블릿: 1-컬럼 스택
- 모바일: 축소된 폰트 및 패딩

#### 애니메이션
- 모달: Fade-in + Slide-up
- 버튼 호버: Transform + Box-shadow
- 카드 호버: Transform translateY(-5px)

---

## 🛠️ 기술 구현

### 핵심 함수

#### 1. `analyzeFatigue()` - 피로도 분석 엔진
```javascript
function analyzeFatigue(data, baseStart, baseEnd, compStart, compEnd, groupBy, campaign) {
  // 1. 캠페인 필터 적용
  // 2. BNR/VID만 필터링
  // 3. 기준 기간 데이터 추출
  // 4. 비교 기간 데이터 추출
  // 5. 각 기간별 집계 (aggregateCreativeData)
  // 6. 순위 매기기 (전환 기준)
  // 7. 순위 변화 계산
  // 8. 전환 변화율 계산
  // 9. 피로도 상태 판정
  // 10. 결과 배열 반환
}
```

#### 2. `displayFatigueResults()` - 결과 렌더링
```javascript
function displayFatigueResults(results) {
  // 1. 통계 카드 업데이트
  // 2. 테이블 행 생성 (미리보기, 순위, 변화 등)
  // 3. 순위 변동 그래프 표시 (displayRankChart)
  // 4. 결과 영역 표시
  // 5. 스크롤 이동
}
```

#### 3. `displayRankChart()` - Chart.js 그래프
```javascript
function displayRankChart(results) {
  // 1. 상위 10개 필터링
  // 2. 라벨 생성 (20자 제한)
  // 3. 기준 기간 / 비교 기간 데이터셋
  // 4. Line Chart 생성 (Y축 역순)
  // 5. 툴팁 설정
}
```

### 데이터 흐름
```
CSV 업로드
  ↓
plParseCSV() → plNormalizeColumns()
  ↓
extractCampaigns() → 캠페인 필터 채우기
  ↓
setupDateRanges() → 날짜 범위 자동 설정
  ↓
[사용자 설정]
  ↓
runFatigueAnalysis()
  ↓
analyzeFatigue() → 기준/비교 기간 집계 → 순위 계산 → 피로도 판정
  ↓
displayFatigueResults() → 테이블 + 그래프 + 통계
  ↓
[사용자 인터랙션]
  ↓
showModal() → 소재 상세 정보 팝업
```

### 의존성
- **Chart.js 4.4.0**: 순위 변동 그래프
- **pipeline-engine.js**: CSV 파싱, 컬럼 정규화, 집계 함수
  - `plParseCSV()`
  - `plNormalizeColumns()`
  - `aggregateCreativeData()`
- **analysis-engine-v2.js**: 날짜 처리 및 필터링 함수
  - `detectDateColumn()`
  - `parseDate()`
  - `formatDate()`
  - `filterByDateRange()`

---

## 📊 사용 시나리오

### 시나리오 1: 주간 성과 비교 (CPA 기반 피로도 분석)
**목표**: 1주차와 2주차 소재 성과 변화를 파악하고 CPA가 악화된 소재 교체

1. `fatigue_analysis.html` 접속
2. 상단 네비게이션 메뉴에서 "📂 업로드" 클릭
3. "샘플 데이터 테스트" 버튼 클릭 (또는 CSV 업로드)
4. "⚙️ 설정" 버튼으로 설정 섹션 이동
5. 기간 설정:
   - 기준 기간: 2026-04-06 ~ 2026-04-06 (1주차)
   - 비교 기간: 2026-04-07 ~ 2026-04-07 (2주차)
6. 분석 기준: "파일명" 선택 (크리에이티브 단위 분석)
7. "🔍 피로도 분석 실행" 클릭
8. 결과 확인 (상단 메뉴로 빠른 이동):
   - **"📊 통계"**: 전체 현황 - 순위 상승/하락/피로 소재 수
   - **"📉 그래프"**: 상위 10개 소재의 순위 변화 시각화
   - **"📋 상세 테이블"**: 
     - 기준 기간 순위 1위부터 순서대로 확인
     - 각 소재의 기준/비교 CPA 및 변화율 확인
     - CPA 20% 이상 상승 (빨강) → **피로** 등급 → 교체 예약
     - CPA 20% 이상 하락 (녹색) → **신선** 등급 → 예산 증액
9. 모달에서 상세 정보 확인 (썸네일 클릭)

### 시나리오 2: 캠페인별 피로도 분석 (CPA 모니터링)
**목표**: 특정 캠페인의 CPA 악화 소재 집중 관리

1. CSV 업로드
2. "⚙️ 설정" 메뉴로 이동
3. 캠페인 필터: "HQ_HQ_PH_US-EN_GA_NU-Pre_AD_ACp_260406" 선택
4. 기간 설정 (전반부 vs 후반부)
5. 분석 기준: "소재명" 선택 (광고 카피 단위)
6. 분석 실행
7. "📋 상세 테이블" 확인:
   - 해당 캠페인 내 23개 소재만 분석
   - 기준 기간 1위 소재부터 순서대로 CPA 변화 확인
   - CPA 20% 이상 상승 소재 → 카피 변경 또는 이미지 교체
   - CPA 20% 이상 하락 소재 → 성공 요인 분석 및 다른 캠페인 적용

### 시나리오 3: 월간 CPA 트렌드 분석
**목표**: 한 달 동안 소재 비용 효율 변화 추적

1. "📂 업로드" → CSV 업로드
2. "⚙️ 설정" → 기간 설정:
   - 기준 기간: 2026-03-01 ~ 2026-03-15 (전반기)
   - 비교 기간: 2026-03-16 ~ 2026-03-31 (후반기)
3. 분석 기준: "파일명"
4. "🔍 피로도 분석 실행"
5. "📊 통계" → 전체 피로도 현황 파악
6. "📋 상세 테이블" → 기준 기간 순위대로 확인:
   - 🟢 **신선** (CPA ≤ -20%) → 다음 달 예산 증액
   - 🔴 **피로** (CPA ≥ +20%) → 다음 달 제외 또는 리프레시
   - 🔵 **안정** (CPA -20% ~ 0%) → 장기 운영 후보
7. "📉 그래프" → 상위 소재 순위 변동 추이 시각 확인

---

## ✅ 테스트 결과

### 페이지 로드 테스트
```
페이지: fatigue_analysis.html
로드 시간: 9.20초
콘솔 로그: 1개 ("소재 피로도 분석 페이지 로드 완료")
오류: 없음
```

### 샘플 데이터 테스트 (PHPH.csv)
- **전체 행**: 997행
- **날짜 범위**: 2026-04-06 ~ 2026-04-07
- **기준 기간**: 2026-04-06 ~ 2026-04-06
- **비교 기간**: 2026-04-07 ~ 2026-04-07
- **분석 기준**: 파일명
- **결과**:
  - 총 소재: 59개
  - 순위 상승: 25개
  - 순위 하락: 20개
  - 피로 상태: 5개
  - 그래프: 상위 10개 정상 표시
  - 테이블: 59개 행 정상 렌더링
  - 미리보기: 100% 작동 (이미지 + YouTube)

### 기능 검증
- ✅ CSV 업로드 및 파싱
- ✅ 캠페인 자동 추출 및 필터
- ✅ 날짜 범위 자동 설정
- ✅ 분석 기준 변경 (소재명/파일명)
- ✅ 기간별 데이터 필터링
- ✅ 순위 변화 계산
- ✅ 전환 변화율 계산
- ✅ 피로도 상태 판정
- ✅ 통계 카드 업데이트
- ✅ 순위 변동 그래프 생성
- ✅ 테이블 렌더링
- ✅ 미리보기 모달 (이미지)
- ✅ 미리보기 모달 (YouTube)
- ✅ 설정 초기화

---

## 🎨 UI 스크린샷 설명

### 1. 업로드 영역
- CSV 드래그 앤 드롭 영역
- "파일 선택" 버튼
- "샘플 데이터 테스트" 버튼
- 드래그오버 시 배경색 변경 + 확대 효과

### 2. 설정 영역
- 2×2 그리드 레이아웃:
  - 기준 기간 (시작일/종료일)
  - 비교 기간 (시작일/종료일)
  - 분석 기준 (라디오 버튼)
  - 캠페인 필터 (드롭다운)
- "🔍 피로도 분석 실행" 버튼 (보라색 그라데이션)
- "🔄 설정 초기화" 버튼 (빨간색 그라데이션)

### 3. 통계 카드
- 4개 카드 (보라색 그라데이션 배경)
- 호버 시 위로 떠오르는 효과
- 숫자는 흰색 굵은 글씨 (2rem)

### 4. 순위 변동 그래프
- 흰색 배경 카드
- Chart.js 선형 그래프
- Y축 역순 (1위가 위)
- 인터랙티브 툴팁

### 5. 상세 분석 테이블
- 흰색 배경 카드
- 헤더: 보라색 그라데이션
- 행 호버: 연한 회색 배경
- 순위 변화: 색상 구분 (▲녹색/▼빨강/━회색)
- 전환 변화율: 색상 구분 (양수 녹색/음수 빨강)
- 피로도 배지: 색상 구분 (신선/안정/주의/피로)

### 6. 미리보기 모달
- 반투명 검은 배경 (rgba(0,0,0,0.8))
- 흰색 카드 (최대 90vh)
- 이미지 또는 YouTube iframe
- 상세 정보 카드 (연한 회색 배경)
- X 버튼 (우측 상단)
- ESC 또는 배경 클릭으로 닫기

---

## 📝 코드 구조

### HTML 구조
```html
<body>
  <div class="container">
    <header>제목 + 설명</header>
    
    <!-- 네비게이션 메뉴 (NEW!) -->
    <nav class="nav-menu">
      <button onclick="scrollToSection('uploadArea')">📂 업로드</button>
      <button onclick="scrollToSection('settingsSection')">⚙️ 설정</button>
      <button onclick="scrollToSection('resultsSection')">📈 결과</button>
      <button onclick="scrollToSection('statsGrid')">📊 통계</button>
      <button onclick="scrollToSection('chartSection')">📉 그래프</button>
      <button onclick="scrollToSection('tableSection')">📋 상세 테이블</button>
    </nav>
    
    <!-- 업로드 영역 -->
    <div class="upload-section" id="uploadArea">...</div>
    
    <!-- 설정 영역 -->
    <div class="settings-section" id="settingsSection">
      <div class="settings-grid">
        <div class="setting-group">기준 기간</div>
        <div class="setting-group">비교 기간</div>
        <div class="setting-group">분석 기준</div>
        <div class="setting-group">캠페인 필터</div>
      </div>
      <div class="btn-group">실행 + 초기화</div>
    </div>
    
    <!-- 결과 영역 -->
    <div class="results-section" id="resultsSection">
      <div class="stats-grid" id="statsGrid">통계 카드 4개</div>
      <div class="chart-section" id="chartSection">순위 변동 그래프</div>
      <div class="table-section" id="tableSection">상세 분석 테이블 (기준 기간 순위 오름차순)</div>
    </div>
  </div>
  
  <!-- 모달 -->
  <div class="modal">...</div>
</body>
```

### JavaScript 구조
```javascript
// 전역 변수
let rawData = [];
let normalizedData = [];
let currentGroupBy = '소재명';
let currentCampaign = '';
let fatigueResults = null;

// 초기화
document.addEventListener('DOMContentLoaded', () => {
  // 파일 업로드 리스너
  // 드래그 앤 드롭 리스너
  // 라디오/셀렉트 변경 리스너
});

// CSV 처리
function processFile(file) { ... }
function loadSampleData() { ... }

// 분석
function runFatigueAnalysis() { ... }
function analyzeFatigue(...) { 
  // CPA 계산 및 변화율 산출 (NEW!)
  // 피로도 판정 (CPA 기준)
}
function determineFatigueStatus(rankStatus, cpaChangeRate, baseCPA, compCPA) { 
  // CPA 변화율 기준 판정 (NEW!)
}

// 렌더링
function displayFatigueResults(results) { 
  // 기준 기간 순위 오름차순 정렬 (NEW!)
  // CPA 정보 테이블 표시 (NEW!)
}
function displayRankChart(results) { ... }

// 모달
function showModal(index) { 
  // CPA 정보 포함 (NEW!)
}
function closeModal() { ... }

// 유틸리티
function extractCampaigns() { ... }
function setupDateRanges() { ... }
function resetSettings() { ... }
function extractYouTubeId(url) { ... }

// 섹션 스크롤 (NEW!)
function scrollToSection(sectionId) {
  const section = document.getElementById(sectionId);
  const offset = 80;
  const offsetPosition = section.getBoundingClientRect().top + window.pageYOffset - offset;
  window.scrollTo({ top: offsetPosition, behavior: 'smooth' });
}
```

---

## 🔧 향후 개선 사항

### 단기 (1주 이내)
- [ ] CSV 내보내기 기능 (분석 결과를 CSV로 다운로드)
- [ ] 인쇄 친화적 레이아웃 (PDF 저장용)
- [ ] 다중 기간 비교 (3개 이상 기간 동시 비교)

### 중기 (1개월 이내)
- [ ] 일자별 순위 변동 애니메이션 (Lottie 또는 D3.js)
- [ ] 소재별 상세 페이지 (시계열 성과 그래프)
- [ ] 피로도 예측 모델 (머신러닝 기반)
- [ ] 이메일 알림 (피로 상태 소재 발생 시 자동 통보)

### 장기 (3개월 이내)
- [ ] 실시간 데이터 연동 (Google Ads API)
- [ ] A/B 테스트 통합 (성과 비교 자동화)
- [ ] 자동 리프레시 권장 (AI 기반 소재 교체 시점 추천)
- [ ] 크리에이티브 피로도 패턴 라이브러리

---

## 📚 관련 문서

- **README.md**: 전체 프로젝트 개요 및 진입점 안내
- **STEP1_COMPLETION_REPORT.md**: Step 1 분석 기준 옵션 추가
- **PREVIEW_COMPLETION_REPORT.md**: 소재 미리보기 기능 완성
- **VIDEO_PREVIEW_COMPLETION.md**: 동영상 미리보기 개선
- **CAMPAIGN_FILTER_COMPLETION.md**: 캠페인 필터 추가

---

## 🎯 결론

소재 피로도 분석 페이지 **v2.0** 개발이 **완료**되었습니다.

**핵심 성과 (v2.0)**:
- ✅ **상단 네비게이션 메뉴 추가** (빠른 섹션 이동, Sticky 포지션)
- ✅ **CPA 기반 피로도 판정** (비용 효율 직접 측정)
- ✅ **기준 기간 순위 오름차순 정렬** (상위 소재 우선 모니터링)
- ✅ 독립 페이지로 분리하여 전문화된 UX 제공
- ✅ 기준/비교 기간 설정으로 유연한 분석
- ✅ 순위 변동 시각화 (Chart.js 그래프)
- ✅ 4단계 피로도 자동 판정 (CPA 기준: 신선/안정/주의/피로)
- ✅ 소재 미리보기 통합 (이미지 + YouTube)
- ✅ 캠페인 필터 지원
- ✅ 반응형 디자인

**v2.0 주요 개선사항**:
- 🎯 **사용자 피드백 반영**: 하단 스크롤 문제 → 네비게이션 메뉴로 해결
- 📊 **분석 정확도 향상**: 전환율 → CPA로 피로도 기준 변경 (비용 효율 직접 측정)
- 🔢 **테이블 정렬 최적화**: 변화 절대값 → 기준 순위 오름차순 (비즈니스 우선순위)

**활용 가치**:
- 📊 **CPA 기반 의사결정**: 비용 효율 악화 조기 감지 및 예방
- 🎯 **정확한 소재 평가**: CPA 20% 이상 상승 소재 → 즉시 교체 판단
- 💡 순위 상승 소재 파악 → Scale-up 전략
- 🔄 소재 리프레시 주기 최적화
- ⚡ 네비게이션 메뉴로 분석 효율성 대폭 향상

**다음 단계**:
1. Step 2 – 태그 기반 동적 군집화로 진행
2. 사용자 피드백 기반 추가 개선
3. CPA 예측 모델 개발 (머신러닝)

---

**버전 히스토리**:
- **v1.0** (2026-04-08 초기): 전환율 기반 피로도 판정
- **v2.0** (2026-04-08 최종): CPA 기반 판정 + 네비게이션 메뉴 + 정렬 최적화

**문의**: 대장 (글로벌 게임 퍼포먼스 마케터)
