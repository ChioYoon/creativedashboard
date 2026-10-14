# nightly 파이프라인 PC 이전 체크리스트

현재 PC 에서 돌고 있는 nightly(작업 스케줄러 `CLOOP-Nightly`, 매일 13:00)를 **상시 가동 PC** 로 옮기는 절차.
위에서부터 순서대로 체크하면 된다. 명령은 모두 **PowerShell** 에서 실행.

- 기존 PC = 지금 쓰는 PC, 새 PC = 옮겨갈 PC
- 예상 소요: 1~2시간 (설치 대기 포함)
- **비밀 파일(`.env`, `.secrets\`)은 USB 등 오프라인으로 옮기고, 메일·메신저·드라이브에 올리지 않는다**

---

## 0. 옮기기 전 (기존 PC)

- [ ] 마지막 nightly 가 정상이었는지 확인 — 최신 로그 끝부분에 `ERROR` 가 없으면 OK
  ```powershell
  Get-ChildItem C:\claude\cloop_dashboard\logs\nightly_*.log | Sort-Object LastWriteTime | Select-Object -Last 1 | Get-Content -Tail 30
  ```
- [ ] USB 에 아래 항목 복사 (프로젝트 폴더 `C:\claude\cloop_dashboard\` 기준)

  | 대상 | 내용 | 없으면 |
  |---|---|---|
  | `.env` | Gemini·Airbridge·AppsFlyer·Sheets 등 모든 설정·토큰 | 파이프라인 전체 동작 안 함 |
  | `.secrets\` 폴더 통째 | `google_ads.yaml`(Google Ads 인증), `sheets_sa.json`(시트 업로드 키) | KPI 수집·시트 업로드 실패 |
  | `cache\` 폴더 통째 (약 20MB) | Gemini 태깅 결과 캐시 | 동작은 하지만 첫날 전체 재태깅 → 시간·Gemini 비용 증가 |
  | (선택) `logs\` | 과거 실행 로그 | 이력만 없어짐 |

## 1. 새 PC 기본 설치

- [ ] **Python 3.14** 설치 — https://www.python.org/downloads/ (설치 첫 화면에서 "Add python.exe to PATH" 체크)
- [ ] **Git for Windows** 설치 — https://git-scm.com/download/win (기본 옵션 그대로. "Git Credential Manager" 포함)
- [ ] **Google Drive for desktop** 설치 후 회사 계정(chioyoon@com2us.com)으로 로그인
  - [ ] 드라이브가 **`G:` 드라이브**로 잡히는지 확인 — 소재·브리프 폴더 경로가 `G:\공유 드라이브\...` 로 설정돼 있음
  - [ ] 탐색기에서 아래 폴더가 열리는지 확인
    - `G:\공유 드라이브\[ZEUS_MKT] 컴투스 X 인크로스\UA\4. 크리에이티브\2. UA 소재`
    - `G:\공유 드라이브\[도원암귀_MKT] 외부 드라이브\1. 소재\0. 제작 완료 소재 (MKT Asset)\0. UA Asset`
    - `G:\공유 드라이브\[UA] N마케팅실\AX_Knowledge\` (브리프 폴더)
  - G: 가 아닌 다른 문자로 잡히면: Drive for desktop 설정 → 환경설정 → 드라이브 문자 `G` 로 변경
- [ ] **절전 끄기** — 설정 → 시스템 → 전원 → "화면 및 절전"에서 절전 모드 **안 함** (화면 끄기는 괜찮음)

## 2. 프로젝트 내려받기

- [ ] 폴더 만들고 저장소 복제 (첫 실행 시 GitHub 로그인 창이 뜨면 **ChioYoon** 계정으로 로그인)
  ```powershell
  New-Item -ItemType Directory -Force C:\claude | Out-Null
  cd C:\claude
  git clone https://github.com/ChioYoon/creativedashboard.git cloop_dashboard
  cd C:\claude\cloop_dashboard
  ```
  > 경로는 기존과 같게(`C:\claude\cloop_dashboard`) 두는 것을 권장 — 문서·설정이 이 경로 기준
- [ ] USB 의 `.env`, `.secrets\`, `cache\` 를 `C:\claude\cloop_dashboard\` 안에 붙여넣기
- [ ] git 사용자 설정·인증 확인
  ```powershell
  .\scripts\setup-git.ps1
  ```

## 3. 파이썬 환경 설치

- [ ] 가상환경 생성 + 패키지 설치 (`requirements.txt` 전부, 수 분 소요)
  ```powershell
  .\scripts\setup.ps1
  ```
  마지막에 `[OK]` 가 나오면 성공. `.env` 는 이미 붙여넣었으니 덮어쓰지 않는다.

## 4. 연결 점검 (하나씩)

- [ ] Google Ads 인증
  ```powershell
  .\scripts\setup-google-ads.ps1 -Healthcheck
  ```
- [ ] Google Sheets 업로드 (실제 업로드 없이 행·셀 수만 계산)
  ```powershell
  .\.venv\Scripts\python.exe -m pipeline.sheets_export --dry-run
  ```
  `타이틀=['zeus', 'tougenanki'] ... 셀=...` 이 나오면 OK
- [ ] 테스트 전체
  ```powershell
  .\.venv\Scripts\python.exe -m pytest -q
  ```
  `passed` 만 나오고 `failed` 가 없으면 OK

## 5. 스케줄 옮기기 — ⚠️ 순서 중요

두 PC 가 동시에 돌면 같은 저장소에 push 가 겹친다. **기존 PC 를 먼저 끄고** 새 PC 를 켠다.

- [ ] **기존 PC** 에서 작업 해제
  ```powershell
  cd C:\claude\cloop_dashboard
  .\scripts\register-task.ps1 -Unregister
  ```
- [ ] **새 PC** 에서 작업 등록 (기본 13:00)
  ```powershell
  .\scripts\register-task.ps1
  ```
- [ ] 새 PC 에서 **지금 한 번 실행**해 검증 (전체 1시간 안팎)
  ```powershell
  Start-ScheduledTask -TaskName 'CLOOP-Nightly'
  ```
  끝난 뒤 확인:
  - [ ] 최신 `logs\nightly_*.log` 끝부분에 `ERROR` 없음, `Push done` 있음
  - [ ] 라이브 대시보드가 오늘 날짜 데이터로 갱신됨
  - [ ] 구글 시트 `raw_creative` 의 `loaded_at` 열이 방금 시각(UTC)으로 바뀜

> 작업은 **로그인 상태에서만** 실행된다(`LogonType Interactive`). 새 PC 는 로그아웃하지 말고 **잠금(Win+L)** 만 해 둘 것.
> 재부팅 후에는 한 번 로그인해야 다시 돈다. 13:00 에 꺼져 있었으면 켜진 직후 자동 실행(StartWhenAvailable).

## 6. 마무리

- [ ] 다음날 13:00 자동 실행 결과를 한 번 더 확인 (5단계의 확인 3가지)
- [ ] 기존 PC 의 `.env`·`.secrets\` 는 새 PC 정상 확인 후 삭제(또는 안전한 곳에 보관). USB 사본도 삭제
- [ ] 문제가 생기면: 새 PC 작업은 `-Unregister`, 기존 PC 에서 `.\scripts\register-task.ps1` 로 다시 등록하면 원상복구

## 참고 — 새 PC 에서 다시 발급할 필요 없는 것

- Google Ads 인증(`google_ads.yaml`)·Sheets 키(`sheets_sa.json`)·각종 API 토큰(`.env`)은 **파일 복사만으로 그대로 동작** (PC 에 묶여 있지 않음)
- 다시 해야 하는 것은 GitHub 로그인(2단계)과 Google Drive 로그인(1단계)뿐

관련 문서: [Sheets 업로드 셋업](sheets-export-setup.md) · `CLAUDE.md` §11 nightly 운영 메모
