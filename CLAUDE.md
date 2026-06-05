# CLAUDE.md — Com2uS R팀 소재 분석 대시보드
> Claude Code 작업 가이드 | 최종 업데이트: 2026-05-21

---

## 1. 프로젝트 한 줄 요약

모바일 게임 광고 소재(BNR/VID) 성과를 CSV로 업로드 → Rank 기반 점수 계산 → 피로도 분석 → Gemini AI 인사이트까지 제공하는 **순수 정적(Static) 단일 파일 대시보드**.
백엔드 없음. 서버 없음. 브라우저에서 직접 실행.

---

## 2. 핵심 파일 맵

```
프로젝트 루트/
├── step1_integrated.html   ★ 메인 작업 파일 (186KB, 약 4,200줄)
│                             — pipeline-engine.js + analysis-engine-v2.js 인라인 포함
├── js/
│   ├── gemini-api.js       ★ Gemini AI 프롬프트·파서·렌더러 (75KB)
│   └── analysis-engine-v2.js  (외부 파일 원본, step1에 인라인 복사됨)
│   └── pipeline-engine.js     (외부 파일 원본, step1에 인라인 복사됨)
├── css/
│   └── gemini-ui.css       AI 인사이트 카드 전용 스타일
├── index.html              홈 (Step1/Step2 진입점)
├── step2_column_selector.html  Step2-① 컬럼 선택
├── step2_clustering.html       Step2-② 군집화 실행
└── sample_data/            테스트용 CSV 파일들
```

### ⚠️ 중요: 인라인화 규칙
`step1_integrated.html`은 **Genspark sandbox CSP** 환경에서 외부 `<script src>` 로드가 차단되어,
`pipeline-engine.js`와 `analysis-engine-v2.js`의 내용이 HTML 내부 `<script>` 블록에 인라인으로 복사되어 있음.

- **수정 시 반드시 HTML 내 인라인 블록을 직접 수정**
- 외부 js 파일(원본)을 수정해도 step1_integrated.html에는 반영 안 됨
- `gemini-api.js`는 예외 — 외부 `<script src>` 방식 유지 (AI 기능만 관련, CSP 통과 확인됨)

---

## 3. step1_integrated.html 내부 구조 (라인 가이드)

| 라인 범위 | 내용 |
|-----------|------|
| 1 ~ 13 | `<head>`: Chart.js CDN, gemini-ui.css, gemini-api.js |
| 14 ~ 759 | `<style>` CSS 전체 |
| 760 ~ 854 | 네비게이션 + 헤더 + **업로드 섹션** (파일탭/붙여넣기탭) |
| 855 ~ 989 | 계산 기준 설정 섹션 (가중치 슬라이더, 필터 옵션) |
| 990 ~ 1080 | **분석 결과 섹션** HTML 구조 |
| 1081 ~ 1230 | 피로도 분석 섹션 |
| 1231 ~ 1290 | 차트 섹션 + 모달 + 로딩 인디케이터 |
| **1291 ~ 1640** | **인라인 pipeline-engine.js** |
| **1641 ~ 1812** | **인라인 analysis-engine-v2.js** |
| 1813 ~ 2371 | UI 유틸 함수 (switchUploadTab, processPastedCSV, processCSV 등) |
| **2372 ~ 2673** | **calculateScores()** — 점수 계산 메인 로직 |
| **2675 ~ 2789** | **displayScoringResults()** — 결과 렌더링 |
| **2790 ~ 3064** | **exportResultHTML()** — HTML 파일 다운로드 |
| **3069 ~ 3192** | **renderTypeSummary()** — BNR/VID 유형별 요약표 |
| 3194 ~ 3920 | resetScoring, 피로도 분석 함수군 |
| **3920 ~ 4130** | **runScoringAIInsight()** + `_buildUpgradeNudge()` |
| 4131 ~ 4230 | **runFatigueAIInsight()** |

---

## 4. 핵심 데이터 흐름

```
CSV 업로드/붙여넣기
  └─ processCSV(csvText, fileName)
       └─ plParseCSV()            # 파싱 (pipeline-engine.js 인라인, line ~1291)
       └─ plNormalizeColumns()    # 컬럼 정규화 (한글/영문 헤더 자동 매핑)
       └─ plDetectTagColumns()    # 태그 컬럼 자동 탐지
            ↓
calculateScores()                  # line 2372
  └─ aggregateCreativeData()      # 소재별 집계 (analysis-engine-v2.js 인라인, line ~1641)
  └─ calculateRankScores()        # Rank 기반 점수화
  └─ calculateTotalScore()        # 가중평균 총점
  └─ displayScoringResults()      # line 2675 → 화면 렌더링
       ├─ renderTypeSummary()     # line 3069 → BNR/VID 요약표
       └─ exportResultHTML()      # line 2790 → HTML 다운로드
```

### 점수 계산 공식
```javascript
// Rank 기반 정규화 (동점자: 동일 Rank 부여, 다음 Rank 건너뜀)
rankScore = (n - Rank + 1) / n * 100

// 지표별 처리
전환수점수: rankScore (전환수 많을수록 높음)
CPA점수:   rankScore (CPA 낮을수록 높음, 전환=0이면 0점 고정)
IPM점수:   rankScore (IPM 높을수록 높음, 노출=0이면 0점 고정)
ROAS점수:  rankScore (ROAS 높을수록 높음, Revenue 없으면 지표 제외)

// 가중평균 총점
TotalScore = Σ(지표점수 × 가중치%) / Σ(활성가중치%)

// 등급
최우수 ≥ 80 / 우수 ≥ 60 / 양호 ≥ 40 / 보통 ≥ 20 / 개선필요 < 20
```

---

## 5. 분석 결과 섹션 DOM 구조

```html
<section id="results">
  <!-- ① 스코어 카드 5개 -->
  <div class="stats-grid">           <!-- 5컬럼 그리드 -->
    #statTotal / #statMax / #statAvg / #statExcellent
    <div class="stat-card stat-card-poor"> #statPoor (개선필요 등급 카운트) </div>
  </div>

  <!-- ② HTML 추출 버튼 -->
  <div id="exportBtnContainer">      <!-- display:none → 결과 생성 시 show -->

  <!-- ③ 필터 조건 (JS 동적 삽입) -->
  <div id="filterSummarySlot">       <!-- displayScoringResults()에서 innerHTML 삽입 -->

  <!-- ④ AI 인사이트 -->
  <div id="scoringAIBox">

  <!-- ⑤ 유형별 요약 -->
  <div id="typeSummaryContainer">    <!-- renderTypeSummary()가 렌더링 -->

  <!-- ⑥ 상세 테이블 -->
  <table> <tbody id="tableBody">
</section>
```

---

## 6. gemini-api.js 구조

```
GEMINI_CONFIG 상수
  └─ FREE_TOKENS: 2000  (winning 1슬롯, 위닝+루징 포함)
  └─ PAID_TOKENS: 2500  (2슬롯 × 2회)

GeminiKeyManager     # API 키 localStorage 관리
callGeminiAPI()      # 실제 API 호출 + 재시도 로직

GeminiPrompts.scoringInsight()   # ★ 소재 성과 분석 프롬프트 빌더
  └─ 무료: winning 1슬롯 (위닝+루징 분리 구조 한 슬롯에 포함)
  └─ 유료 1회차: winning + losing
  └─ 유료 2회차: actionItems + scaleUp + stopNow
  ※ formatGap(포맷별 진단) 제거됨 (2026-05-21)

GeminiPrompts.fatigueInsight()   # 피로도 분석 프롬프트 빌더
  └─ 무료: riseReason 1슬롯
  └─ 유료: riseReason + fatigueDiag / swapTiming + opsAction

parseScoringSlots(raw)   # JSON 파싱 + 복원 (5단계 폴백)
buildScoringSlotCards(slots) # 슬롯 → HTML 카드 렌더링
  └─ winning 단독일 때 1컬럼 전체폭 렌더링

parseFatigueSlots(raw)
buildFatigueSlotCards(slots)
```

### 슬롯 키 매핑 (최신 기준)

| 키 | 플랜 | 설명 |
|----|------|------|
| `winning` | 무료+유료 | 위닝 소재 목록·공통패턴 (무료는 루징도 포함) |
| `losing` | 유료만 | 저효율 소재 별도 분석 |
| `actionItems` | 유료만 | 확장🟢/개선🟡/중단🔴 즉시 실행 액션 |
| `scaleUp` | 유료만 | 예산 확대 우선순위 |
| `stopNow` | 유료만 | 즉시 중단 소재 |
| `winTags` | (구버전) | → `winning`으로 자동 통합 (하위 호환) |

---

## 7. 자주 수정하는 포인트 & 주의사항

### ① 점수 계산 로직 수정
```
위치: step1_integrated.html line ~2372 (calculateScores)
      step1_integrated.html line ~1728 (runStep1_Scoring — 인라인)
      step1_integrated.html line ~1641 (aggregateCreativeData — 인라인)
주의: js/analysis-engine-v2.js 원본은 수정해도 HTML에 반영 안 됨
     → HTML 내 인라인 블록(line 1641~1812)을 직접 수정
```

### ② AI 프롬프트 수정
```
위치: js/gemini-api.js
      GeminiPrompts.scoringInsight() — line ~325
      GeminiPrompts.fatigueInsight() — line ~483
주의: gemini-api.js는 외부 파일 그대로 수정 가능
```

### ③ 결과 UI 추가/수정
```
HTML 구조: step1_integrated.html line ~990
CSS:       step1_integrated.html line ~14 (인라인 style 블록)
           css/gemini-ui.css (AI 인사이트 카드만)
JS 렌더링: displayScoringResults() line ~2675
```

### ④ HTML 추출 기능 수정
```
위치: exportResultHTML() — step1_integrated.html line ~2790
내용: Blob 다운로드 + 미리보기(BNR img / VID 썸네일) + 상세 컬럼
```

---

## 8. 컬럼 정규화 매핑 (주요 항목)

```javascript
// plNormalizeColumns() 내부 매핑 (line ~1350 근방)
'전환'     ← 전환, 설치, install, conversion, cv
'노출수'   ← 노출, impression, impr
'클릭수'   ← 클릭, click
'비용'     ← 비용, spend, cost
'매출'     ← 매출, revenue, roas_revenue
'소재명'   ← 소재명, creative, ad_name
'파일명'   ← 파일명, file, filename
'유형'     ← 유형, type, format (BNR/VID 자동 판별)
'링크'     ← 링크, url, image_url, link  → 미리보기에 사용
```

---

## 9. 알려진 제약 & 우회 방법

| 제약 | 원인 | 현재 해결 방법 |
|------|------|---------------|
| 외부 JS 로드 불가 | Genspark sandbox CSP | pipeline-engine.js + analysis-engine-v2.js 인라인화 |
| `fileInput.click()` 차단 | iframe sandbox 보안 | input[type=file]을 `position:absolute; opacity:0; inset:0` overlay로 변경 |
| Gemini rate limit | 무료 분당 15회 한도 | 무료 1회/유료 2회 호출 분리 + 1600ms 대기 |
| JSON 잘림 | 토큰 예산 초과 | 5단계 폴백 복원 로직 (`_cleanAndRepairJson`) |

---

## 10. 로컬 개발 환경 설정

```bash
# 1. 클론 또는 다운로드
# 2. 로컬 서버 실행 (CORS 이슈 방지)
npx serve .
# 또는
python -m http.server 8080
# 또는 VS Code Live Server 익스텐션

# 3. 브라우저에서 열기
http://localhost:8080/step1_integrated.html
```

### Claude Code 작업 시 권장 플로우
```
1. step1_integrated.html 수정
2. 브라우저 새로고침으로 즉시 확인 (F5)
3. 브라우저 콘솔(F12) → "✅ Step 1 통합 페이지 로드 완료" 확인
4. JS 오류 없으면 완료
```

---

## 11. 현재 버전 기준 미완성/후속 개발 후보

| 항목 | 설명 | 우선순위 |
|------|------|---------|
| AI 인사이트 UI 렌더링 개선 | winning 슬롯 내 위닝/루징 블록을 시각적으로 분리 (카드 내 섹션 구분선, 배지 등) | 🔴 높음 |
| 사용안내서 최신화 | `사용안내서_인쇄용.html` — CSV 붙여넣기 탭, 저조소재 카드, HTML추출 미리보기 반영 | 🟡 중간 |
| README.md 업데이트 | 5/19~20 변경사항 반영 (현재 4/13 기준) | 🟡 중간 |
| Step2 군집화 AI 인사이트 | step2_clustering.html — Gemini 연동 미완성 | 🟢 낮음 |
| 레거시 파일 정리 | test_*.html, 완료보고서 .md 파일 다수 → 별도 폴더로 이동 | 🟢 낮음 |

---

## 12. 테스트 체크리스트

작업 후 아래 항목 확인:

```
□ 브라우저 콘솔 JS 오류 0건
□ "✅ Step 1 통합 페이지 로드 완료" 로그 확인
□ sample_data/PH_SL_260508.csv 로 점수 계산 실행 → 결과 정상 출력
□ AI 인사이트 버튼 클릭 → 로딩 후 결과 카드 렌더링
□ HTML 추출 버튼 → 파일 다운로드 확인
□ 모바일 뷰포트(375px)에서 레이아웃 깨짐 없음
```

---

## 13. 주요 전역 변수

```javascript
// step1_integrated.html 전역
rawData            // 파싱된 원본 CSV rows
normalizedData     // 컬럼 정규화 후 { columns, rows }
scoredCreatives    // 점수 계산 결과 배열 (displayScoringResults 입력)
window.currentCreatives  // exportResultHTML에서 사용
currentGroupBy     // '소재명' | '파일명'
currentCampaign    // 선택된 캠페인 필터값
_lastFatigueData   // 피로도 분석 결과 캐시
```

---

*이 파일은 Claude Code 세션 시작 시 자동으로 참조됩니다.*
*프로젝트 루트에 위치시키면 Claude Code가 컨텍스트로 인식합니다.*
