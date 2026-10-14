# Google Sheets 자동 업로드 셋업 (BI 포털 연동)

매일 nightly(13:00) 파이프라인이 끝나면 `pipeline/sheets_export.py` 가 소재 데이터를 지정한 구글 시트에 올린다.
데이터전략실 BI 포털은 이 시트를 불러와 쓴다.

- 대상 타이틀: `js/titles.json` 에서 `_pipeline_enabled=true` 인 타이틀(현재 zeus·tougenanki). 모든 타이틀이 한 시트에 들어가고 `title_id` 컬럼으로 구분됨
- 갱신 방식: **매일 전체 교체**(JSON 이 이미 전체 기간 누적본이라 중복이 생기지 않음)
- 실패해도 대시보드·git push 에는 영향 없음(로그에 WARN 만 남음)
- 꺼져 있는 것이 기본값 — `.env` 에서 `SHEETS_EXPORT_ENABLED=1` 로 바꿔야 동작

---

## 1. 서비스 계정 키 발급 (최초 1회)

서비스 계정은 "사람 없이 프로그램이 쓰는 구글 계정"이다. 비밀번호 대신 JSON 키 파일로 로그인한다.

1. https://console.cloud.google.com 접속(회사 구글 계정) → 상단에서 프로젝트 선택
   (Google Ads API 용으로 이미 쓰는 프로젝트를 그대로 써도 됨)
2. 왼쪽 메뉴 **API 및 서비스 → 라이브러리** → `Google Sheets API` 검색 → **사용**
3. **IAM 및 관리자 → 서비스 계정 → + 서비스 계정 만들기**
   - 이름: `cloop-sheets` → **만들고 계속하기** → 역할은 **비워 두고** 완료
   (시트 접근 권한은 아래 2단계의 "공유"로만 준다. 프로젝트 역할 불필요)
4. 만든 서비스 계정 클릭 → **키** 탭 → **키 추가 → 새 키 만들기 → JSON** → 파일이 다운로드됨
5. 다운로드된 파일 이름을 `sheets_sa.json` 으로 바꿔 저장소의 `.secrets\` 폴더에 넣는다
   (`.secrets/` 는 git 에 올라가지 않음. **이 파일을 메일·메신저·드라이브에 올리지 말 것**)
6. 서비스 계정 이메일(`cloop-sheets@<프로젝트>.iam.gserviceaccount.com`)을 복사해 둔다
   (JSON 파일 안 `client_email` 값과 같음)

> 4단계에서 "키 생성이 조직 정책으로 차단됨"(`iam.disableServiceAccountKeyCreation`)이 뜨면
> 사내 GCP 관리자(IT/데이터전략실)에게 해당 프로젝트에 서비스 계정 키 발급 허용을 요청해야 한다.

## 2. 대상 시트 만들기·공유 (최초 1회)

1. 회사 계정 구글 드라이브에서 **빈 스프레드시트** 생성(이름 예: `raw_creative`. 이름·위치는 나중에 바꿔도 됨 — 코드는 시트 ID 로 찾음. 단 탭 이름은 바꾸지 말 것)
2. 오른쪽 위 **공유** → 1-6 의 서비스 계정 이메일 붙여넣기 → 권한 **편집자** → "이메일 알림" 체크 해제 → 공유
3. 데이터전략실/BI 포털 담당자 계정도 필요하면 **뷰어**로 공유
4. 시트 URL 을 복사해 둔다

> **공유 드라이브 주의**: 서비스 계정(`@...iam.gserviceaccount.com`)은 회사 외부 계정으로 취급된다.
> 공유 드라이브가 "멤버가 아닌 사용자 및 외부 공유 차단"이면 2-2 가 막힌다
> ("이 공유 드라이브의 설정으로 인해 … 외부로 공유할 수 없습니다").
> 이 경우 공유 드라이브 관리자에게 ① 서비스 계정을 드라이브 멤버(콘텐츠 관리자)로 추가하거나
> ② 외부 공유 허용을 요청한다. 불가하면 시트를 '내 드라이브'에 두고 팀 폴더엔 바로가기만 둔다.
> (현재 시트: `[MI] 내부 공유 / ★ 소재 대시… / ☆ RAW / raw_creative`, 서비스 계정
> `cloop-sheets@valid-reflector-321907.iam.gserviceaccount.com` — GCP 프로젝트 `My First Project`)

탭은 직접 만들 필요 없음 — 첫 업로드 때 자동 생성된다. 기본 탭(`시트1`)은 지워도 되고 남겨도 된다.

## 3. `.env` 설정

저장소 루트의 `.env` 에 아래를 추가(값은 본인 것으로):

```
SHEETS_EXPORT_ENABLED=1
SHEETS_SPREADSHEET_ID=https://docs.google.com/spreadsheets/d/xxxxxxxx/edit
SHEETS_CREDENTIALS=.secrets/sheets_sa.json
```

## 4. 동작 확인

저장소 폴더에서 PowerShell 로:

```powershell
# 업로드 없이 행·셀 수만 계산(키·네트워크 불필요)
.\.venv\Scripts\python.exe -m pipeline.sheets_export --dry-run

# 실제 업로드 1회
.\.venv\Scripts\python.exe -m pipeline.sheets_export
```

마지막 줄에 `업로드 완료 — https://docs.google.com/...` 가 나오면 성공. 이후는 nightly 가 매일 자동 실행.

자주 나오는 오류:

| 메시지 | 원인 | 조치 |
|---|---|---|
| `비활성 ... 스킵` | `.env` 값 누락 또는 키 파일 경로 틀림 | 3단계 확인, `.secrets\sheets_sa.json` 존재 확인 |
| `Sheets API 403` | 시트를 서비스 계정에 공유 안 함 / Sheets API 미사용 | 2-2, 1-2 확인 |
| `Sheets API 404` | 시트 URL/ID 오타 | `.env` 의 `SHEETS_SPREADSHEET_ID` 확인 |
| `JSON 로드 실패 — 업로드 중단` | 타이틀 JSON 이 없거나 손상 | 전날 시트가 그대로 유지됨. nightly 로그 확인 |

## 5. 시트 형식 (BI 포털 참고)

탭 4개, 1행 = 헤더(영문 컬럼명, 고정됨), 2행부터 데이터. 컬럼 정의는 `pipeline/bq_export.py` `TABLE_SPECS` 와 동일.

| 탭 | 한 행 단위 | 주요 컬럼 |
|---|---|---|
| `kpi_daily` | 소재 × 날짜 × 캠페인/광고그룹 (Google Ads) | date, creative_name, campaign_name, impressions, clicks, cost, conversions, conversions_value |
| `mmp_daily` | 소재 × 날짜 × 매체 채널 (Airbridge/AppsFlyer) | date, channel, creative_name, installs, retained_d1, revenue_d7, conversions |
| `creatives` | 소재 1개 (태그 스냅샷) | 소재명, 유형, theme_primary, hooking_strategy, art_style, cta_type … |
| `axis` | 분석 축(L/P 단계) 스냅샷 | stage, axis, status, ipm, cvr, roas7 |

- 날짜(`date`·`snapshot_date`)는 `YYYY-MM-DD` **텍스트**, `loaded_at` 은 UTC ISO 시각
- 값은 원문 그대로 저장(RAW) — `=` 로 시작하는 소재명도 수식으로 바뀌지 않음
- 여러 값 컬럼(`theme_secondary`·`theme_flags`)은 `, ` 로 이어 붙임
- 규모: 2026-10 기준 약 3.4만 행·55만 셀(시트 한도 1,000만 셀의 5%). 900만 셀을 넘으면 업로드를 중단하고 로그에 오류를 남긴다

## 6. PC 이전 시

새 PC 로 옮길 때 아래 두 가지만 추가로 챙기면 된다(패키지는 `pip install -r requirements.txt` 에 포함).

- `.secrets\sheets_sa.json` 파일 복사(USB 등 오프라인 수단 권장)
- `.env` 의 `SHEETS_*` 3줄 복사

옮긴 뒤 4단계 명령으로 한 번 확인.
