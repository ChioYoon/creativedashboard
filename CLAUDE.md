# CLAUDE.md — Com2uS R팀 소재 분석 대시보드
> Claude Code 작업 가이드 | 최종 업데이트: 2026-10-13

---

## 1. 프로젝트 한 줄 요약

모바일 게임 광고 소재(BNR/VID) 성과 분석 시스템. 두 축:
- **정적 대시보드**(브라우저 단독): CSV 업로드/붙여넣기 → Rank 점수 → 피로도 → Gemini AI 인사이트. `step1_integrated.html` 메인.
- **백엔드 nightly 파이프라인**(`pipeline/`, Python): 매일 밤 Google Ads + MMP(Airbridge/AppsFlyer) 수집·소재 태깅(Gemini)·점수 산출 → `public/data/{title}.json` → GitHub Pages 라이브 서빙(`live_dashboard.html`).

> ⚠️ 예전 "백엔드 없음" 설명은 옛말 — 이제 nightly 파이프라인이 데이터를 생성함(작업 스케줄러 `CLOOP-Nightly`, 13:00).

---

## 2. 핵심 파일 맵

```
프로젝트 루트/
├── index.html                  홈(랜딩) — 진입점
├── step1_integrated.html   ★ 소재 분석(메인, ~9,000줄) — 파싱·분석 엔진 인라인 포함
├── live_dashboard.html         라이브 대시보드 (public/data JSON 자동 로드)
├── pre_eval.html               소재 사전 평가 (Gemini Vision)
├── step2_column_selector.html  군집화 ① 컬럼·가중치
├── step2_clustering.html       군집화 ② 실행·결과
├── 사용안내서_인쇄용.html       사용 안내서(인쇄용, v5.11)
├── js/
│   ├── gemini-api.js       ★ Gemini 프롬프트·파서·렌더러 (외부 <script src>, step1도 이걸 로드)
│   ├── data-source.js          titles.json / public/data JSON 로드·정규화
│   ├── canonical-filter.js     5차원 캐노니컬 필터(캠페인목적/국가/OS/매체/상품)
│   ├── layer-metrics.js        Google Ads / MMP 레이어 지표·라벨(layerLabels)
│   ├── live-dashboard.js       라이브 대시보드 로직(LIVE.*)
│   ├── access-gate.js          외부 공유용 접근 고지 게이트
│   ├── pipeline-engine.js      CSV 파싱·정규화·검증(원본, step1에 인라인 복사됨)
│   ├── titles.json             타이틀 등록 + _pipeline_* 설정 + _ui_hidden
│   └── titles_overrides.json   소재명 별칭 매핑
├── css/gemini-ui.css           AI 인사이트 카드 스타일
├── pipeline/               ★ 백엔드 nightly (Python): main.py · sources/(google_ads·airbridge·appsflyer)
│                             · scoring.py · mmp_metrics.py · tagger.py · campaign_canonical.py
│                             · media_normalize.py · schemas.py · notify.py · game_context/*.md
├── public/data/{title}.json    파이프라인 산출물(대시보드가 fetch)
├── scripts/nightly.ps1         nightly 실행(작업 스케줄러 CLOOP-Nightly)
├── docs/                       설계·레퍼런스(measurement-reference·mmp-channel-media-design 등)
└── sample_data/                테스트용 CSV
```

### ⚠️ 중요: step1 인라인화 규칙
`step1_integrated.html`은 파싱·분석 엔진(pipeline-engine 등)을 HTML 내부 `<script>` 블록에 **인라인 복사**해 자립 실행함(과거 CSP 회피 잔재. live_dashboard·step2 등 다른 페이지는 외부 `<script src>` 정상 사용).

- **step1 로직 수정 시 반드시 HTML 내 인라인 블록을 직접 수정** — 외부 원본 js 수정은 step1에 반영 안 됨
- `gemini-api.js`는 예외 — step1도 외부 `<script src>`로 로드(인라인 아님)
- ⚠️ 인라인 analysis-engine 블록(`aggregateCreativeData`·`calculateRankScores`·`runStep1_Scoring` 등)과 인라인 `plDetectTagColumns`·`plCalcScores` 등은 **호출되지 않는 죽은 코드**. 실제 점수 경로는 `aggregateCreatives` → `calculateCreativeScores`(§4). 원본 `analysis-engine-v2.js` 는 `archive/js/` 에만 있음

---

## 3. step1_integrated.html 내부 구조 (함수 인덱스)

> 라인 번호는 수시로 바뀜 — **함수명으로 `grep`** 할 것. 컬럼 정렬은 `data-sortkey`(TotalScore/__mmpscore 등), 점수 표시명은 GA=종합점수 / MMP=MMP 품질점수(로직 키와 분리됨).

| 함수 | 역할 |
|------|------|
| `calculateScores()` | 점수 계산 메인 — 필터·집계·점수·렌더 오케스트레이션, MMP 레이어 재계산 포함 |
| `aggregateCreatives(rows, groupBy)` | 소재별 집계. `meta` 는 첫 행의 **사본**(MMP 재계산이 meta 를 덮어씀 — 원본 rawData 오염 금지) |
| `calculateCreativeScores(...)` | Rank 기반 점수·등급 (Python 포트 `pipeline/scoring.py` 와 동일성 유지 — `scripts/verify-scoring.py`) |
| `getReportWeights()` | 슬라이더 가중치를 **합계로 정규화**. 분석 실행·피로도·보고서 공용 |
| `displayScoringResults()` | 결과 렌더링 (표·제외목록·배지) |
| `renderTypeSummaryTable()` | BNR/VID 유형별 요약표 |
| `runFatigueAnalysis()` | 피로도 분석 |
| `openPreviewModal()` / `showFatigueModal()` | 소재 상세 모달 |
| `runScoringAIInsight()` / `runFatigueAIInsight()` | Gemini AI 인사이트 |

### XSS 규칙 (step1·live 공통)
- 소재명·캠페인명·파일명·링크 등 **데이터 값은 innerHTML 에 넣기 전 `escapeHtml()`**. 대행사 입력값이라 신뢰 불가
- 인라인 `onclick` 인자는 **`jsAttr(값)`** 로 생성 (JSON 리터럴 + 속성 이스케이프). `'${x}'` 수동 이스케이프 금지

---

## 4. 핵심 데이터 흐름

```
타이틀 선택(public/data JSON) 또는 CSV 업로드/붙여넣기
  └─ processCSV / DataSource.loadCreativeData   # 파싱·컬럼 정규화(plParseCSV·plNormalizeColumns 인라인)
            ↓
calculateScores()
  └─ aggregateCreatives()        # 소재별 집계 (meta = 첫 행 사본)
  └─ getReportWeights()          # 가중치 합계 정규화
  └─ calculateCreativeScores()   # Rank 점수·가중평균·등급
  └─ (MMP 레이어) aggMmpWindow → scoreMmpItems   # js/layer-metrics.js
  └─ displayScoringResults()     # 렌더링 → renderTypeSummaryTable()
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

## 5. 분석 결과 섹션

DOM 구조는 자주 바뀜 — `displayScoringResults()` 와 `id="tableBody"` 를 기준으로 grep. (HTML 추출 기능 `exportResultHTML`·`#exportBtnContainer` 는 02d53ed 에서 제거됨)

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
위치: step1_integrated.html calculateCreativeScores / getReportWeights (grep)
주의: 인라인 analysis-engine 블록은 죽은 코드 — 거기 고쳐도 반영 안 됨
     공식 변경 시 pipeline/scoring.py 도 동일하게 + scripts/verify-scoring.py 통과 확인
```

### ② AI 프롬프트 수정
```
위치: js/gemini-api.js
      GeminiPrompts.scoringInsight() — line ~491
      GeminiPrompts.fatigueInsight() — line ~659
주의: gemini-api.js는 외부 파일 그대로 수정 가능
```

### ③ 결과 UI 추가/수정
```
CSS: step1_integrated.html 인라인 style 블록 (모바일 ≤768px: 사이드바 접힘+오버레이)
     css/gemini-ui.css (AI 인사이트 카드만)
JS 렌더링: displayScoringResults()
공용 js/css 수정 시 HTML ?v= 캐시버스터는 pre-commit 훅이 자동 갱신(tools/bump_cache_busters.py)
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

## 11. nightly 파이프라인 운영 메모

- 종료 코드: 0 정상 · 1 파이프라인 실패(타이틀 partial/exception, KPI·MMP fetch 실패 포함) · 2 git 단계(commit·pull·push) 실패
- 로그: `logs/nightly_*.log`. 작업 스케줄러 `CLOOP-Nightly` 13:00, 실행 제한 3시간
- push 전 `git pull --rebase --autostash`. 커밋은 `public/data` + 브리프 미러(`js/brand_briefs.json`·`js/gate_registry.json`) 경로로 한정
- KPI/MMP fetch 실패 날은 `{title}.json` 미갱신(이전 산출물 유지). fetch 는 일시 오류 3회 재시도
- MMP 전환은 **캠페인 유형별**(NU-Pre=등록, NU=D1잔존). 등록 이벤트 설정 타이틀도 NU·RT 실적이 생기면 설치 기준(ROAS 축 포함)으로 자동 전환
- 처리 대상: `js/titles.json` `_pipeline_enabled=true` (gd·pepp-us 는 레거시로 비활성)
- push 뒤 격리 실행: `bq_export`(비활성) · `sheets_export`(BI 포털용 Google Sheets 4탭 전체 교체, `SHEETS_EXPORT_ENABLED` 게이팅, 셋업 `docs/sheets-export-setup.md`)
- 미완: SMTP 메일 알림(앱 비밀번호 미설정 — 실패 알림이 안 감)

---

## 12. 테스트 체크리스트

작업 후 아래 항목 확인:

```
□ 브라우저 콘솔 JS 오류 0건
□ "✅ Step 1 통합 페이지 로드 완료" 로그 확인
□ sample_data/PH_SL_260508.csv 로 점수 계산 실행 → 결과 정상 출력
□ AI 인사이트 버튼 클릭 → 로딩 후 결과 카드 렌더링
□ pytest · scripts/verify-scoring.py · node --test tests/js/canonical-filter.test.js 통과
□ 모바일 뷰포트(375px)에서 레이아웃 깨짐 없음
```

---

## 13. 주요 전역 변수

```javascript
// step1_integrated.html 전역
rawData            // 파싱된 원본 CSV rows
normalizedData     // 컬럼 정규화 후 { columns, rows }
scoredCreatives    // 점수 계산 결과 배열 (displayScoringResults 입력)
window.currentCreatives  // 모달·보고서·AI 인사이트가 사용하는 현재 결과
currentGroupBy     // '소재명' | '파일명'
currentCampaign    // 선택된 캠페인 필터값
_lastFatigueData   // 피로도 분석 결과 캐시
```

---

*이 파일은 Claude Code 세션 시작 시 자동으로 참조됩니다.*
*프로젝트 루트에 위치시키면 Claude Code가 컨텍스트로 인식합니다.*
