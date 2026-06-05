# 🚀 Stage 2 자동 태깅 파이프라인 — 초보자용 셋업 가이드

> **대상 사용자**: Python 명령어를 처음 사용하는 R팀 담당자
> **소요 시간**: 최초 15분 (다음번부터 1분 이내 실행 가능)
> **사전 준비**: Python 3.11+ 설치 완료 / Google Drive 데스크톱 앱 설치 완료

---

## 📋 한눈에 보는 흐름

```
[Google Drive 폴더]                 [Python 파이프라인]            [대시보드]
G:\공유 드라이브\...\01. BNR\선론칭   ──►  pipeline/main.py  ──►   public/data/pepp-us.json
                                              │                       │
                                              │ Gemini에 영상/이미지 전송  │
                                              │ 4-compact taxonomy 태깅 │
                                              │ 결과 JSON 저장          │
                                                                      ▼
                                            step1_integrated.html?title=pepp-us
                                              (브라우저에서 자동 로드)
```

---

## 1️⃣ 신규 Gemini API 키 발급 (5분, 1회만)

이미 회수 안내한 노출 키는 **사용 금지**입니다. 새로 발급합니다.

1. https://aistudio.google.com/apikey 접속
2. 본인 Google 계정으로 로그인
3. 우측 상단 **"Create API key"** 클릭
4. 키 이름: `cloop-backend-pepp-us` (구분용)
5. 발급된 키(`AIza...`로 시작, 39자)를 **메모장에 임시 복사**
   - ⚠️ 절대 채팅창·공개 문서·코드 파일에 직접 붙여넣지 마세요.

---

## 2️⃣ 원클릭 셋업 (PowerShell, 5분, 1회만)

### 2-1. PowerShell 열기
- 작업 표시줄 검색 → `PowerShell` → 엔터
- 또는 `Win + X` → `Windows PowerShell` 선택

### 2-2. 프로젝트 폴더로 이동
```powershell
cd C:\claude\cloop_dashboard
```

### 2-3. 셋업 스크립트 실행
```powershell
.\scripts\setup.ps1
```

**처음 실행 시 권한 오류가 나면** (`이 시스템에서 스크립트를 실행할 수 없으므로...`):

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
# Y 입력 후 엔터
.\scripts\setup.ps1
```

스크립트가 자동으로 수행:
- ✅ Python 3.11+ 확인
- ✅ `.venv` 가상환경 생성
- ✅ 의존성 설치 (`google-genai`, `pydantic`, `python-dotenv`, `tqdm`)
- ✅ `.env` 환경 변수 파일 생성
- ✅ dry-run 검증 (Gemini 호출 없이 폴더 스캔만 확인)

---

## 3️⃣ `.env` 파일에 키 입력 (2분, 1회만)

### 3-1. 메모장으로 `.env` 열기

PowerShell에서:
```powershell
notepad .env
```

### 3-2. `GEMINI_API_KEY=` 줄에 키 붙여넣기

기본 상태:
```
GEMINI_API_KEY=여기에_AIza로_시작하는_새로운_키_붙여넣기
```

수정 후:
```
GEMINI_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

> ⚠️ `=` 양옆에 공백 없이, 따옴표 없이 그대로 붙여넣으세요.

### 3-3. 저장 후 메모장 닫기 (`Ctrl + S` → `Alt + F4`)

> 🔒 `.env` 파일은 `.gitignore` 에 등록되어 있어 GitHub에 절대 커밋되지 않습니다.

---

## 4️⃣ 첫 검증 (3개만 태깅, 약 1분)

```powershell
.\.venv\Scripts\Activate.ps1
python -m pipeline.main --title pepp-us --limit 3
```

성공하면 다음과 같이 출력됩니다:

```
🎯 타이틀:        pepp-us
📂 소재 루트:     G:\공유 드라이브\[펩 히어로즈] R마케팅실\01. UA\01. UA 소재
🗂  차수 필터:     선론칭
🎨 유형 필터:     BNR / VID
...
🔍 1) 로컬 폴더 스캔 중...
   → 소재 폴더 20개 (BNR=19개, VID=1개) · 총 미디어 파일 80개
   → --limit 3 적용: 3개로 축소

🚀 2) Gemini 태깅 시작 (프롬프트: v1.0-2026.05.29) ...
태깅: 100%|███████████████| 3/3 [00:42<00:00, 14.2s/소재]

✅ 완료 (42.1초)
   캐시 히트:     0
   Gemini 호출:   3
   실패:          0
   산출 파일:     public\data\pepp-us.json
   대시보드 URL:  step1_integrated.html?title=pepp-us
```

---

## 5️⃣ 대시보드에서 확인

브라우저에서 다음 중 하나로 접속:

- **로컬 파일 열기**: `step1_integrated.html` 더블클릭 후 우상단 드롭다운에서 "Pepp Heroes (US)" 선택
  - 단, 로컬 파일에서는 `fetch()` 보안 정책으로 JSON 로드가 막힐 수 있음
  - 그럴 땐 ⬇ 로컬 서버 실행

- **로컬 서버로 열기** (권장):
  ```powershell
  python -m http.server 8080
  ```
  브라우저에서 http://localhost:8080/step1_integrated.html?title=pepp-us 접속

→ 3개 소재가 점수 계산·AI 인사이트와 함께 표시됩니다.

---

## 6️⃣ 전체 태깅 실행

검증 성공 후 `--limit 3` 옵션을 제거하고 전체 실행:

```powershell
python -m pipeline.main --title pepp-us
```

- 20개 소재 × 약 14초 = 약 **5분** 소요
- 실행 중 진행률 바 표시
- 중단(Ctrl+C)해도 캐시는 부분 저장되어 다음 실행 시 이어서 진행

---

## 🔁 일상 운영 (2번째 실행부터)

매번 위 1~3번을 반복할 필요 없습니다. PowerShell에서:

```powershell
cd C:\claude\cloop_dashboard
.\.venv\Scripts\Activate.ps1
python -m pipeline.main --title pepp-us
```

- 캐시 덕분에 **변경된 소재만 재태깅** (대부분 1분 이내 완료)
- 새 소재를 GDrive에 추가하면 → 다음 실행 시 자동 발견

---

## 🛠️ 자주 쓰는 옵션

| 옵션 | 효과 | 예시 |
|---|---|---|
| `--phase` | 차수 한정 | `--phase 사전예약 --phase 선론칭` |
| `--type` | 유형 한정 | `--type BNR` 만 / `--type VID` 만 |
| `--limit N` | 최대 N개 소재만 | `--limit 5` |
| `--no-cache` | 캐시 무시, 강제 재태깅 | `--no-cache` |
| `--dry-run` | Gemini 호출 없이 스캔만 | `--dry-run` |

---

## ❓ 문제 해결

### Q. "GEMINI_API_KEY 가 비어있습니다" 오류
→ `.env` 파일 안에 `GEMINI_API_KEY=AIza...` 라인이 있고 값이 채워졌는지 확인.

### Q. "소재 루트 폴더가 없습니다" 오류
→ `.env` 의 `CLOOP_CREATIVES_ROOT=` 경로가 본인 PC에서 접근 가능한지 확인.
   PowerShell에서 다음 명령으로 검증:
```powershell
Test-Path "G:\공유 드라이브\[펩 히어로즈] R마케팅실\01. UA\01. UA 소재"
# → True 가 나와야 정상
```

### Q. "429 RESOURCE_EXHAUSTED" 오류
→ Gemini 무료 한도(분당 15회) 초과. 1분 대기 후 재실행하면 캐시된 부분은 건너뜀.

### Q. 영상이 너무 길어 시간 초과
→ Files API 처리 한도는 영상 길이에 따라 30초~3분. `pipeline/tagger.py` 의 `POLL_TIMEOUT_SEC = 180` 값을 늘려 재시도.

### Q. 다른 타이틀(스타시드 등) 추가하려면?
→ `js/titles.json` 에 새 타이틀 메타 추가 + `python -m pipeline.main --title starseed-jp --root "..."` 실행.

---

## 📁 산출물 구조

```
cloop_dashboard/
├── pipeline/                  # Python 모듈
│   ├── main.py                # CLI 진입점 (--title / --all-titles)
│   ├── schemas.py             # Pydantic 4-compact taxonomy
│   ├── scanner.py             # 로컬 폴더 스캔
│   ├── tagger.py              # Gemini API 호출 (재시도 + 폴백)
│   ├── cache.py               # SHA-256 캐시
│   └── notify.py              # SMTP 이메일 알림 (Stage 4)
├── scripts/
│   ├── setup.ps1              # 초기 venv + pip 셋업
│   ├── setup-git.ps1          # Git/PAT 인증 셋업 (Stage 4)
│   ├── setup-email.ps1        # SMTP 셋업 (Stage 4)
│   ├── nightly.ps1            # Task Scheduler 진입점 (Stage 4)
│   └── register-task.ps1      # Task Scheduler 등록 (Stage 4)
├── public/data/               # 대시보드가 자동 로드, GitHub Pages 호스팅
│   ├── pepp-us.json           # ★ 태깅 결과 (대시보드에 표시됨)
│   └── starseed-jp.json       # (다른 타이틀 추가 시)
├── cache/                     # 재호출 방지 캐시 (git 미커밋)
├── logs/                      # 야간 배치 로그 (30일 자동 회전, git 미커밋)
├── .env                       # ★ 본인 키 (git 미커밋)
└── .venv/                     # Python 가상환경 (git 미커밋)
```

---

## 🌙 Stage 4 — Nightly 자동화 셋업

R팀 담당자가 GDrive에 신규 소재를 올리면, 매일 **13:00 KST**에 자동으로:
1. 태깅 파이프라인 실행
2. GitHub 레포에 결과 commit & push
3. GitHub Pages 대시보드 자동 갱신
4. 결과 이메일 발송

### 사전 조건

- Stage 2 완료 (Python venv, .env, 첫 태깅 검증)
- Git for Windows 설치
- GitHub Personal Access Token (PAT) 발급 권한
- Gmail 또는 Office 365 이메일 계정

### 셋업 순서 (1회만)

#### 1️⃣ Git 인증 셋업 (5분)
```powershell
.\scripts\setup-git.ps1
```
- Git 설치 확인
- user.name / user.email 설정
- GitHub PAT 발급 안내
- Push 권한 검증

#### 2️⃣ 이메일 알림 셋업 (3분)
```powershell
.\scripts\setup-email.ps1
```
- Gmail 또는 Office 365 선택
- 자격증명 입력 (.env 자동 갱신)
- 테스트 메일 발송 검증

#### 3️⃣ 야간 배치 수동 테스트 (1분)
```powershell
# Dry-run: 파이프라인만 실행, git push 안 함
.\scripts\nightly.ps1 -DryRun

# 정상 동작 확인 후 실제 실행
.\scripts\nightly.ps1
```

#### 4️⃣ Windows Task Scheduler 등록 (1분)
```powershell
.\scripts\register-task.ps1                     # 기본 13:00 KST
.\scripts\register-task.ps1 -Time '08:30'       # 시간 변경
```

### 일상 운영

자동 실행이 등록되면 더 이상 수동 작업 불필요. 매일 13:00에:

- `logs/nightly_YYYYMMDD_HHMMSS.log` 생성
- 신규 소재가 있으면 `public/data/*.json` 갱신
- 변경 사항을 GitHub에 push (`auto: nightly tagging YYYY-MM-DD`)
- `NOTIFY_TO` 이메일로 결과 발송

### 다중 타이틀 추가

`js/titles.json` 에 새 타이틀 항목 추가:
```json
{
  "id": "starseed-jp",
  "name": "스타시드: 아스니아 트리거 (JP)",
  "json_url": "public/data/starseed-jp.json",
  "description": "...",
  "_pipeline_creatives_root": "G:\\공유 드라이브\\[스타시드] R마케팅실\\01. UA\\01. UA 소재",
  "_pipeline_phases": ["선론칭"],
  "_pipeline_types": ["BNR", "VID"],
  "_pipeline_enabled": true
}
```

→ 다음 nightly 실행 시 자동 포함됨.

### 자동 폴백 (quota 한도)

`gemini-2.5-flash`가 일 한도(무료 20회) 도달 시 자동으로 `gemini-2.5-flash-lite`로 전환하여 계속 진행. 두 모델 모두 한도 도달 시 알림에 `daily_quota_exhausted` 플래그 포함.

### 트러블슈팅

**Q. 이메일이 안 옴 (Gmail)**
- 앱 비밀번호 16자 정확히 입력 (공백 제거됨, OK)
- 2단계 인증 활성화 필수
- Gmail 보낸편지함 확인 → 안 보이면 SMTP 인증 실패
- 폴백 로그 확인: `Get-ChildItem logs\nightly_*.log | Sort -Desc | Select -First 1`

**Q. 이메일이 안 옴 (Office 365)**
- 회사 IT가 SMTP AUTH 차단했을 가능성 → Gmail로 전환 권장
- 또는 IT에 `smtp.office365.com:587 STARTTLS` 허용 요청

**Q. Git push 실패**
- PAT 만료 → 새로 발급 후 `setup-git.ps1` 재실행
- 또는 Windows 자격증명 관리자에서 `github.com` 항목 삭제 → 다음 push 시 재인증

**Q. Task Scheduler 실행 안 됨**
```powershell
Get-ScheduledTask -TaskName 'CLOOP-Nightly' | Get-ScheduledTaskInfo
```
- `LastRunResult`가 0이 아니면 실패 → 로그 확인
- `NextRunTime`이 과거면 정상, 미래면 정상 대기 중
- 즉시 실행 테스트: `Start-ScheduledTask -TaskName 'CLOOP-Nightly'`

**Q. PC가 꺼져 있어서 실행 안 됨**
- `StartWhenAvailable` 옵션으로 다음 ON 시점에 catch-up 실행됨
- 만약 24시간+ 꺼져 있었다면 다음 정시 실행으로 처리

**Q. 등록 해제**
```powershell
.\scripts\register-task.ps1 -Unregister
```
