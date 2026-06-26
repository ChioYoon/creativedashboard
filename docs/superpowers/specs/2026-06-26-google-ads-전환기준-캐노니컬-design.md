# Google Ads 전환 기준 캐노니컬화 (캠페인 타입별 전환 액션) 설계 스펙

작성 2026-06-26 · 브레인스토밍 합의 + gd·펩 실데이터 진단 기반.

---

## 0. 한 줄 요약

현재 Google Ads `전환`은 `metrics.conversions`(캠페인의 **모든** 전환 액션 합산)이라 액션/ROAS/리타겟 캠페인이 설치+구매+이벤트로 **부풀려진다**. 캠페인명을 캐노니컬 파싱(LTV 대시보드 규칙)해 **`ua_type`로 전환 기준을 분기** — `NU-Pre`→사전예약 전환, 그 외→설치(first_open). 노출/클릭/비용/ROAS는 불변, **전환 카운트만** 정정.

---

## 1. 배경 · 문제

- `pipeline/sources/google_ads.py`가 `metrics.conversions`만 수집 → 캠페인의 전환에 포함된 **모든 액션의 합**.
- **실데이터 진단(2026-06-26)**:
  - NU-Pre 캠페인 → `App pre-registration`만 (깨끗). 설치 캠페인(ACi/INSTALL) → `first_open`만 (깨끗).
  - **액션 캠페인(ACa/ACA-PU/ACA-LV10)·ROAS(tROAS)** → `first_open` + `in_app_purchase` + `level_10` 등 **합산**(설치 아님, 부풀림). **리타겟(RT/ACe)** → `session_start`(설치 아님).
- 소재 데이터는 캠페인을 통합 비교하므로, 이대로면 캠페인 유형별 다른 액션이 섞여 "전환" 비교가 왜곡.

---

## 2. 확정 결정 (브레인스토밍 + 진단)

| 항목 | 결정 |
|------|------|
| 분기 키 | 캠페인명 캐노니컬 파싱의 **`ua_type`** (LTV 대시보드 규칙과 동일) |
| 전환 기준 | `ua_type == "NU-Pre"` → 사전예약 전환, 그 외(NU·RT·미파싱) → 설치(first_open) |
| 액션 매핑 | **타이틀별 설정**(titles.json). 미설정 타이틀은 **현행 metrics.conversions 유지**(하위호환) |
| 쿼리 | **듀얼 쿼리** — 기존(노출·클릭·비용·conversions_value 불변) + 신규(conversion_action별 전환). ⚠️ conversion_action 세그먼트는 노출/비용을 **중복**시키므로 신규 쿼리에서는 **전환만** 사용 |
| ROAS | **불변** (conversions_value = 기존 쿼리, 손대지 않음) |
| 캐노니컬 필드 | 캠페인명 파싱 결과(country·media·ua_type·product 등)를 **출력에 저장** → 대시보드 필터(Phase 2) 토대 |

**확정 액션 매핑:**
| 타이틀 | prereg | install |
|---|---|---|
| gd | `App pre-registration(com.com2us.gd.android.google.global.normal)` | `Gods & Demons - Com2uS (Android) first_open` |
| pepp-us | `App pre-registration(com.com2us.rheroes.android.google.global.normal)` | `rheroes - com.com2us.rheroes.android.google.global.normal (Android) First open` |

---

## 3. 아키텍처

```
titles.json: _pipeline_conversion_actions = {prereg:[...], install:[...]}
   ↓ resolve_config → cfg["conversion_actions"]
google_ads.py fetch_window(customer, start, end, ..., conversion_actions=cfg):
   쿼리 1 (기존, 불변): ad_group_ad_asset_view
        → asset×campaign×ad_group×date: impressions·clicks·cost·conversions_value
   쿼리 2 (신규, conversion_actions 있을 때만): ad_group_ad_asset_view
        + segments.conversion_action_name
        → asset×campaign×ad_group×date×action: metrics.conversions
   집계:
        캠페인명 → parse_campaign_ua_type()
        target = prereg actions (ua_type==NU-Pre) else install actions
        전환[4-key] = Σ 쿼리2 conversions where action ∈ target
   머지: CreativeKpiDaily.conversions ← 전환[4-key]  (나머지 필드는 쿼리1)
   + campaign_canonical 맵을 cfg/출력에 저장
```

---

## 4. 컴포넌트 상세

### 4-A. 캐노니컬 캠페인명 파서 (`pipeline/sources/google_ads.py` 또는 신규 `pipeline/campaign_canonical.py`)

LTV 대시보드 규칙: `{agency}_{executor}_{title}_{country}_{media}_{ua_type}_{os}_{product}[_{date}]` (`_` 구분, date=캠페인 시작일).

- **`parse_campaign_canonical(name) -> dict`**: `_` split → 위치 기반 필드. date(마지막, `^\d{6}$`)는 선택. 세그먼트 부족·형식 위반 시 가능한 필드만 채우고 나머지 None.
- **`campaign_ua_type(name) -> str`**: 세그먼트 중 알려진 ua_type 집합 `{NU-Pre, NU, RT, Boosting}` 과 **정확 일치**하는 값 반환(우선순위 NU-Pre). 없으면 `""`.
  - ⚠️ 견고성: 전환 기준 분기는 `campaign_ua_type(name) == "NU-Pre"` 단일 판정만 필요(위치 의존 최소화). 미파싱/미인식 → "" → 설치 버킷(기본).
- media_group 룩업·country/product 마스터 정규화는 **범위 밖**(LTV P0 소관). cloop은 위치 원시값 그대로 저장.

### 4-B. 듀얼 GAQL 쿼리 + 전환 기준 집계 (`fetch_window` / `_build_gaql`)

- **쿼리 1 (기존, 변경 없음)**: 현재 `_build_gaql` 그대로. impr·clicks·cost·conversions_value·conversions(폴백용) 수집. → 4-key CreativeKpiDaily.
- **쿼리 2 (신규)**: `conversion_actions` 설정 있을 때만 실행. 기존 SELECT에서 metrics는 **`metrics.conversions`만** + `segments.conversion_action_name` 추가. (impressions/clicks/cost 미수집 — 중복되므로.)
  - `_build_gaql_conversions(start, end, chunk, campaign_filter)` 신규 빌더.
  - 집계: `(creative_name, campaign_name, ad_group_name, date) → {action_name: conversions}`.
- **전환 기준 적용**:
  ```python
  prereg = set(cfg_actions["prereg"]); install = set(cfg_actions["install"])
  for key, action_map in conv_by_key.items():
      ua = campaign_ua_type(key.campaign_name)
      target = prereg if ua == "NU-Pre" else install
      conv = sum(v for a, v in action_map.items() if a in target)
      # 머지: 쿼리1의 CreativeKpiDaily[key].conversions = conv
  ```
  - prereg/install 액션이 둘 다 없는 캠페인(리타겟 session_start 등) → 전환 0.
- **머지**: 쿼리1 결과의 `conversions` 필드를 쿼리2 산출 전환으로 **덮어씀**. conversions_value·impr·clicks·cost는 쿼리1 그대로.
- **설정 없는 타이틀**: 쿼리2 미실행, 쿼리1의 metrics.conversions 그대로 사용(현행 동작).

### 4-C. 타이틀별 전환 액션 설정 (titles.json + resolve_config)

```json
"_pipeline_conversion_actions": {
  "prereg":  ["App pre-registration(com.com2us.gd.android.google.global.normal)"],
  "install": ["Gods & Demons - Com2uS (Android) first_open"]
}
```
- `resolve_config`(두 분기): `conversion_actions = title_meta.get("_pipeline_conversion_actions")` → cfg.
- 액션명은 **정확 일치**(앱ID suffix 포함). 리스트라 복수 액션 허용(현재 각 1개).
- gd·펩 값은 §2 표대로. 다른 타이틀은 미설정 → 현행.

### 4-D. 캐노니컬 필드 저장 (필터 토대, Phase 2)

- 파이프라인이 출력 JSON에 **campaign→캐노니컬 맵** 저장: `{campaign_name: {agency, executor, title, country, media, ua_type, os, product, date}}`.
- Phase 2 대시보드(step1·live_dashboard) 필터가 이 맵으로 country/media/ua_type/product 슬라이스. (Phase 2는 별도 플랜 — 본 스펙은 토대 데이터만 산출.)

---

## 5. 범위 밖

- **Phase 2 대시보드 필터 UI** (step1·live_dashboard의 ua_type/country/media/product 필터) — 본 스펙은 데이터(campaign_canonical 맵) 토대만. 필터 UI는 후속 스펙/플랜.
- **LTV 대시보드의 마스터 정규화**(media→media_group, country/product 마스터, alias/인코딩/정크 필터) — 별도 프로젝트(`C:\claude\ltvdashboard`) P0. cloop은 위치 원시값 사용.
- ROAS/conversions_value 정의 변경.
- 미설정 타이틀(펩·gd 외)의 전환 기준 — 현행 유지(opt-in).

---

## 6. 테스트 전략

| # | 검증 | 방법 |
|---|------|------|
| T1 | `campaign_ua_type` — NU-Pre/NU/RT/미파싱 정확 판정 | 단위테스트 |
| T2 | `parse_campaign_canonical` — 위치 필드 추출(date 유무·세그먼트 부족) | 단위테스트 |
| T3 | 전환 기준 집계 — NU-Pre→prereg 합, 그 외→install 합, in_app_purchase/session_start 제외, prereg/install 없으면 0 | 단위테스트(action_map 픽스처) |
| T4 | 미설정 타이틀 — 쿼리2 미실행·현행 conversions 유지(하위호환) | 단위테스트(cfg 분기) |
| T5 | 라이브 검증(gd·펩) — 신규 전환수가 진단값과 일치(예: 펩 NU-Pre 사전예약 98,951, 설치캠 first_open) + 노출/비용/ROAS 무변동 | 실측 재실행 |
| T6 | 전체 회귀 | `pytest tests/` |

---

## 7. 구현 범위 (이번 회차 — Phase 1)

- [ ] `campaign_ua_type()` + `parse_campaign_canonical()` (파서) + 단위테스트(T1·T2)
- [ ] `_build_gaql_conversions()` + `fetch_window` 듀얼 쿼리 + 전환 기준 집계·머지 + 단위테스트(T3·T4)
- [ ] resolve_config 배선(`conversion_actions`) + titles.json gd·펩 설정
- [ ] 출력에 campaign_canonical 맵 저장(Phase 2 토대)
- [ ] 라이브 검증(gd·펩, T5) + 전체 회귀(T6)
- [ ] Phase 2(대시보드 필터)는 별도 플랜
