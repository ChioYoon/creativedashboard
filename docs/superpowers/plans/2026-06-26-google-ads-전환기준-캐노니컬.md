# Google Ads 전환 기준 캐노니컬화 (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Google Ads '전환'을 캠페인 `ua_type`별로 분기 — `NU-Pre`→사전예약 전환, 그 외→설치(first_open) — 해 캠페인 유형이 섞이는 전환 부풀림을 정정한다.

**Architecture:** 캠페인명을 LTV 캐노니컬 규칙으로 파싱(`ua_type`)하고, Google Ads를 **듀얼 쿼리**로 가져온다 — 기존 쿼리(노출·클릭·비용·conversions_value 불변) + 신규 conversion_action별 전환 쿼리. 전환 카운트만 타깃 액션(prereg/install) 합으로 덮어쓴다. 액션 매핑은 타이틀별 설정(미설정 시 현행 유지).

**Tech Stack:** Python 3.12, pytest, google-ads SDK (ad_group_ad_asset_view, GAQL).

## Global Constraints

- **분기 키**: `ua_type == "NU-Pre"` → 사전예약, 그 외(NU·RT·미파싱) → 설치. 캠페인명 캐노니컬 규칙 `{agency}_{executor}_{title}_{country}_{media}_{ua_type}_{os}_{product}[_{date}]`, `_` 구분, date=`\d{6}`(캠페인 시작일).
- **전환 액션 정확 일치**(앱ID suffix 포함, 리스트). 매핑:
  - gd: prereg=`App pre-registration(com.com2us.gd.android.google.global.normal)`, install=`Gods & Demons - Com2uS (Android) first_open`
  - pepp-us: prereg=`App pre-registration(com.com2us.rheroes.android.google.global.normal)`, install=`rheroes - com.com2us.rheroes.android.google.global.normal (Android) First open`
- **듀얼 쿼리**: 기존 쿼리 변경 없음. 신규 쿼리는 conversion_action 세그먼트 → 노출/클릭/비용 **중복**되므로 신규 쿼리에서 **conversions만** SELECT·사용.
- **ROAS 불변**: conversions_value는 기존 쿼리 그대로.
- **하위호환**: `_pipeline_conversion_actions` 미설정 타이틀 → 신규 쿼리 미실행, 현행 metrics.conversions 유지.
- **범위**: Phase 1 = 파이프라인 전환 기준. **campaign_canonical 맵 저장 + 대시보드 필터(country/media/ua_type/product)는 Phase 2(별도 플랜)** — 본 플랜은 파서를 그 토대로 함께 제공.
- 수동 실행: PowerShell `$env:PYTHONUTF8=1`, `.venv\Scripts\python.exe`.

## File Structure

- Create `pipeline/campaign_canonical.py` — 캠페인명 파서(`parse_campaign_canonical`, `campaign_ua_type`). 순수·HTTP 무의존.
- Modify `pipeline/sources/google_ads.py` — `_build_gaql_conversions`, `_apply_conversion_basis`(순수), `fetch_window`(conversion_actions 듀얼 쿼리).
- Modify `pipeline/main.py` — resolve_config 배선(`conversion_actions`) + fetch_window 호출.
- Modify `js/titles.json` — gd·pepp `_pipeline_conversion_actions`.
- Create `tests/test_campaign_canonical.py`, `tests/test_google_ads_conversions.py`.

---

## Task 1: 캠페인명 캐노니컬 파서

**Files:**
- Create: `pipeline/campaign_canonical.py`
- Test: `tests/test_campaign_canonical.py`

**Interfaces — Produces:**
- `parse_campaign_canonical(name: str) -> dict` (키: agency·executor·title·country·media·ua_type·os·product·date, 없으면 None)
- `campaign_ua_type(name: str) -> str` (NU-Pre/NU/RT/Boosting 중 정확 일치, NU-Pre 우선; 없으면 "")

---

- [ ] **Step 1: 테스트 작성** (`tests/test_campaign_canonical.py`)

```python
"""캠페인명 캐노니컬 파서 단위테스트."""
from pipeline.campaign_canonical import parse_campaign_canonical, campaign_ua_type


def test_ua_type_nupre():
    assert campaign_ua_type("Maximizer_HQ_GD_KR-KR_GA_NU-Pre_AD_ACp_241218") == "NU-Pre"
    assert campaign_ua_type("HQ_HQ_PH_US-EN_GA_NU-Pre_AD_ACp_251104") == "NU-Pre"


def test_ua_type_nu_and_rt():
    assert campaign_ua_type("Maximizer_HQ_GD_KR-KR_GA_NU_AD_ACi_250115") == "NU"
    assert campaign_ua_type("HQ_HQ_PH_US-EN_GA_RT_AD_ACe_250522") == "RT"


def test_ua_type_unparsed_empty():
    assert campaign_ua_type("test_campaign_junk") == ""
    assert campaign_ua_type("") == ""


def test_parse_canonical_full():
    p = parse_campaign_canonical("Maximizer_HQ_GD_KR-KR_GA_NU-Pre_AD_ACp_241218")
    assert p["agency"] == "Maximizer" and p["executor"] == "HQ" and p["title"] == "GD"
    assert p["country"] == "KR-KR" and p["media"] == "GA" and p["ua_type"] == "NU-Pre"
    assert p["os"] == "AD" and p["product"] == "ACp" and p["date"] == "241218"


def test_parse_canonical_no_date():
    p = parse_campaign_canonical("Mobidays_HQ_RUSH_WW-EN_FB_NU_AD_AAA-AEO-Tutorial2")
    assert p["product"] == "AAA-AEO-Tutorial2" and p["date"] is None
    assert p["ua_type"] == "NU"
```

- [ ] **Step 2: 실패 확인**

```bash
cd C:\claude\cloop_dashboard
.venv\Scripts\python.exe -m pytest tests/test_campaign_canonical.py -q 2>&1 | tail -6
```
기대: `ModuleNotFoundError: No module named 'pipeline.campaign_canonical'`.

- [ ] **Step 3: 구현** (`pipeline/campaign_canonical.py` 신규)

```python
# -*- coding: utf-8 -*-
"""캠페인명 캐노니컬 파싱 — LTV 대시보드 규칙.

규칙: {agency}_{executor}_{title}_{country}_{media}_{ua_type}_{os}_{product}[_{date}]
'_' 구분, 마지막 6자리 숫자 세그먼트는 date(캠페인 시작일). 위치 기반.
(media→media_group 룩업·country/product 마스터 정규화는 LTV 프로젝트 소관 — 여기선 위치 원시값.)
"""
from __future__ import annotations

import re

_FIELDS = ["agency", "executor", "title", "country", "media", "ua_type", "os", "product"]
_KNOWN_UA_TYPES = ("NU-Pre", "RT", "Boosting", "NU")  # NU-Pre 우선(NU 보다 앞)
_DATE_RE = re.compile(r"^\d{6}$")


def parse_campaign_canonical(name: str) -> dict:
    """캠페인명 → 캐노니컬 필드 dict (위치 기반). 부족/위반 시 가능한 필드만, 나머지 None."""
    out: dict = {f: None for f in _FIELDS}
    out["date"] = None
    if not name:
        return out
    segs = name.split("_")
    if segs and _DATE_RE.match(segs[-1]):
        out["date"] = segs[-1]
        segs = segs[:-1]
    for i, f in enumerate(_FIELDS):
        if i < len(segs):
            out[f] = segs[i]
    return out


def campaign_ua_type(name: str) -> str:
    """캠페인명에서 ua_type 추출 — 세그먼트와 정확 일치(NU-Pre 우선). 없으면 ''."""
    if not name:
        return ""
    segs = set(name.split("_"))
    for ua in _KNOWN_UA_TYPES:
        if ua in segs:
            return ua
    return ""
```

- [ ] **Step 4: 통과 확인**

```bash
cd C:\claude\cloop_dashboard
.venv\Scripts\python.exe -m pytest tests/test_campaign_canonical.py -q 2>&1 | tail -4
```
기대: 5 passed.

- [ ] **Step 5: 커밋**

```bash
cd C:\claude\cloop_dashboard
git add pipeline/campaign_canonical.py tests/test_campaign_canonical.py
git commit -m "feat(canonical): 캠페인명 캐노니컬 파서(ua_type·필드 위치 파싱) — LTV 규칙 정렬"
```

---

## Task 2: Google Ads 듀얼 쿼리 전환 기준

**Files:**
- Modify: `pipeline/sources/google_ads.py`
- Test: `tests/test_google_ads_conversions.py`

**Interfaces — Consumes:** `campaign_ua_type`(Task 1)
**Interfaces — Produces:**
- `GoogleAdsKpiSource._build_gaql_conversions(start, end, chunk, campaign_filter) -> str`
- `_apply_conversion_basis(agg: dict, conv_by_key: dict, prereg: set, install: set) -> dict` (모듈 함수, agg의 conversions 덮어씀)
- `fetch_window(..., conversion_actions: Optional[dict] = None)` (신규 인자)

---

- [ ] **Step 1: 테스트 작성** (`tests/test_google_ads_conversions.py`)

```python
"""Google Ads 전환 기준 분기 단위테스트 (HTTP 무의존)."""
from pipeline.schemas import CreativeKpiDaily
from pipeline.sources.google_ads import _apply_conversion_basis, GoogleAdsKpiSource
from datetime import date

PRE = {"App pre-registration(com.com2us.gd.android.google.global.normal)"}
INS = {"Gods & Demons - Com2uS (Android) first_open"}


def _daily(cn, camp, conv=0.0):
    return CreativeKpiDaily(creative_name=cn, date="2026-01-01", source="google_ads",
                            customer_id="1", campaign_name=camp, conversions=conv)


def test_nupre_campaign_uses_prereg_only():
    key = ("A", "Maximizer_HQ_GD_KR-KR_GA_NU-Pre_AD_ACp_241218", "ag", "2026-01-01")
    agg = {key: _daily("A", key[1])}
    conv = {key: {"App pre-registration(com.com2us.gd.android.google.global.normal)": 100.0,
                  "Gods & Demons - Com2uS (Android) first_open": 5.0}}
    _apply_conversion_basis(agg, conv, PRE, INS)
    assert agg[key].conversions == 100.0


def test_nu_campaign_uses_install_excludes_purchase():
    key = ("B", "Maximizer_HQ_GD_KR-KR_GA_NU_AD_ACa_250115", "ag", "2026-01-01")
    agg = {key: _daily("B", key[1])}
    conv = {key: {"Gods & Demons - Com2uS (Android) first_open": 30.0,
                  "Gods & Demons - Com2uS (Android) in_app_purchase": 110.0}}
    _apply_conversion_basis(agg, conv, PRE, INS)
    assert agg[key].conversions == 30.0   # 설치만, 구매 제외


def test_retargeting_no_target_action_zero():
    key = ("C", "Maximizer_HQ_GD_KR-KR_GA_RT_AD_ACe_250522", "ag", "2026-01-01")
    agg = {key: _daily("C", key[1], conv=99.0)}
    conv = {key: {"Gods & Demons - Com2uS (Android) session_start": 50.0}}
    _apply_conversion_basis(agg, conv, PRE, INS)
    assert agg[key].conversions == 0.0   # 설치/사전예약 액션 없음 → 0


def test_key_with_no_conversions_zero():
    key = ("D", "Maximizer_HQ_GD_KR-KR_GA_NU_AD_ACi_250115", "ag", "2026-01-01")
    agg = {key: _daily("D", key[1], conv=7.0)}
    _apply_conversion_basis(agg, {}, PRE, INS)   # conv_by_key 비어있음
    assert agg[key].conversions == 0.0


def test_build_gaql_conversions_shape():
    q = GoogleAdsKpiSource._build_gaql_conversions(date(2025, 1, 1), date(2025, 1, 31), None, None)
    assert "segments.conversion_action_name" in q
    assert "metrics.conversions" in q
    assert "metrics.impressions" not in q   # 중복 방지 — 노출 미수집
    assert "FROM ad_group_ad_asset_view" in q
```

- [ ] **Step 2: 실패 확인**

```bash
cd C:\claude\cloop_dashboard
.venv\Scripts\python.exe -m pytest tests/test_google_ads_conversions.py -q 2>&1 | tail -8
```
기대: `ImportError: cannot import name '_apply_conversion_basis'`.

- [ ] **Step 3: 구현 — 모듈 함수 + 쿼리 빌더** (`pipeline/sources/google_ads.py`)

파일 상단 import 영역(`from ..schemas import CreativeKpiDaily` 다음)에 추가:
```python
from ..campaign_canonical import campaign_ua_type
```

모듈 레벨(클래스 밖, 파일 끝 `resolve_window` 근처)에 추가:
```python
def _apply_conversion_basis(agg: dict, conv_by_key: dict, prereg: set, install: set) -> dict:
    """agg(4-key→CreativeKpiDaily)의 conversions 를 캠페인 ua_type별 타깃 액션 합으로 덮어씀.

    ua_type == 'NU-Pre' → prereg 액션 합, 그 외 → install 액션 합. 타깃 액션 없으면 0.
    conv_by_key: 4-key(creative_name, campaign_name, ad_group_name, date) → {action_name: conversions}.
    """
    for key, daily in agg.items():
        ua = campaign_ua_type(key[1])  # key[1] = campaign_name
        target = prereg if ua == "NU-Pre" else install
        action_map = conv_by_key.get(key) or {}
        daily.conversions = float(sum(v for a, v in action_map.items() if a in target))
    return agg
```

`GoogleAdsKpiSource` 클래스 내 `_build_gaql` 다음에 추가:
```python
    @staticmethod
    def _build_gaql_conversions(start, end, chunk, campaign_filter) -> str:
        """conversion_action별 전환 전용 쿼리. ⚠️ conversion_action 세그먼트는 노출/비용을
        중복시키므로 conversions 만 SELECT (노출·클릭·비용 미수집)."""
        where_clauses = [
            f"segments.date BETWEEN '{start.isoformat()}' AND '{end.isoformat()}'"
        ]
        if campaign_filter:
            where_clauses.append(f"campaign.name IN ({_quote_csv(campaign_filter)})")
        if chunk:
            names_csv = _quote_csv(chunk)
            where_clauses.append(
                f"(asset.name IN ({names_csv}) OR asset.youtube_video_asset.youtube_video_title IN ({names_csv}))"
            )
        query = f"""
            SELECT
              segments.date,
              asset.name,
              asset.youtube_video_asset.youtube_video_title,
              ad_group.name,
              campaign.name,
              segments.conversion_action_name,
              metrics.conversions
            FROM ad_group_ad_asset_view
            WHERE {' AND '.join(where_clauses)}
        """
        return " ".join(query.split())
```

- [ ] **Step 4: 구현 — fetch_window 듀얼 쿼리 통합** (`pipeline/sources/google_ads.py`)

`fetch_window` 시그니처에 인자 추가:
```python
    def fetch_window(
        self,
        customer_id: str,
        start: date,
        end: date,
        creative_names: Optional[Sequence[str]] = None,
        campaign_filter: Optional[Sequence[str]] = None,
        conversion_actions: Optional[dict] = None,
    ) -> Iterable[CreativeKpiDaily]:
```

`fetch_window` 본문에서 기존 쿼리 루프(`return list(agg.values())` 직전)에 추가:
```python
        # ── 전환 기준 분기 (conversion_actions 설정 시): 듀얼 쿼리 ──
        if conversion_actions:
            from collections import defaultdict as _dd
            prereg = set(conversion_actions.get("prereg") or [])
            install = set(conversion_actions.get("install") or [])
            conv_by_key: dict = _dd(lambda: _dd(float))
            for chunk in chunks:
                q2 = self._build_gaql_conversions(start, end, chunk, campaign_filter)
                try:
                    stream2 = ga_service.search_stream(customer_id=customer_id, query=q2)
                    for batch in stream2:
                        for row in batch.results:
                            cname = self._resolve_creative_name(row)
                            if not cname:
                                continue
                            key = (cname, row.campaign.name or "", row.ad_group.name or "", row.segments.date)
                            act = row.segments.conversion_action_name or ""
                            conv_by_key[key][act] += float(row.metrics.conversions)
                except GoogleAdsException as e:
                    err_msg = self._format_googleads_exception(e)
                    if self._is_auth_error(e):
                        raise AuthError(err_msg)
                    if self._is_quota_error(e):
                        raise QuotaError(err_msg)
                    raise RuntimeError(err_msg)
            _apply_conversion_basis(agg, conv_by_key, prereg, install)

        return list(agg.values())
```

- [ ] **Step 5: 통과 확인**

```bash
cd C:\claude\cloop_dashboard
.venv\Scripts\python.exe -m pytest tests/test_google_ads_conversions.py -q 2>&1 | tail -5
.venv\Scripts\python.exe -c "from pipeline.sources import google_ads; print('import OK')"
```
기대: 5 passed + import OK.

- [ ] **Step 6: 커밋**

```bash
cd C:\claude\cloop_dashboard
git add pipeline/sources/google_ads.py tests/test_google_ads_conversions.py
git commit -m "feat(google_ads): 듀얼 쿼리 전환 기준 분기(ua_type→prereg/install 액션) + 노출/비용/ROAS 불변"
```

---

## Task 3: main.py 배선 + titles.json 설정

**Files:**
- Modify: `pipeline/main.py`
- Modify: `js/titles.json`

**Interfaces — Consumes:** `fetch_window(..., conversion_actions=)`(Task 2)

---

- [ ] **Step 1: resolve_config 배선 (override 분기)** (`pipeline/main.py`)

`title_override` 분기에서 `appsflyer_exclude = title_override.get("_pipeline_appsflyer_exclude_media_sources", [])` 다음 줄에 추가:
```python
        conversion_actions = title_override.get("_pipeline_conversion_actions")
```

- [ ] **Step 2: resolve_config 배선 (meta 분기)** (`pipeline/main.py`)

`title_meta` 분기에서 `appsflyer_exclude = title_meta.get("_pipeline_appsflyer_exclude_media_sources", [])` 다음 줄에 추가:
```python
        conversion_actions = title_meta.get("_pipeline_conversion_actions")
```

- [ ] **Step 3: cfg dict + fetch_window 호출 배선** (`pipeline/main.py`)

cfg dict(`"appsflyer_exclude_media_sources": appsflyer_exclude,` 다음 줄)에 추가:
```python
        "conversion_actions": conversion_actions,
```

Google Ads fetch 호출 — 찾을 문자열:
```python
                source.fetch_window(
                    customer_id=cfg["google_ads_customer_id"],
                    start=kpi_window_start,
                    end=kpi_window_end,
                    creative_names=None,
                    campaign_filter=cfg.get("google_ads_campaign_filter") or None,
                )
```
교체(마지막 인자 추가):
```python
                source.fetch_window(
                    customer_id=cfg["google_ads_customer_id"],
                    start=kpi_window_start,
                    end=kpi_window_end,
                    creative_names=None,
                    campaign_filter=cfg.get("google_ads_campaign_filter") or None,
                    conversion_actions=cfg.get("conversion_actions"),
                )
```

- [ ] **Step 4: titles.json — gd·pepp 설정** (`js/titles.json`)

gd 항목: `"_pipeline_google_ads_campaign_filter": [],` 다음 줄에 추가:
```json
    "_pipeline_conversion_actions": {
      "prereg": ["App pre-registration(com.com2us.gd.android.google.global.normal)"],
      "install": ["Gods & Demons - Com2uS (Android) first_open"]
    },
```

pepp-us 항목: `"_pipeline_google_ads_campaign_filter": [],` 다음 줄에 추가:
```json
    "_pipeline_conversion_actions": {
      "prereg": ["App pre-registration(com.com2us.rheroes.android.google.global.normal)"],
      "install": ["rheroes - com.com2us.rheroes.android.google.global.normal (Android) First open"]
    },
```

- [ ] **Step 5: import + JSON 유효성 + 회귀**

```bash
cd C:\claude\cloop_dashboard
.venv\Scripts\python.exe -c "import json; d=json.load(open('js/titles.json',encoding='utf-8')); [print(t['id'], 'conv_actions:', bool(t.get('_pipeline_conversion_actions'))) for t in d if t['id'] in ('gd','pepp-us')]"
.venv\Scripts\python.exe -c "from pipeline import main; print('import OK')"
.venv\Scripts\python.exe -m pytest tests/ -q 2>&1 | tail -4
```
기대: gd·pepp-us conv_actions True, import OK, 전체 PASSED.

- [ ] **Step 6: 커밋**

```bash
cd C:\claude\cloop_dashboard
git add pipeline/main.py js/titles.json
git commit -m "feat(main): conversion_actions 배선 + gd·펩 전환 액션 설정(NU-Pre→사전예약, 그 외→설치)"
```

---

## Task 4: 라이브 검증 + 회귀

**Files:** (검증만 — 코드 변경 없음)

---

- [ ] **Step 1: 펩 재실행 — 전환 기준 적용 확인**

> Google Ads 듀얼 쿼리 + 전환 분기 적용. Gemini는 캐시 히트(0콜) 또는 quota 무관(KPI fetch만 확인).

```bash
cd C:\claude\cloop_dashboard
$env:PYTHONUTF8=1; $env:PYTHONIOENCODING='utf-8'
.venv\Scripts\python.exe -m pipeline.main --title pepp-us 2>&1 | Select-String "KPI fetch|행 fetch|conversions|완료" | Select-Object -First 10
```
산출 검증 — 펩 소재의 전환이 NU-Pre→사전예약·그 외→설치로 집계되는지(부풀림 제거):
```bash
.venv\Scripts\python.exe -c "import json; d=json.loads(open('public/data/pepp-us.json',encoding='utf-8-sig').read()); tot=sum((c.get('전환') or 0) for c in d['creatives']); print('펩 소재 전환 합계:', tot)"
```
기대: 정상 완료. 전환 합계가 사전예약(NU-Pre)+설치(그 외)만 반영(in_app_purchase·level 이벤트 제외) — 진단값(사전예약 98,951대 + 설치 4,101대 범위) 정합. 노출/비용/ROAS 무변동.

- [ ] **Step 2: gd 검증 (선택 — 태깅 quota 무관, KPI만)**

gd는 태깅 quota로 소재가 적을 수 있으나 Google Ads fetch·전환 분기는 동작. 16:00 이후 또는 캐시 상태에서:
```bash
cd C:\claude\cloop_dashboard
$env:PYTHONUTF8=1; .venv\Scripts\python.exe -m pipeline.main --title gd 2>&1 | Select-String "KPI fetch|행 fetch|완료" | Select-Object -First 8
```
기대: Google Ads fetch 정상(2025 데이터, kpi_start_date), 전환이 ACa/ROAS 캠페인에서 설치(first_open)만 반영.

- [ ] **Step 3: 전체 회귀 + 커밋·push**

```bash
cd C:\claude\cloop_dashboard
.venv\Scripts\python.exe -m pytest tests/ -q 2>&1 | tail -4
git add public/data/pepp-us.json public/data/gd.json
git commit -m "data(kpi): 전환 기준 캐노니컬 분기 적용 — 펩·gd 재산출"
git push origin main
```
기대: 전체 PASSED. (gd.json은 변경 있을 때만 add.)

---

## 검증 체크리스트

- [ ] `pytest tests/test_campaign_canonical.py` 5개 PASSED (ua_type·필드 파싱)
- [ ] `pytest tests/test_google_ads_conversions.py` 5개 PASSED (NU-Pre→prereg·NU→install·제외·0·쿼리형태)
- [ ] 전체 `pytest tests/` 무회귀 + import OK
- [ ] 펩 재실행 — 전환이 사전예약/설치만 반영(이벤트 제외), 노출·비용·ROAS 무변동
- [ ] 미설정 타이틀(있다면) 현행 동작 유지

## Phase 2 (별도 플랜 — 본 플랜 범위 밖)

- campaign_canonical 맵을 출력 JSON에 저장 (파서는 Task 1에서 제공됨)
- step1·live_dashboard에 ua_type/country/media/product 필터 UI
