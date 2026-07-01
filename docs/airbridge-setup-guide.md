# Stage 7-A — Airbridge 토큰 설정 안내 (사용자 작업)

Airbridge(MMP) 연동을 켜기 위한 1회성 설정입니다. **코드 작업 없음** — 토큰 발급 + `.env` 기입 + 검증 명령 3개면 끝납니다. 소요 약 10분.

> 백엔드(Stage 7-B)는 이미 완성·머지됨. 이 설정만 하면 nightly 가 자동으로 MMP 품질지표를 채웁니다. 설정 전까지는 **에러 없이 깨끗하게 건너뜁니다**(skipped).

---

## 1단계 — API 토큰 발급 (Airbridge 대시보드)

1. Airbridge 대시보드 로그인 → 우측 상단 또는 좌측 메뉴 **[Settings] (설정)** 진입
2. **[Tokens] (토큰)** 메뉴 클릭
3. **API 토큰 생성** (읽기 권한이면 충분 — Reports API 조회용)
4. 생성된 토큰 문자열 복사 (한 번만 표시되니 안전한 곳에 보관)

## 2단계 — 앱 이름(app_name) 확인

- Airbridge 의 **앱 식별자**입니다. 대시보드 URL 또는 앱 설정에서 확인되는 앱 슬러그/이름.
- 보통 `pepp` 처럼 짧은 식별자입니다. 헷갈리면 Airbridge 담당자/대시보드 [Settings] > [App] 에서 "App Name" 확인.

## 3단계 — `.env` 파일에 기입

`C:\claude\cloop_dashboard\.env` 파일을 메모장으로 엽니다.
(없으면 `.env.example` 을 복사해 `.env` 로 이름 변경)

아래 3줄을 찾아 값 채우기:

```
AIRBRIDGE_API_TOKEN=여기에_복사한_토큰
AIRBRIDGE_APP_NAME=여기에_앱이름
AIRBRIDGE_EXCLUDE_CHANNELS=googleadwords,Google Ads
```

저장 후 닫기. (`.env` 는 git 에 안 올라가니 토큰 노출 걱정 없음)

## 4단계 — 검증 명령 3개 (PowerShell)

`C:\claude\cloop_dashboard` 에서 가상환경 활성화 후 순서대로:

```powershell
cd C:\claude\cloop_dashboard
.\.venv\Scripts\Activate.ps1

# ① 인증 OK 확인
python -m pipeline.mmp --healthcheck

# ② ★가장 중요★ — 소재 단위(ad_creative) 지원 검증
python -m pipeline.mmp --metadata-check

# ③ 실제 데이터 + 4지표 미리보기 (상위 10개 소재)
python -m pipeline.mmp --days 30 --limit 10
```

### ② metadata-check 결과 해석 (핵심)

```
actuals   : ad_creative ✅
revenue    : ad_creative ✅      ← 또는 "⚠️ 미지원"
retention  : ad_creative ✅      ← 또는 "⚠️ 미지원"
```

- **3개 다 ✅** → 4지표 전부 소재 단위로 나옵니다. 완벽.
- **revenue/retention 이 ⚠️ 미지원** → 그 지표만 소재 단위가 안 나오므로 **자동 생략**됩니다 (나머지 가용 지표로 분석 진행 — 합의된 정책). 이 경우 알려주시면 대안을 검토합니다.

### ③ 결과에서 확인할 것

- 소재별 **D1잔존·D1IPM·D1CPI·D7ROAS·D1Ret%** 표가 출력됩니다.
- **0행** 이면: pepp 가 해당 기간 非Google 매체 집행이 없었거나, 채널 필터/앱이름 문제. → 알려주세요.
- 표에 **Google Ads 가 섞여 보이면**: Airbridge 의 Google 채널 표기명이 `googleadwords`/`Google Ads` 와 다른 것 → 실제 표기명을 `AIRBRIDGE_EXCLUDE_CHANNELS` 에 추가.

## 5단계 — 완료

위 3개 명령이 정상이면 끝. 다음 nightly(매일 13:00) 부터 `public/data/pepp-us.json` 에 `mmp_*` 품질지표가 자동 채워지고, 7-C 대시보드 UI 가 그걸 표시합니다.

수동으로 즉시 반영하려면:
```powershell
python -m pipeline.main --title pepp-us
```

---

## 문제 발생 시 알려줄 정보

- `--healthcheck` 실패 → 토큰/앱이름 오타 또는 토큰 권한 부족
- `--metadata-check` 의 ✅/⚠️ 결과 (특히 revenue/retention)
- `--days 30 --limit 10` 출력 (0행인지, Google 섞였는지, 4지표 값이 그럴듯한지)

이 3가지를 캡처해 주시면 다음 단계를 정확히 잡겠습니다.

---

# 향후 타이틀 추가 (멀티 계정) — "제우스식" 📌

위 1~5단계는 **첫(기본) 타이틀** 설정입니다(현재 펩=`relicheros`, `.env`의 `AIRBRIDGE_API_TOKEN`/`AIRBRIDGE_APP_NAME` 사용). 두 번째부터의 타이틀은 보통 **자기 Airbridge 계정/토큰**을 써서 아래 방식으로 추가합니다. (2026-07-01 제우스 연동에서 확립)

## 핵심 규칙 (한눈에)

| | 토큰 | 앱 이름(subdomain) |
|---|---|---|
| **기본 타이틀(펩)** | `.env` `AIRBRIDGE_API_TOKEN` | `.env` `AIRBRIDGE_APP_NAME` |
| **추가 타이틀(제우스~)** | `.env` `AIRBRIDGE_API_TOKEN_<타이틀ID>` | `titles.json` `_pipeline_airbridge_app_name` |

- ⚠️ **기본 2줄(`AIRBRIDGE_API_TOKEN`/`AIRBRIDGE_APP_NAME`)은 절대 바꾸지 마세요** — 펩 전용입니다.
- 추가 타이틀 토큰은 **새 줄로 추가**(`_<ID>` 접미사), **앱 이름은 titles.json에**(`.env` 아님).

## 절차 (3단계)

### ① `.env`에 그 타이틀 토큰 추가
```
AIRBRIDGE_API_TOKEN_<타이틀ID>=<그 타이틀의 Airbridge 토큰>
```
- `<타이틀ID>` = `titles.json`의 `id`를 **대문자**로, `-`·공백은 `_`로 바꾼 것.
  - `zeus` → `AIRBRIDGE_API_TOKEN_ZEUS`
  - `starseed-jp` → `AIRBRIDGE_API_TOKEN_STARSEED_JP`
- 기본 `AIRBRIDGE_API_TOKEN`(펩)은 **그대로 두고**, 아래에 새 줄만 추가.

### ② `titles.json`(또는 등록부)에 앱·활성화 설정
해당 타이틀 항목에:
```json
"_pipeline_mmp_provider": "airbridge",
"_pipeline_airbridge_enabled": true,
"_pipeline_airbridge_app_name": "<앱 subdomain>"
```
- 앱 subdomain = Airbridge 대시보드 URL `https://app.airbridge.io/`**`여기`**`/...` 의 이름 (제우스=`zeuskr`).

### ③ 반영 + 검증
```powershell
cd C:\claude\cloop_dashboard
.\.venv\Scripts\python.exe -m pipeline.main --title <타이틀ID>
```
- 로그에 `→ airbridge N행 fetch` 가 나오면 **성공**.
- `403`/`404` 가 나오면: 토큰(계정 불일치) 또는 앱 이름 오타 → 확인.

## 같은 계정을 쓰는 타이틀이라면?
그 계정 토큰이 여러 앱 접근 권한(org 토큰)을 가지면 **①(토큰 추가)을 생략**하고 기본 `AIRBRIDGE_API_TOKEN`으로 접근할 수도 있습니다. 다만 **헷갈리지 않게 항상 ①까지 넣는 걸 권장**합니다.

## 실제 예시 — 제우스 (2026-07-01 확립)
- `.env`: `AIRBRIDGE_API_TOKEN_ZEUS=<제우스 토큰>` (사용자 직접 입력)
- `titles.json` zeus: `_pipeline_mmp_provider="airbridge"` · `_pipeline_airbridge_enabled=true` · `_pipeline_airbridge_app_name="zeuskr"`
- 결과: `airbridge 92행 fetch` · MMP 9소재 (채널 `facebook.business`)
- 뒷단 코드: `pipeline/main.py` `_resolve_airbridge_token(title)` — env `AIRBRIDGE_API_TOKEN_<ID>` 우선, 없으면 기본 `AIRBRIDGE_API_TOKEN` 폴백.
