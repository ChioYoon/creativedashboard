# Com2uS R팀 소재 분석 시스템 (대시보드 + 파이프라인)

## 프로젝트 개요
Com2uS R마케팅팀 담당 모바일 게임들의 광고 소재(BNR/VID) 성과 분석 시스템입니다. 두 축으로 구성됩니다.

- **정적 대시보드**(브라우저 단독 실행, 백엔드 없음) — CSV 업로드/붙여넣기 → Rank 기반 점수 계산 → 피로도 분석 → Gemini AI 인사이트. `step1_integrated.html`이 메인.
- **백엔드 nightly 파이프라인**(`pipeline/`, Python) — 매일 밤 Google Ads + MMP(AppsFlyer/Airbridge) 지표를 자동 수집·소재 태깅(Gemini)·점수 산출해 `public/data/{title}.json`으로 저장. 대시보드가 이 JSON을 자동 로드(`live_dashboard.html`).
- **사용 대상 타이틀**: R팀 담당 전체 타이틀 (`js/titles.json` 등록). 라이브 노출은 제우스(외부 대행사 공유용 접근 고지 게이트 적용, `js/access-gate.js`).

---

## 🔑 Gemini API 키 발급 (첫 사용자 필수)

R팀 담당자별로 **개별 키**를 발급해서 사용합니다. (공용 키 미배포)

1. https://aistudio.google.com/apikey 접속 → 본인 Google 계정 로그인
2. **"Create API key"** 클릭 → `AIza...`로 시작하는 키 발급 (무료)
3. 대시보드 첫 접속 시 우상단 **"✨ AI 설정"** → 발급한 키 입력 → "저장"
4. 키는 본인 브라우저(localStorage)에만 저장되며 **서버·레포에 보관되지 않습니다.**

**무료 한도**: 분당 15회 / 일 1,500회 (마케터 1인 기준 충분)
**키 분실 시**: 위 페이지에서 기존 키 삭제 → 재발급 → 대시보드에 재입력
**보안 정책**: 평문 임베드 금지 (v5.2 Stage 0 보안 핫픽스로 기존 공용 키 회수 완료)

---

## 진입점 (Entry Points)
| URL | 설명 | 상태 |
|-----|------|------|
| `index.html` | **홈페이지**: 컴투스 브랜드 디자인, 워크플로우 안내, 소재 분석/군집화 진입 | ✅ 완성 |
| `step1_integrated.html` | **소재 분석**(메인): 4지표 Rank 점수 계산 + 피로도 분석 + 성과 보고서 + 5차원 캐노니컬 필터 | ✅ 완성 |
| `live_dashboard.html` | **라이브 대시보드**: 백엔드 nightly 산출 `public/data/{title}.json` 자동 로드 | ✅ 완성 |
| `pre_eval.html` | **소재 사전 평가**: 집행 전 소재 이미지 기반 사전 진단(Gemini Vision) | ✅ 완성 |
| `step2_column_selector.html` | **군집화 ①**: 태그 컬럼 선택 & 가중치 → 군집화 모드 설정 | ✅ 완성 |
| `step2_clustering.html` | **군집화 ②**: 하이브리드 군집화 + 결과 시각화 + 인사이트 | ✅ 완성 |

> 전 페이지에 외부 공유용 접근 고지 게이트(`js/access-gate.js`) 적용. `pipeline.html`·`fatigue_analysis.html`·`test_step1_scoring.html`(구 레거시 HTML)은 제거됨 — 현재 파이프라인은 아래 백엔드(`pipeline/`)로 대체.

---

## 백엔드 nightly 파이프라인 (`pipeline/`, Python)

매일 밤 Windows 작업 스케줄러(`CLOOP-Nightly`, 13:00)가 `scripts/nightly.ps1` → `pipeline/main.py`를 실행해 타이틀별 소재 데이터를 자동 산출·커밋한다.

- **소재 스캔** — `js/titles.json`의 타이틀별 `_pipeline_creatives_root`(GDrive)에서 BNR/VID 소재 스캔.
- **성과 수집** — 커넥터(`pipeline/sources/`): Google Ads(GAQL 조회), MMP(Airbridge/AppsFlyer, 非Google 매체). 전부 **READ 전용**. 소재↔캠페인↔매체 귀속은 `pipeline/campaign_canonical.py`(매체 축은 이름파싱+MMP channel 정규화, `pipeline/media_normalize.py`).
- **소재 태깅** — `pipeline/tagger.py`가 Gemini Files API로 소재 파일을 구조화 태그(`pipeline/schemas.py`의 `CreativeTag`: hooking/USP/visual/strengths/test_ideas 등)로 분석. 장르·게임 컨텍스트는 `pipeline/game_context/*.md` 주입.
- **점수·품질 산출** — `pipeline/scoring.py`(Google Ads 4지표 Rank 점수, 대시보드 로직과 동일), `pipeline/mmp_metrics.py`(MMP 품질 4지표). KPI 백분위(CTR/CVR/CPA)도 계산.
- **산출·배포** — `public/data/{title}.json` 저장 → git 커밋·push → GitHub Pages가 라이브 대시보드로 서빙. 실행 로그 `logs/`, 결과 메일 알림(`pipeline/notify.py`).
- **캐시** — `cache/{title}_kpi.json`·`{title}_tags.json`(Gemini 태깅 캐시).

측정 기준·항목 상세: [`docs/measurement-reference.md`](docs/measurement-reference.md). 매체 축 정규화 설계: [`docs/mmp-channel-media-design.md`](docs/mmp-channel-media-design.md).

---

## 🚀 빠른 시작 가이드 (`step1_integrated.html`)

### Step 1: 페이지 열기
브라우저에서 `step1_integrated.html` 파일을 엽니다.

### Step 2: CSV 업로드
1. **드래그 앤 드롭**: CSV 파일을 화면 상단 업로드 영역에 드래그
2. **파일 선택**: 업로드 영역을 클릭하여 파일 브라우저에서 선택
3. ✅ 업로드 완료 메시지와 데이터 요약 확인

### Step 3: 점수 계산
1. 📊 상단 네비게이션에서 **"점수 계산"** 버튼 클릭
2. (선택) 가중치 슬라이더 조정
3. (선택) 분석 기준(소재명/파일명), 캠페인, 날짜 범위 설정
4. **"📊 점수 계산 실행"** 버튼 클릭
5. 📋 분석 결과 섹션으로 자동 이동하여 결과 확인

### Step 4: 피로도 분석
1. 🔍 상단 네비게이션에서 **"피로도 분석"** 버튼 클릭
2. (선택) 기준/비교 기간 조정 (기본값: 자동 분할)
3. **"🔍 피로도 분석 실행"** 버튼 클릭
4. 📈 통계 섹션으로 자동 이동하여 결과 확인
5. 📉 차트 섹션에서 Top 10 순위 변동 시각화 확인

### Step 5: 결과 해석
- 🟢 **신선** (CPA ≤ -20%) → 예산 증액 (Scale-up)
- 🔵 **안정** (-20% < CPA ≤ 0%) → 현상 유지 (Maintain)
- 🟡 **경고** (0% < CPA ≤ 20%) → 모니터링 강화 (Watch)
- 🔴 **피로** (CPA > 20%) → 교체/리프레시 (Replace)

### 📌 문제 해결
**Q: CSV 파일이 업로드되지 않아요!**
- A1: **✅ v1.2에서 수정됨!** "Cannot read properties of undefined (reading 'length')" 오류 해결
- A2: 브라우저 콘솔(F12)을 열어 오류 메시지 확인
- A3: `js/pipeline-engine.js`와 `js/analysis-engine-v2.js` 파일이 같은 폴더에 있는지 확인
- A4: CSV 파일이 UTF-8 인코딩인지 확인
- A5: 파일 크기가 너무 크지 않은지 확인 (권장: 5MB 이하)
- A6: `test_step1_csv_upload.html`을 열어 자동 테스트 실행 (모든 단계가 ✅이어야 함)

**Q: 날짜 범위가 자동 설정되지 않아요!**
- A: CSV에 "일", "날짜", "일자", "date", "day" 등의 날짜 컬럼이 있는지 확인

**Q: 캠페인 필터가 비어있어요!**
- A: CSV에 "캠페인", "campaign" 등의 캠페인 컬럼이 있는지 확인

---

## 📌 최신 업데이트 (2026-08-07, 사용안내서 v5.10) — 매체 축 정규화 · 라이브 파이프라인 안정화

> 상세 변경 이력은 `사용안내서_인쇄용.html`의 버전 이력(v5.5~v5.10)을 정본으로 참조. 아래는 요약.

- **매체 축 정규화** (v5.10) — 이름파싱 토큰(FB/ML/TT)과 MMP channel(Airbridge `facebook.business`·AppsFlyer `facebook ads`)의 상이 표기를 단일 표준 매체명(Meta/TikTok/Kakao…)으로 수렴. 이름파싱 우선 + MMP 폴백, 충돌 시 검수 플래그, 소재 대표 매체 `media_canonical` 산출 (`pipeline/media_normalize.py`, `pipeline/campaign_canonical.py`).
- **캠페인명 media 파싱 개선** — ua_type 앵커 기반으로 변경, `agency_executor` 접두 누락 시 오파싱 해소.
- **MMP 기준 레이어 재설계** (v5.7) — 분석 기준을 MMP로 전환 시 전환=캠페인 유형별 합산(NU-Pre 등록 + NU D1 잔존), 총점=MMP 품질점수(4지표 rank), 성과 백분위도 MMP 기준.
- **레이어 우선 분석** (v5.8) — 타이틀 → 분석 레이어(Google Ads/MMP 토글) → 분석 순서로 데이터 단위 확정.
- **성과 보고서 개편 + 피로도 제외 추천** (v5.9) — 콘텐츠 이해 기반 인사이트·위닝 플레이북·저효율 진단·캠페인 제외 후보.
- **외부 공유 게이트** — 전 페이지 접근 고지 + 제우스 외 타이틀 UI 숨김(`js/access-gate.js`, `js/titles.json` `_ui_hidden`).

---

## 📜 변경 이력 (아카이브)

2026-04 ~ 2026-06의 상세 변경 이력은 [`docs/CHANGELOG-archive.md`](docs/CHANGELOG-archive.md)로 분리했습니다. 최신 요약은 위 "최신 업데이트" 및 `사용안내서_인쇄용.html` 버전 이력을 참조하세요.

---

## 구현된 기능 (페이지별)

### 🏠 홈 (`index.html`)
- 랜딩 페이지 — Hero, 워크플로우 안내, 소재 분석/군집화 진입 버튼 (분석 기능은 아래 페이지가 담당)

### 📊 소재 분석 (`step1_integrated.html`, 메인)
- **점수 계산** — 4지표(전환수·CPA·IPM·ROAS) Rank 기반 Total Score + 5등급, 가중치 슬라이더·프리셋
- **필터** — 소재 유형(BNR/VID)·캠페인·날짜·집계 기준 + **5차원 캐노니컬 필터**(캠페인 목적/국가/OS/매체/상품)
- **분석 결과** — 스코어 카드 5종, 유형별 요약표, 상세 테이블(정렬·선택·일별 추이 모달)
- **성과 보고서** — 콘텐츠 이해 기반 AI 인사이트 5섹션 + 위닝 플레이북 + 저효율 진단 + 캠페인 제외 후보
- **피로도·제외 추천** — 기간 비교 CPA 변화율 4상태 + 제외 추천, CSV 내보내기
- **레이어 토글** — Google Ads ↔ MMP 품질 기준 전환(총점·백분위 재산출)
- **HTML 추출** — 결과를 정적 HTML로 다운로드(사외 공유 안전, AI 인사이트 제외)

### 📡 라이브 대시보드 (`live_dashboard.html`)
- 백엔드 nightly 산출 `public/data/{title}.json` 자동 로드 — 업로드 없이 최신 성과 확인

### 🔬 소재 사전 평가 (`pre_eval.html`)
- 집행 전 소재 이미지 기반 사전 진단(Gemini Vision)

### 🧩 군집화 (`step2_column_selector.html` → `step2_clustering.html`)
- 태그 컬럼·가중치 설정 → 하이브리드 군집화 → 군집 등급(S/A/B/C·D)·전략(Scale-up/Pivot/Exit)·시각화

### 🤖 Gemini AI 인사이트 (`js/gemini-api.js`, 전 페이지 공통)
- 무료/유료 플랜 분기, winning/losing 분리, 피로도 riseReason, 군집 위닝 로직 — 개인 API 키(localStorage)

### 🔒 외부 공유 게이트 (`js/access-gate.js`)
- 전 페이지 접근 고지 + 타이틀 UI 숨김(`js/titles.json` `_ui_hidden`)

---

## 파일 구조
```
index.html                 홈 (진입점)
step1_integrated.html      소재 분석 (메인 — pipeline-engine 등 인라인 포함, CSP 회피)
live_dashboard.html        라이브 대시보드 (public/data JSON 자동 로드)
pre_eval.html              소재 사전 평가 (Gemini Vision)
step2_column_selector.html 군집화 ① 컬럼·가중치 설정
step2_clustering.html      군집화 ② 실행·시각화
사용안내서_인쇄용.html      사용 안내서 (인쇄용)
js/
  gemini-api.js            Gemini 프롬프트·파서·렌더러
  data-source.js           titles.json / public/data JSON 로드
  canonical-filter.js      5차원 캐노니컬 필터 (캠페인 목적/국가/OS/매체/상품)
  access-gate.js           외부 공유용 접근 고지 게이트
  layer-metrics.js         Google Ads / MMP 레이어 지표
  live-dashboard.js        라이브 대시보드 로직
  pipeline-engine.js       CSV 파싱·정규화·검증 (원본, step1에 인라인 복사됨)
  titles.json              타이틀 등록 + 파이프라인 설정
  titles_overrides.json    소재명 별칭 매핑
css/gemini-ui.css          AI 인사이트 카드 스타일
pipeline/                  백엔드 nightly 파이프라인 (Python)
  main.py · sources/(google_ads·airbridge·appsflyer) · scoring.py
  mmp_metrics.py · tagger.py · campaign_canonical.py · media_normalize.py
  schemas.py · notify.py · game_context/*.md
public/data/{title}.json   파이프라인 산출물 (대시보드가 로드)
scripts/nightly.ps1        nightly 실행 스크립트 (작업 스케줄러 CLOOP-Nightly)
docs/                      설계·레퍼런스 문서 (measurement-reference 등)
```

---

## 데이터 모델

### 소재 (Creative)
| 필드 | 타입 | 설명 |
|------|------|------|
| name | string | 소재명 (기준 키) |
| type | 'BNR'/'VID' | 소재 유형 |
| score | number | Total Score (0~100) |
| rank | number | 소재 순위 |
| grade | string | 성과 등급 (최우수/우수/양호/보통/개선필요) |
| cluster | string | 소속 군집명 |
| fileCount | number | 파일 수 |
| tags | string[] | 태그 목록 (일반 태그 + [MI] 인사이트 키워드) |
| link | string | 이미지 URL |

### CSV 업로드 컬럼 구조

**필수 컬럼** (자동 정규화 지원):
- `소재명` ← 파일명 (BNR/VID) 또는 소재명 (TXT)
- `유형` ← 유형 (BNR/VID) 또는 유형
- `전환` ← 전환, conversions, installs
- `비용` ← 비용, cost, spend
- `노출수` ← 노출수, impressions
- `클릭수` (선택) ← 클릭수, clicks

**태그 컬럼** (자동 탐지):
- `hooking_strategy`, `visual_technique`, `emotion`, `gameplay` 등
- CSV 헤더에서 자동으로 태그 컬럼과 메타 컬럼 분리

**인사이트 컬럼** (자동 탐지):
- `marketer_insight`, `마케터 인사이트`, `insight_memo` 등
- 자유 텍스트 필드에서 키워드 추출 → [MI] 태그 변환

---

## 기술 스택
- HTML5 / CSS3 / Vanilla JavaScript (ES6+)
- Chart.js 4.4.0 (CDN)
- Font Awesome 6.4.0 (CDN)
- Google Fonts – Pretendard
- localStorage (데이터 영구 저장)

---

## 미구현 / 향후 개선 사항

### 분석 기능
- [ ] **Jaccard 유사도 기반 동적 군집화**: 현재 Union-Find 알고리즘을 Jaccard 유사도 기반 클러스터링으로 교체
- [ ] **BNR/VID 다차원 분석**: 군집별 배너/비디오 성과 차이 및 최적화 포인트 제시
- [ ] **성과 견인 핵심 태그 식별**: 상위 스코어 군집에서 공통 발견되는 결정적 태그 자동 추출
- [x] ✅ **소재 피로도 분석**: 기간별 순위 변동 추적 및 피로도 상태 판정 → `fatigue_analysis.html` 완성
- [ ] 다국가/매체별 성과 필터 (KR/EN/JP)
- [ ] 캠페인별 분류 탭
- [x] ✅ 날짜 범위 필터 (Step 1 및 피로도 분석에서 구현 완료)
- [ ] 소재별 시계열 성과 트렌드

### 데이터 연동
- [ ] 서버사이드 데이터 연동 (REST API)
- [ ] Google Ads / Facebook Ads API 직접 연동
- [ ] 실시간 성과 데이터 자동 업데이트

### 리포트 & 내보내기
- [ ] PDF/PPT 자동 내보내기
- [ ] 군집별 인사이트 리포트 생성
- [ ] 이메일 자동 발송 (주간/월간 리포트)

---

## 배포
**Publish 탭**에서 원클릭 배포 후 에이전시에 URL 공유 가능.
