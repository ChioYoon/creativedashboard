# AppsFlyer MMP 소스 + 메인 MMP 선택 설계 스펙

작성 2026-06-26 · 브레인스토밍 합의 기반. (Stage 7 Airbridge MMP 소스의 자매 작업 — 두 번째 MMP 프로바이더)

---

## 0. 한 줄 요약

향후 등록 타이틀 중 **AppsFlyer를 메인 MMP로 쓰는 타이틀**이 있어, Airbridge와 **동일 인터페이스**의 `AppsFlyerMmpSource`를 신설한다. 한 타이틀에 두 MMP를 **동시 등록**할 수 있고, **메인으로 지정된 한 곳만** 매일 수집해 대시보드에 사용한다(메인만 수집·사용 모델). 출력 스키마(`CreativeMmpDaily`)·품질지표·대시보드는 무변경.

---

## 1. 배경 · 문제

- 현 MMP 레이어는 **Airbridge 단일 프로바이더**에 하드코딩(main.py 2.6 블록 `if cfg.get("airbridge_enabled")`).
- 향후 타이틀은 AppsFlyer를 메인 MMP로 사용 → AppsFlyer API 연동 필요. 일부 타이틀은 **AppsFlyer·Airbridge 동시 적용**.
- **실측(라이브 AppsFlyer 계정, 147 앱)**: `Ad` 그룹핑으로 소재 단위 데이터 제공, 소재명이 파이프라인과 **동일 명명규칙**(`260616_VID_A-Character-Combat02A-UA_...`). 메트릭(Impressions/Clicks/Cost/Installs/Revenue/Retention rate/IPM/ROAS) 보유. 통화 USD, 타임존 UTC, 퍼센트는 소수(0.5=50%).
- **⚠️ 비용/노출은 기간 내 실제 유료 집행이 있어야만 채워짐** — cost 연동이 SUCCESS여도 해당 창에 집행 없으면 빈 값(펩·갓앤데몬 최근 주 실측에서 cost/impressions 비어 있었음). 타이틀·기간별 편차 큼 → **비용 유무 무관 graceful 필수**.

---

## 2. 확정 결정 (브레인스토밍)

| 항목 | 결정 |
|------|------|
| 매체 범위 | **항상 Google 제외** (현 2계층 모델 유지 — AppsFlyer=非Google MMP 레이어, Google은 Google Ads API가 별도). Airbridge와 동일 |
| 동시 적용 | 한 타이틀에 두 MMP **공존 가능**, **메인 한 곳만 수집·사용**. 메인 전환 = `_pipeline_mmp_provider` 변경. 비교 UI는 범위 밖(후속) |
| 접근법 | **형제 소스 + 프로바이더 선택기**(A안). `sources/appsflyer.py` 신설, main.py 작은 팩토리 분기. Airbridge 코드 무수정 |
| 인증 | `APPSFLYER_API_TOKEN`(.env, 조직 단위 1개 — 담당자 관리). 앱 식별자는 **타이틀별**(등록부 → `_pipeline_appsflyer_app_id`) |
| 비용 결측 | 0이 아니라 **결측**으로 — 설치·매출·잔존만 채우고 CPI/IPM/cost-ROAS는 대시보드 '—'(기존 None→'—' 경로) |
| 검증 | **실제 유료 집행이 있는 앱·기간을 탐색**해 4대 지표 전부 실데이터 확인 + 비용 없는 창 graceful 확인 |

---

## 3. 아키텍처

```
등록부 xlsx / titles.json:
   _pipeline_mmp_provider = "appsflyer" | "airbridge"   (메인 선택)
   _pipeline_appsflyer_app_id = "com.com2us.xxx..."     (AppsFlyer app)
   _pipeline_airbridge_enabled / .env AIRBRIDGE_APP_NAME (Airbridge app)
        ↓ resolve_config → cfg["mmp_provider"], cfg["appsflyer_app_id"]
main.py 2.6 블록:
   mmp_src = make_mmp_source(cfg)        # 팩토리: provider 로 분기
      provider=="appsflyer" → AppsFlyerMmpSource(token, app_id, ...)
      provider=="airbridge" → AirbridgeMmpSource.from_env()
   _start,_end = resolve_window(window_days, kpi_start_date)   # 공통(기존)
   mmp_daily = mmp_src.fetch_mmp_window(_start, _end, exclude_channels)
      → list[CreativeMmpDaily]           # 동일 스키마
   cfg["_mmp_daily"] = mmp_daily          # 다운스트림 무변경
   cfg["_mmp_currency"]/_mmp_fx_rate/_mmp_provider 주입
```

두 소스는 **동일 계약**: `fetch_mmp_window(start, end, exclude_channels) -> list[CreativeMmpDaily]`, 속성 `last_fetch_truncated`·`currency`·`usd_to_krw`.

---

## 4. 컴포넌트 상세

### 4-A. 프로바이더 선택기 (메인 MMP)

- **`make_mmp_source(cfg)`** (main.py 모듈 헬퍼): `cfg["mmp_provider"]`로 분기해 소스 인스턴스 반환. 미설정 시 `airbridge_enabled` → "airbridge"로 폴백(하위호환). 둘 다 없으면 None(skip).
- `resolve_config`(두 분기) 추가: `mmp_provider = title_meta.get("_pipeline_mmp_provider", "")` (빈 값이면 `airbridge_enabled`로 폴백), `appsflyer_app_id = title_meta.get("_pipeline_appsflyer_app_id", "")`. cfg 에 `"mmp_provider"`, `"appsflyer_app_id"` 추가.
- main.py 2.6 블록: 하드코딩된 `if cfg.get("airbridge_enabled")` → `mmp_src = make_mmp_source(cfg); if mmp_src is None: skip`. 윈도우 산출·주입·메트릭·graceful·예외처리(FileNotFoundError=토큰 미설정 skip)는 **공유**.
- **하위호환**: 기존 펩(`_pipeline_airbridge_enabled=True`, `_pipeline_mmp_provider` 없음) → provider="airbridge" 폴백 → 동작 무변경.

### 4-B. AppsFlyer 소스 & 데이터 매핑 (`pipeline/sources/appsflyer.py`)

- **`class AppsFlyerMmpSource`** (KpiSource ABC 미상속 — Airbridge와 동일 정책):
  - `__init__(self, token, app_id, metrics_map=None, usd_to_krw=1.0, session=None, ...)`. `from_env()` 클래스메서드(token=`APPSFLYER_API_TOKEN`, app_id 인자 필요 — main.py 가 registry app_id 전달). 토큰 미설정 시 `FileNotFoundError`(Airbridge와 동일 graceful skip).
  - `fetch_mmp_window(start, end, exclude_channels) -> list[CreativeMmpDaily]`, `last_fetch_truncated`, `currency`, `usd_to_krw`.
- **데이터 소스**(AppsFlyer raw 리포팅 API, 토큰 인증 — 헤드리스/nightly 가능):
  - **Cohort API** (`POST https://hq1.appsflyer.com/api/cohorts/v1/data/app/{app_id}`): groupings `["af_ad","media_source","date"]`, kpi `installs·cost·revenue(D7 누적)·retention(D1)`. retention은 **비율(%)** → `retained_d1 = round(retention_rate * installs)`(스키마는 count). D7 매출=cohort day0~7 누적.
  - **Aggregate Performance Report API** (소재=af_ad 그룹핑): `impressions·clicks`(IPM·CTR 용 — cohort 메트릭 아님).
  - 두 응답을 **(creative, media_source, date) 키로 머지** → `CreativeMmpDaily`. 한쪽에만 있는 행도 보존(비용 결측 graceful).
- **⚠️ 정확한 엔드포인트·파라미터·필드 key 는 구현 시 라이브 API로 검증**(Airbridge 7-A 방식). MCP `fetch_aggregated_data`로 기대값 교차 대조.
- 통화 USD → 기존 `usd_to_krw` fx 재사용(비용·매출만 ×fx, 비율 불변). 범위 제한 있으면 Airbridge처럼 청크 분할(AppsFlyer 한도 구현 시 확인).
- 소재명(af_ad)은 파이프라인 concept 추출 그대로(동일 명명규칙 확인됨). 빈 `af_ad`(오가닉) 행 skip.

### 4-C. 비용 결측 graceful (분모 가드)

- `CreativeMmpDaily`는 int 0 기본이라 "비용 없음"과 "비용 0"을 데이터 레벨에서 구분 불가. AppsFlyer는 **설치>0·비용=0** 행이 흔함(어트리뷰션은 있고 cost 연동 미스). 그대로 두면 CPI=cost/installs=₩0, IPM=installs/0 등 **오표시** 발생.
- **분모 가드 (전 MMP 프로바이더 공통)**: 품질지표 산출에서 분모/원천이 0이면 해당 지표 **null('—')** 로 — `cost<=0` → CPI·cost-ROAS null, `impressions<=0` → IPM null. 매출·설치·(잔존율=잔존/설치, 설치>0이면 유효)은 그대로 표시. 즉 "유료지표는 비용·노출이 있어야 산출, 없으면 비공개".
- 적용 위치: **파이프라인 `pipeline/mmp_metrics.py`**(저장 점수) + **대시보드 `scoreMmpItems`/`mmpQualityMetrics`(layer-metrics.js)**(런타임 재계산) — 양쪽 동일 규칙(파이프라인=대시보드 정합 유지).
- ⚠️ **Airbridge 회귀 주의**: 기존 펩에 cost=0 MMP 행이 있으면 CPI ₩0 → '—'로 바뀜(의도된 개선이나 T6에서 확인). Airbridge는 cost_channel 연동이라 0 빈도 낮음.

### 4-D. 매체 제외셋 (AppsFlyer media_source 체계)

- AppsFlyer media_source id 는 Airbridge channel 명과 다름(`googleadwords_int`·`facebook`·`tiktokglobal_int` 등). **별도 기본 제외셋** `DEFAULT_EXCLUDE_MEDIA_SOURCES = {"googleadwords_int", "organic", "None", ...}`(Google + 오가닉/내부). 빈 af_ad 행 skip.
- titles 오버라이드 가능(`_pipeline_appsflyer_exclude_media_sources`).

### 4-E. 등록부 / 설정 배선 (동시 적용 + 메인)

- **registry.py** `_map_row`: `MMP 종류`(메인 MMP) 값으로 분기 —
  - `"appsflyer"` → `_pipeline_mmp_provider="appsflyer"` + `_pipeline_appsflyer_app_id`(= `MMP 앱 식별자`) + fx 기본값.
  - `"airbridge"` → 기존대로 `_pipeline_airbridge_enabled=True` (+ `_pipeline_mmp_provider="airbridge"` 명시).
- **동시 적용**: 두 프로바이더 식별자(`_pipeline_appsflyer_app_id` + Airbridge app)가 한 타이틀에 공존 가능. 등록부 단일 `MMP 종류`는 **메인**을 정함; 보조 프로바이더 식별자는 `titles_overrides.json`(운영자)로 추가(자기 등록 폼은 메인 1개만 — 멀티 MMP 폼 컬럼은 후속). 메인 전환 = `_pipeline_mmp_provider` 변경(식별자가 이미 있으면 폼 재입력 불필요).
- Airbridge app 은 현재 .env 단일앱(relicheros) — 멀티 Airbridge 타이틀 등장 시 registry app 로 일반화(범위 밖).
- **출력 투명성**: 산출 JSON/메트릭에 `mmp_provider`(어느 MMP가 채웠는지) 기록 → notify 이메일·향후 대시보드 라벨용.

---

## 5. 범위 밖

- 두 MMP **동시 수집 + 대시보드 토글/비교**(이번은 메인만 수집·사용; 비교는 후속).
- iOS+Android **멀티플랫폼 합산**(타이틀당 단일 app_id로 시작).
- AppsFlyer SKAN·오가닉·리텐션 곡선 등 추가 분석.
- 대시보드 UI 변경(동일 `CreativeMmpDaily` 스키마라 불필요).
- 멀티 Airbridge 타이틀용 Airbridge app 의 registry 이관.
- 자기 등록 폼의 멀티 MMP 컬럼(현재 메인 1개; 보조는 overrides).

---

## 6. 테스트 전략

| # | 검증 | 방법 |
|---|------|------|
| T1 | 프로바이더 선택(폴백 포함) — appsflyer/airbridge/none·하위호환 | 단위테스트(`make_mmp_source` cfg 분기) |
| T2 | AppsFlyer 응답 → `CreativeMmpDaily` 파싱·머지(Cohort+Aggregate, retention%→count) | 단위테스트(픽스처, HTTP 무의존 파서) |
| T3 | 비용 결측 graceful — cost/impr 없는 행도 설치·매출·잔존 보존; 분모 가드(cost<=0→CPI/ROAS null, impr<=0→IPM null) | 단위테스트(부분 픽스처, mmp_metrics) |
| T4 | 매체 제외(googleadwords_int·오가닉·빈 af_ad) | 단위테스트 |
| T5 | 라이브 소스 검증 — 유료 집행 있는 앱·기간 탐색해 4대 지표 채워짐 + 비용 없는 창 graceful | 실측(MCP 교차 대조) |
| T6 | 기존 Airbridge(펩) 무회귀 | 펩 재실행 + 기존 전체 테스트 |

---

## 7. 구현 범위 (이번 회차)

- [ ] `pipeline/sources/appsflyer.py`: `AppsFlyerMmpSource`(Cohort+Aggregate fetch·머지·파서·graceful·청크) + `parse_*`(HTTP 무의존)
- [ ] main.py: `make_mmp_source(cfg)` 팩토리 + 2.6 블록 프로바이더 분기 + resolve_config 배선(`mmp_provider`·`appsflyer_app_id`) + 출력 `mmp_provider`
- [ ] registry.py: `MMP 종류 == "appsflyer"` 분기(provider·app_id·fx)
- [ ] 분모 가드: `mmp_metrics.py` + `layer-metrics.js`(scoreMmpItems/mmpQualityMetrics) — cost<=0→CPI/ROAS null, impr<=0→IPM null
- [ ] `tests/test_appsflyer_source.py`(T1~T4)
- [ ] 라이브 검증(T5) — 유료 집행 앱·기간 탐색, 4대 지표 + graceful + 펩 무회귀(T6)
- [ ] `.env` `APPSFLYER_API_TOKEN` 안내(docs/appsflyer-setup-guide.md)
