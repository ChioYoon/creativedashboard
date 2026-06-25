# MMP(Airbridge) 절대 시작일 + 청크 fetch 설계 스펙

작성 2026-06-25 · 브레인스토밍 합의 기반. (Google Ads 절대 시작일 수정 79edc84의 자매 작업)

---

## 0. 한 줄 요약

Google Ads처럼 MMP(Airbridge)도 `window_days`(159)에 묶여 2026-01-22부터만 수집 중 → **비Google 매체(Facebook) 2025-11~12월 데이터 누락**(실측 568행 존재). 공통 `_pipeline_kpi_start_date`로 일반화하고, Airbridge actuals **쿼리 범위 제한을 90일 청크 분할**로 회피해 캠페인 시작부터 수집한다.

---

## 1. 배경 · 문제

- Google Ads는 79edc84로 절대 시작일(`_pipeline_google_ads_start_date`) 적용 완료 → 2025-11월부터 수집.
- **MMP(Airbridge)는 여전히 `kpi_window_days`(159) 상대 윈도우** 사용(main.py line 577) → **2026-01-22부터만** 수집.
- **실측**: Airbridge에 Facebook 데이터 **2025-11-18 ~ 12-21 존재(568행)** — 현재 윈도우 밖이라 누락.
- **Airbridge actuals 쿼리 범위 제한**: 81일·159일 OK, **236일(8개월) → HTTP 400**. 넓은 범위는 청크 필요(코드 docstring "최대 400일"은 부정확).

---

## 2. 확정 결정 (브레인스토밍)

| 항목 | 결정 |
|------|------|
| 설정 | `_pipeline_google_ads_start_date` → **`_pipeline_kpi_start_date`** 일반화 (Google Ads + MMP 공통) |
| MMP 윈도우 | `resolve_window(window_days, kpi_start_date)` (Google Ads와 동일 헬퍼) |
| 범위 제한 회피 | `fetch_mmp_window` 가 **≤90일 청크 분할** fetch 후 병합(dedup) |
| 적용 | pepp `_pipeline_kpi_start_date: "2025-11-01"` |

---

## 3. 아키텍처

```
titles.json: pepp _pipeline_kpi_start_date = "2025-11-01"
   ↓ resolve_config → cfg["kpi_start_date"]
main.py:
   Google Ads fetch: resolve_window(window_days, kpi_start_date)   # 기존(rename만)
   MMP fetch:        resolve_window(window_days, kpi_start_date)   # 신규 적용
      ↓ start=2025-11-01, end=어제 (≈237일)
   AirbridgeMmpSource.fetch_mmp_window(start, end):
      범위 > 90일 → [2025-11-01..2026-01-29], [2026-01-30..2026-04-29], [2026-04-30..어제] 청크
      각 청크 단일 쿼리(_fetch_window_single) → 병합·dedup
```

---

## 4. 컴포넌트 상세

### 4-A. 설정 필드 일반화 (`google_ads_start_date` → `kpi_start_date`)

- `js/titles.json`·`js/titles_overrides.json`: `_pipeline_google_ads_start_date` → `_pipeline_kpi_start_date` (pepp `"2025-11-01"`).
- `pipeline/main.py` resolve_config(두 분기): `_pipeline_kpi_start_date` 읽기 → cfg `"kpi_start_date"`.
- Google Ads fetch(line ~484): `resolve_window(cfg["kpi_window_days"], cfg.get("kpi_start_date") or None)` (기존 `google_ads_start_date` 참조 교체).
- 의미: 타이틀 UA 시작일(보통 Google·非Google 동일). 분리가 필요한 타이틀은 향후 granularity 추가(YAGNI).

### 4-B. MMP 윈도우에 resolve_window 적용 (`pipeline/main.py` ~577)

현행:
```python
            _win = cfg.get("kpi_window_days") or cfg.get("google_ads_window_days") or 159
            _end = _date.today() - _td(days=1)
            _start = _end - _td(days=_win - 1)
```
변경:
```python
            from .sources.google_ads import resolve_window as _resolve_window
            _start, _end = _resolve_window(
                cfg.get("kpi_window_days") or 159, cfg.get("kpi_start_date") or None
            )
```

### 4-C. Airbridge 청크 fetch (`pipeline/sources/airbridge.py`)

- `fetch_mmp_window(start, end, exclude_channels)` 를 **청크 래퍼**로 재작성:
  - 현행 단일 쿼리 본문(229-254) → `_fetch_window_single(start, end, exclude) -> tuple[list, bool]`(rows, truncated)로 추출.
  - `fetch_mmp_window`: `(end-start) > MAX_CHUNK_DAYS(=90)` 이면 ≤90일 청크로 분할, 각 청크 `_fetch_window_single` 호출, 행 병합 + dedup(key = creative_name·channel·campaign_name·date). `last_fetch_truncated` = 청크 중 하나라도 truncated.
  - 범위가 90일 이하면 단일 쿼리(청크 1개)와 동일 → 기존 동작 유지(하위 호환).
- 상수: `MAX_CHUNK_DAYS = 90` (실측 81일 성공 + 기존 retention 92일 청크 패턴과 정합).

### 4-D. 적용 (pepp)

- pepp `_pipeline_kpi_start_date: "2025-11-01"` → Google Ads(기존 유지) + MMP(신규) 둘 다 2025-11월부터.
- 펩 재실행 → MMP Facebook Nov-Dec(568행) 반영, mmp_daily 날짜 2025-11~ 확인.

---

## 5. 범위 밖

- 타이틀별 Google/非Google **분리 시작일**(현재 단일 `kpi_start_date` 공유) — 필요 시 후속.
- AppsFlyer 소스(미구현).
- Airbridge 10,000행/청크 상한 자체(기존 가드 유지).

---

## 6. 테스트 전략

| # | 검증 | 방법 |
|---|------|------|
| T1 | resolve_window 재사용(rename 후 Google Ads 무회귀) | 기존 `tests/test_kpi_window.py` 통과 |
| T2 | 청크 분할 — 90일 초과 범위가 N개 청크로 호출되고 병합·dedup | 단위테스트(`_fetch_window_single` mock → 청크 경계·dedup 검증) |
| T3 | 90일 이하 범위 → 단일 청크(기존 동작) | 단위테스트(mock 호출 1회) |
| T4 | 펩 재실행 → mmp_daily 2025-11월 데이터 반영 | 실측(MMP 날짜 min 2025-11~, Facebook Nov-Dec 행 존재) |
| T5 | 기존 전체 테스트 무회귀 | `pytest tests/` |

---

## 7. 구현 범위 (이번 회차)

- [ ] 필드 rename: `_pipeline_google_ads_start_date` → `_pipeline_kpi_start_date` (titles.json·overrides·main.py config·Google Ads fetch)
- [ ] main.py MMP 윈도우에 `resolve_window` 적용
- [ ] `airbridge.py`: `fetch_mmp_window` 청크 래퍼 + `_fetch_window_single` 추출 + dedup
- [ ] `tests/test_airbridge_chunk.py`: T2·T3
- [ ] pepp 재실행 검증(T4) + 전체 테스트(T5)
