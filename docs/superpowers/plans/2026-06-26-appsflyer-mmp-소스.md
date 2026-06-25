# AppsFlyer MMP 소스 + 메인 MMP 선택 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AppsFlyer를 메인 MMP로 쓰는 타이틀을 위해 `AppsFlyerMmpSource`(Airbridge와 동일 인터페이스)를 신설하고, 타이틀별 메인 MMP를 선택하는 프로바이더 분기를 도입한다.

**Architecture:** `pipeline/sources/appsflyer.py`에 AppsFlyer Master API 기반 소스를 추가(동일 `CreativeMmpDaily` 생산). main.py의 하드코딩된 Airbridge 분기를 `make_mmp_source(cfg)` 팩토리로 교체. 등록부 `MMP 종류`로 메인 선택. 비용/노출 결측 시 분모 가드로 '—' 처리.

**Tech Stack:** Python 3.12, pytest, requests, openpyxl. AppsFlyer Master API(`master-agg-data/v4`, GET CSV).

## Global Constraints

- **항상 Google 제외** — AppsFlyer = 非Google MMP 레이어(현 2계층 모델). 기본 제외 media_source: `googleadwords_int`·`organic`·`none`·`""`.
- **메인만 수집·사용** — 두 MMP 공존 가능, `_pipeline_mmp_provider`로 메인 지정, 메인만 fetch. 비교 UI는 범위 밖.
- **동일 스키마** — 출력은 기존 `CreativeMmpDaily`(creative_name·date·channel·campaign_name·impressions·clicks·cost·installs·retained_d1·revenue_d7). 대시보드·품질지표 무변경.
- **분모 가드** — `cost<=0` → CPI·cost-ROAS null('—'), `impressions<=0` → IPM null. 파이프라인 + 대시보드 동일 규칙.
- **인증** — `APPSFLYER_API_TOKEN`(.env, 조직 단위). app_id는 타이틀별(등록부 `MMP 앱 식별자` → `_pipeline_appsflyer_app_id`).
- **하위호환** — `_pipeline_mmp_provider` 미설정 시 `airbridge_enabled` → "airbridge" 폴백(기존 펩 무변경).
- **v1 graceful 한계(합의)** — revenue는 활동기준(코호트 D7 정밀화 후속), `retained_d1=0`(D1 잔존 KPI는 라이브 검증 후 추가; 그동안 '—'). 분모 가드가 비용/노출 결측을 '—'로.
- **날짜 범위** — Master API ~3개월 제한 → ≤90일 청크(`MAX_CHUNK_DAYS=90`, Airbridge와 동일 패턴).
- **수동 실행** — PowerShell `$env:PYTHONUTF8=1; $env:PYTHONIOENCODING='utf-8'`, `.venv\Scripts\python.exe` 사용.

## File Structure

- Create `pipeline/sources/appsflyer.py` — `AppsFlyerMmpSource` + `extract_master`/`parse_master_rows`(HTTP 무의존) + 청크 fetch
- Modify `pipeline/main.py` — `make_mmp_source(cfg)` 팩토리 + 2.6 블록 분기 + resolve_config 배선(2 분기·cfg)
- Modify `pipeline/mmp_metrics.py` — `compute_mmp_quality` 분모 가드
- Modify `js/layer-metrics.js` — `mmpQualityMetrics`·`creativeLayerView` 분모 가드
- Modify `pipeline/registry.py` — `MMP 종류 == "appsflyer"` 분기
- Create `tests/test_appsflyer_source.py` — 파서·제외·graceful·청크
- Create `tests/test_mmp_provider.py` — `make_mmp_source` 선택자
- Modify `tests/test_mmp_score.py` — 분모 가드 단위테스트
- Modify `tests/test_registry.py` — appsflyer 매핑
- Create `docs/appsflyer-setup-guide.md` — 토큰 발급 안내

---

## Task 1: AppsFlyer 소스

**Files:**
- Create: `pipeline/sources/appsflyer.py`
- Test: `tests/test_appsflyer_source.py`

**Interfaces — Produces:**
- `extract_master(csv_text: str) -> list[dict]` — Master CSV → 정규화 dict 리스트
- `parse_master_rows(rows: list[dict], exclude: set, fx_rate: float=1.0) -> list[CreativeMmpDaily]`
- `class AppsFlyerMmpSource` — `from_env(app_id, usd_to_krw=1.0, exclude_media_sources=None)`, `fetch_mmp_window(start, end, exclude_channels=None) -> list[CreativeMmpDaily]`, 속성 `last_fetch_truncated`·`currency`·`usd_to_krw`·`MAX_CHUNK_DAYS=90`
- `DEFAULT_EXCLUDE_MEDIA_SOURCES = {"googleadwords_int","organic","none",""}`

---

- [ ] **Step 1: 테스트 작성** (`tests/test_appsflyer_source.py`)

```python
"""AppsFlyer MMP 소스 — 파서·제외·graceful·청크 단위테스트."""
from datetime import date
from pipeline.sources.appsflyer import (
    AppsFlyerMmpSource, extract_master, parse_master_rows,
    DEFAULT_EXCLUDE_MEDIA_SOURCES,
)


def test_extract_master_maps_headers():
    csv_text = "Ad,Media Source,Campaign,Date,Impressions,Clicks,Installs,Cost,Revenue\n" \
               "260616_VID_X,Facebook Ads,camp1,2026-06-20,1000,50,10,20.5,30.0\n"
    rows = extract_master(csv_text)
    assert len(rows) == 1
    r = rows[0]
    assert r["creative"] == "260616_VID_X"
    assert r["media_source"] == "Facebook Ads"
    assert r["campaign"] == "camp1"
    assert r["date"] == "2026-06-20"
    assert r["impressions"] == "1000"
    assert r["cost"] == "20.5"


def test_parse_master_basic_with_fx():
    rows = [{"creative": "A", "media_source": "facebook ads", "campaign": "c",
             "date": "2026-06-20", "impressions": "1000", "clicks": "50",
             "installs": "10", "cost": "20", "revenue": "30"}]
    out = parse_master_rows(rows, exclude=set(), fx_rate=1500.0)
    assert len(out) == 1
    d = out[0]
    assert d.creative_name == "A" and d.channel == "facebook ads"
    assert d.campaign_name == "c" and d.date == "2026-06-20"
    assert d.impressions == 1000 and d.clicks == 50 and d.installs == 10
    assert d.cost == 30000 and d.revenue_d7 == 45000   # ×fx
    assert d.retained_d1 == 0                            # v1


def test_parse_master_excludes_google_and_organic_and_empty():
    rows = [
        {"creative": "A", "media_source": "googleadwords_int", "date": "2026-06-20"},
        {"creative": "B", "media_source": "organic", "date": "2026-06-20"},
        {"creative": "", "media_source": "facebook", "date": "2026-06-20"},
        {"creative": "C", "media_source": "Facebook", "date": "2026-06-20", "installs": "5"},
    ]
    out = parse_master_rows(rows, exclude=set(DEFAULT_EXCLUDE_MEDIA_SOURCES))
    assert [d.creative_name for d in out] == ["C"]


def test_parse_master_graceful_missing_cost():
    # 설치>0·비용/노출 결측 → cost=0·impr=0, 설치·매출 보존 (분모 가드가 '—' 처리)
    rows = [{"creative": "A", "media_source": "facebook", "date": "2026-06-20",
             "installs": "10", "revenue": "5"}]
    out = parse_master_rows(rows, exclude=set())
    assert out[0].installs == 10 and out[0].revenue_d7 == 5
    assert out[0].cost == 0 and out[0].impressions == 0


def test_fetch_chunks_over_90_days_and_dedup():
    s = AppsFlyerMmpSource(token="x", app_id="y")
    calls = []
    csv_row = "Ad,Media Source,Date,Installs\nA,facebook,2026-06-20,3\n"

    def fake(cs, ce):
        calls.append((cs, ce))
        return csv_row
    s._fetch_master_csv = fake
    out = s.fetch_mmp_window(date(2025, 11, 1), date(2026, 5, 19), exclude_channels=set())
    assert len(calls) == 3
    assert calls[0] == (date(2025, 11, 1), date(2026, 1, 29))
    assert calls[1] == (date(2026, 1, 30), date(2026, 4, 29))
    assert calls[2] == (date(2026, 4, 30), date(2026, 5, 19))
    # 세 청크 모두 동일 (A,facebook,2026-06-20) → dedup → 1건
    assert len(out) == 1
```

- [ ] **Step 2: 실패 확인**

```bash
cd C:\claude\cloop_dashboard
.venv\Scripts\python.exe -m pytest tests/test_appsflyer_source.py -q 2>&1 | tail -8
```
기대: `ModuleNotFoundError: No module named 'pipeline.sources.appsflyer'`.

- [ ] **Step 3: 구현** (`pipeline/sources/appsflyer.py` 신규)

```python
# -*- coding: utf-8 -*-
"""AppsFlyer MMP Source — Stage 7 (두 번째 MMP 프로바이더).

Airbridge 와 동일 계약: fetch_mmp_window(start, end, exclude) -> list[CreativeMmpDaily].
v1 데이터 = Master API(master-agg-data/v4, GET CSV) 단일 호출: af_ad×pid×c×date 로
impressions·clicks·cost·installs·revenue. 날짜 범위 제한(~3개월) 회피 위해 ≤90일 청크.
파서(extract_master/parse_master_rows)는 HTTP 무의존 — 단위테스트. 원시 CSV 헤더 매핑은
라이브 검증(7-A 방식) 후 MASTER_HEADER_MAP·kpis 조정 가능.

⚠️ v1 graceful 한계(설계 합의): revenue 는 활동기준(코호트 D7 정밀화 후속),
retained_d1=0(→ '—'; 잔존 KPI 라이브 검증 후 추가). 분모 가드가 비용/노출 결측을 '—'로.
"""
from __future__ import annotations

import csv
import io
import os
import sys
from datetime import date, timedelta
from typing import Optional

import requests

from ..base_errors import AuthError, QuotaError
from ..schemas import CreativeMmpDaily

MASTER_BASE = "https://hq1.appsflyer.com/api/master-agg-data/v4/app"

# Google + 오가닉/내부 제외 (AppsFlyer media_source id 체계)
DEFAULT_EXCLUDE_MEDIA_SOURCES = {"googleadwords_int", "organic", "none", ""}

# Master API CSV 헤더 → 정규화 키 (라이브 검증 시 여기만 조정). 소문자·strip 후 매칭.
MASTER_HEADER_MAP = {
    "ad": "creative", "af_ad": "creative",
    "media source": "media_source", "pid": "media_source",
    "campaign": "campaign", "c": "campaign",
    "date": "date",
    "impressions": "impressions",
    "clicks": "clicks",
    "installs": "installs",
    "cost": "cost", "total cost": "cost",
    "revenue": "revenue", "total revenue": "revenue",
}


def _norm_header(h: str) -> str:
    key = (h or "").strip().lower()
    return MASTER_HEADER_MAP.get(key, key)


def _num(v) -> float:
    try:
        return float(str(v).replace(",", "").strip() or 0)
    except (ValueError, AttributeError):
        return 0.0


def extract_master(csv_text: str) -> list[dict]:
    """Master API CSV → 정규화 dict 리스트.

    키: creative·media_source·campaign·date·impressions·clicks·installs·cost·revenue (문자열).
    """
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    if not rows:
        return []
    header = [_norm_header(h) for h in rows[0]]
    out: list[dict] = []
    for raw in rows[1:]:
        if not raw:
            continue
        rec = {header[i]: raw[i] for i in range(min(len(header), len(raw)))}
        out.append(rec)
    return out


def parse_master_rows(rows: list[dict], exclude: set, fx_rate: float = 1.0) -> list[CreativeMmpDaily]:
    """정규화 dict 리스트 → CreativeMmpDaily. 빈 creative/제외 media_source skip.

    cost·revenue 에 fx_rate(USD→KRW) 적용. retained_d1=0(v1). revenue → revenue_d7.
    """
    out: list[CreativeMmpDaily] = []
    for r in rows:
        creative = (r.get("creative") or "").strip()
        ms = (r.get("media_source") or "").strip().lower()
        if not creative or ms in exclude:
            continue
        out.append(CreativeMmpDaily(
            creative_name=creative,
            date=(r.get("date") or "").strip(),
            channel=ms,
            campaign_name=(r.get("campaign") or "").strip(),
            impressions=int(round(_num(r.get("impressions")))),
            clicks=int(round(_num(r.get("clicks")))),
            cost=int(round(_num(r.get("cost")) * fx_rate)),
            installs=int(round(_num(r.get("installs")))),
            retained_d1=0,
            revenue_d7=int(round(_num(r.get("revenue")) * fx_rate)),
        ))
    return out


class AppsFlyerMmpSource:
    """AppsFlyer Master API 로 소재별 MMP 데이터 수집. (KpiSource ABC 미상속 — Airbridge 동일 정책)"""

    MAX_CHUNK_DAYS = 90  # Master API 날짜 범위 제한(~3개월) 회피

    def __init__(self, token: str, app_id: str, usd_to_krw: float = 1.0,
                 session=None, request_timeout: float = 120.0,
                 exclude_media_sources: Optional[set] = None):
        self.token = token
        self.app_id = app_id
        self.usd_to_krw = float(usd_to_krw or 1.0)
        self.session = session or requests.Session()
        self.request_timeout = request_timeout
        self.exclude = {s.lower() for s in (exclude_media_sources or DEFAULT_EXCLUDE_MEDIA_SOURCES)}
        self.last_fetch_truncated = False

    @property
    def currency(self) -> str:
        return "KRW" if self.usd_to_krw and self.usd_to_krw != 1.0 else "USD"

    @classmethod
    def from_env(cls, app_id: str, usd_to_krw: float = 1.0,
                 exclude_media_sources: Optional[set] = None) -> "AppsFlyerMmpSource":
        token = os.environ.get("APPSFLYER_API_TOKEN", "").strip()
        if not token:
            raise FileNotFoundError(
                "APPSFLYER_API_TOKEN 미설정. .env 에 추가하세요 (AppsFlyer 대시보드 > API Token V2.0)."
            )
        if not app_id:
            raise FileNotFoundError("AppsFlyer app_id 미설정 (등록부 'MMP 앱 식별자').")
        return cls(token=token, app_id=app_id, usd_to_krw=usd_to_krw,
                   exclude_media_sources=exclude_media_sources)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}", "accept": "text/csv"}

    @staticmethod
    def _raise_classified(e: Exception, resp_obj=None):
        code = getattr(resp_obj, "status_code", None)
        msg = str(e).lower()
        if code in (401, 403) or "401" in msg or "403" in msg or "unauthorized" in msg:
            raise AuthError(f"AppsFlyer 인증 실패: {e}")
        if code == 429 or "429" in msg or "too many" in msg:
            raise QuotaError(f"AppsFlyer rate limit: {e}")
        raise RuntimeError(f"AppsFlyer HTTP 오류: {e}")

    def _fetch_master_csv(self, start: date, end: date) -> str:
        """Master API GET → CSV 텍스트. (단위테스트에서 monkeypatch)"""
        url = f"{MASTER_BASE}/{self.app_id}"
        params = {
            "from": start.isoformat(), "to": end.isoformat(),
            "groupings": "af_ad,pid,c,date",
            # ⚠️ cost 가 calculated_kpis 여야 할 수 있음 — 라이브 검증(Task 5)에서 확정
            "kpis": "impressions,clicks,installs,cost,revenue",
            "format": "csv",
        }
        try:
            r = self.session.get(url, headers=self._headers(), params=params,
                                 timeout=self.request_timeout)
            r.raise_for_status()
        except Exception as e:
            self._raise_classified(e, resp_obj=locals().get("r"))
        return r.text

    def fetch_mmp_window(self, start: date, end: date,
                         exclude_channels: Optional[set] = None) -> list[CreativeMmpDaily]:
        """기간 내 Master API → CreativeMmpDaily. ≤90일 청크 분할·병합·dedup.

        dedup key = (creative_name, channel, campaign_name, date).
        """
        exclude = {s.lower() for s in exclude_channels} if exclude_channels else self.exclude
        out: list[CreativeMmpDaily] = []
        seen: set = set()
        self.last_fetch_truncated = False
        cs = start
        while cs <= end:
            ce = min(cs + timedelta(days=self.MAX_CHUNK_DAYS - 1), end)
            rows = extract_master(self._fetch_master_csv(cs, ce))
            for rec in parse_master_rows(rows, exclude, fx_rate=self.usd_to_krw):
                key = (rec.creative_name, rec.channel, rec.campaign_name, str(rec.date))
                if key not in seen:
                    seen.add(key)
                    out.append(rec)
            cs = ce + timedelta(days=1)
        return out
```

- [ ] **Step 4: 통과 확인**

```bash
cd C:\claude\cloop_dashboard
.venv\Scripts\python.exe -m pytest tests/test_appsflyer_source.py -q 2>&1 | tail -6
```
기대: 5 passed.

- [ ] **Step 5: 커밋**

```bash
cd C:\claude\cloop_dashboard
git add pipeline/sources/appsflyer.py tests/test_appsflyer_source.py
git commit -m "feat(appsflyer): AppsFlyerMmpSource — Master API 소재별 MMP 수집(파서·청크·graceful)"
```

---

## Task 2: 프로바이더 선택기 + main.py 배선

**Files:**
- Modify: `pipeline/main.py`
- Test: `tests/test_mmp_provider.py`

**Interfaces — Consumes:** `AppsFlyerMmpSource`(Task 1), `AirbridgeMmpSource`(기존)
**Interfaces — Produces:** `make_mmp_source(cfg: dict) -> tuple[object|None, str]` — (소스 인스턴스 또는 None, provider 문자열)

---

- [ ] **Step 1: 테스트 작성** (`tests/test_mmp_provider.py`)

```python
"""메인 MMP 프로바이더 선택자 단위테스트."""
import os
import pytest
from pipeline.main import make_mmp_source
from pipeline.sources.appsflyer import AppsFlyerMmpSource
from pipeline.sources.airbridge import AirbridgeMmpSource


def test_provider_appsflyer(monkeypatch):
    monkeypatch.setenv("APPSFLYER_API_TOKEN", "tok")
    src, provider = make_mmp_source(
        {"mmp_provider": "appsflyer", "appsflyer_app_id": "com.x", "airbridge_usd_to_krw": 1500})
    assert provider == "appsflyer"
    assert isinstance(src, AppsFlyerMmpSource)
    assert src.app_id == "com.x" and src.usd_to_krw == 1500


def test_provider_airbridge_explicit(monkeypatch):
    monkeypatch.setenv("AIRBRIDGE_API_TOKEN", "tok")
    monkeypatch.setenv("AIRBRIDGE_APP_NAME", "relicheros")
    src, provider = make_mmp_source({"mmp_provider": "airbridge"})
    assert provider == "airbridge"
    assert isinstance(src, AirbridgeMmpSource)


def test_provider_airbridge_fallback(monkeypatch):
    # mmp_provider 미설정 + airbridge_enabled=True → airbridge 폴백(하위호환)
    monkeypatch.setenv("AIRBRIDGE_API_TOKEN", "tok")
    monkeypatch.setenv("AIRBRIDGE_APP_NAME", "relicheros")
    src, provider = make_mmp_source({"airbridge_enabled": True})
    assert provider == "airbridge"
    assert isinstance(src, AirbridgeMmpSource)


def test_provider_none():
    src, provider = make_mmp_source({})
    assert src is None and provider == ""
```

- [ ] **Step 2: 실패 확인**

```bash
cd C:\claude\cloop_dashboard
.venv\Scripts\python.exe -m pytest tests/test_mmp_provider.py -q 2>&1 | tail -8
```
기대: `ImportError: cannot import name 'make_mmp_source'`.

- [ ] **Step 3: 구현 — `make_mmp_source` 추가** (`pipeline/main.py`, 2.6 블록 위 모듈 레벨)

`pipeline/main.py` 상단(다른 모듈 헬퍼 근처, 예: `_load_game_context` 정의 다음)에 추가:

```python
def make_mmp_source(cfg: dict):
    """cfg['mmp_provider'](또는 airbridge_enabled 폴백)로 메인 MMP 소스 선택.

    Returns: (source, provider). 미설정이면 (None, "").
    """
    provider = (cfg.get("mmp_provider") or "").strip().lower()
    if not provider:
        provider = "airbridge" if cfg.get("airbridge_enabled") else ""
    if provider == "appsflyer":
        from .sources.appsflyer import AppsFlyerMmpSource
        src = AppsFlyerMmpSource.from_env(
            app_id=cfg.get("appsflyer_app_id") or "",
            usd_to_krw=cfg.get("airbridge_usd_to_krw") or 1.0,
            exclude_media_sources=set(cfg["appsflyer_exclude_media_sources"])
            if cfg.get("appsflyer_exclude_media_sources") else None,
        )
        return src, provider
    if provider == "airbridge":
        from .sources.airbridge import AirbridgeMmpSource
        src = AirbridgeMmpSource.from_env()
        if cfg.get("airbridge_usd_to_krw"):
            src.usd_to_krw = cfg["airbridge_usd_to_krw"]
        return src, provider
    return None, ""
```

- [ ] **Step 4: 통과 확인**

```bash
cd C:\claude\cloop_dashboard
.venv\Scripts\python.exe -m pytest tests/test_mmp_provider.py -q 2>&1 | tail -6
```
기대: 4 passed.

- [ ] **Step 5: resolve_config 배선 (2 분기 + cfg)**

`pipeline/main.py` **override 분기**(현 `airbridge_usd_to_krw = float(title_override.get("_pipeline_airbridge_usd_to_krw", 0) or 0)` 다음 줄)에 추가:

```python
        mmp_provider = title_override.get("_pipeline_mmp_provider", "")
        appsflyer_app_id = title_override.get("_pipeline_appsflyer_app_id", "")
        appsflyer_exclude = title_override.get("_pipeline_appsflyer_exclude_media_sources", [])
```

`pipeline/main.py` **meta 분기**(현 `airbridge_usd_to_krw = float(title_meta.get("_pipeline_airbridge_usd_to_krw", 0) or 0)` 다음 줄)에 추가:

```python
        mmp_provider = title_meta.get("_pipeline_mmp_provider", "")
        appsflyer_app_id = title_meta.get("_pipeline_appsflyer_app_id", "")
        appsflyer_exclude = title_meta.get("_pipeline_appsflyer_exclude_media_sources", [])
```

cfg dict(현 `"airbridge_usd_to_krw": airbridge_usd_to_krw,` 다음 줄)에 추가:

```python
        "mmp_provider": mmp_provider,
        "appsflyer_app_id": appsflyer_app_id,
        "appsflyer_exclude_media_sources": appsflyer_exclude,
```

- [ ] **Step 6: 2.6 블록 프로바이더 분기로 교체**

`pipeline/main.py` 현 2.6 블록(`mmp_status = "skipped"` 부터 `metrics["mmp_status"] = mmp_status` 까지)을 아래로 교체:

```python
    # ── 2.6) Stage 7: MMP 페치 (Airbridge | AppsFlyer — 메인 프로바이더) ──
    mmp_status = "skipped"
    mmp_src, mmp_provider = make_mmp_source(cfg)
    if mmp_src is not None:
        try:
            from .sources.google_ads import resolve_window as _resolve_window
            _start, _end = _resolve_window(
                cfg.get("kpi_window_days") or 159, cfg.get("kpi_start_date") or None
            )
            # airbridge 는 채널 제외셋을 명시 전달, appsflyer 는 소스 내부 기본 제외셋 사용
            _exclude = set(cfg.get("airbridge_exclude_channels", [])) if mmp_provider == "airbridge" else None
            mmp_daily = mmp_src.fetch_mmp_window(_start, _end, exclude_channels=_exclude)
            cfg["_mmp_daily"] = mmp_daily
            cfg["_mmp_currency"] = mmp_src.currency
            cfg["_mmp_fx_rate"] = mmp_src.usd_to_krw
            cfg["_mmp_provider"] = mmp_provider
            mmp_status = "success_truncated" if mmp_src.last_fetch_truncated else "success"
            metrics["mmp_rows_fetched"] = len(mmp_daily)
            metrics["mmp_truncated"] = mmp_src.last_fetch_truncated
            metrics["mmp_provider"] = mmp_provider
            if mmp_src.last_fetch_truncated:
                metrics["errors"].append("MMP fetch 상한 도달 — 일부 소재 누락됨.")
            print(f"   → {mmp_provider} {len(mmp_daily)}행 fetch (非Google 매체, "
                  f"통화={mmp_src.currency} fx={mmp_src.usd_to_krw})")
        except FileNotFoundError:
            print(f"   💠 MMP({mmp_provider}): 토큰/앱ID 미설정 → 건너뜀")
            mmp_status = "skipped"
        except Exception as e:
            err_type = type(e).__name__
            print(f"\n⚠️  MMP fetch 실패 ({err_type}): {e} → mmp_* 비움, 진행 계속")
            metrics["errors"].append(f"MMP fetch 실패: {e}")
            mmp_status = "auth_failed" if err_type == "AuthError" else "failed"
    metrics["mmp_status"] = mmp_status
```

- [ ] **Step 7: import 무결성 + 회귀**

```bash
cd C:\claude\cloop_dashboard
.venv\Scripts\python.exe -c "from pipeline import main; print('import OK')"
.venv\Scripts\python.exe -m pytest tests/ -q 2>&1 | tail -6
```
기대: `import OK` + 전체 PASSED(기존 + appsflyer_source 5 + mmp_provider 4).

- [ ] **Step 8: 커밋**

```bash
cd C:\claude\cloop_dashboard
git add pipeline/main.py tests/test_mmp_provider.py
git commit -m "feat(mmp): make_mmp_source 팩토리 + 메인 프로바이더 분기(airbridge|appsflyer, 하위호환 폴백)"
```

---

## Task 3: 분모 가드 (비용/노출 결측 → '—')

**Files:**
- Modify: `pipeline/mmp_metrics.py:58-61`
- Modify: `js/layer-metrics.js:35-36`, `js/layer-metrics.js:94`
- Test: `tests/test_mmp_score.py`

**Interfaces — Consumes:** 기존 `compute_mmp_quality(agg)`

---

- [ ] **Step 1: 테스트 작성** (`tests/test_mmp_score.py` 에 추가)

```python
def test_compute_mmp_quality_impr_zero_ipm_none():
    from pipeline.mmp_metrics import compute_mmp_quality
    q = compute_mmp_quality({"impressions": 0, "cost": 1000, "installs": 10,
                             "retained_d1": 5, "revenue_d7": 2000})
    assert q["d1_ipm"] is None          # 노출 0 → IPM '—'


def test_compute_mmp_quality_cost_zero_cpi_none():
    from pipeline.mmp_metrics import compute_mmp_quality
    q = compute_mmp_quality({"impressions": 1000, "cost": 0, "installs": 10,
                             "retained_d1": 5, "revenue_d7": 0})
    assert q["d1_cpi"] is None          # 비용 0 → CPI '—'
    assert q["d7_roas"] is None         # 비용 0 → ROAS '—'
```

- [ ] **Step 2: 실패 확인**

```bash
cd C:\claude\cloop_dashboard
.venv\Scripts\python.exe -m pytest tests/test_mmp_score.py -q 2>&1 | tail -8
```
기대: `test_compute_mmp_quality_impr_zero_ipm_none` FAIL(현재 d1_ipm=0.0, None 아님).

- [ ] **Step 3: 파이프라인 가드** (`pipeline/mmp_metrics.py`)

찾을 문자열(58-59):
```python
    d1_ipm = (retained_d1 / impressions) * 1000 if impressions > 0 else 0.0
    d1_cpi: Optional[float] = (cost / retained_d1) if retained_d1 > 0 else None
```
교체:
```python
    d1_ipm: Optional[float] = (retained_d1 / impressions) * 1000 if impressions > 0 else None
    d1_cpi: Optional[float] = (cost / retained_d1) if (retained_d1 > 0 and cost > 0) else None
```
(d7_roas 는 이미 `cost > 0 else None` ✓. d1_retention 은 표시용이라 유지.)

- [ ] **Step 4: 대시보드 가드** (`js/layer-metrics.js`)

`mmpQualityMetrics` 찾을 문자열(35-36):
```javascript
      d1_ipm: a.imp > 0 ? (a.retained_d1 / a.imp) * 1000 : 0,
      d1_cpi: a.retained_d1 > 0 ? (a.cost / a.retained_d1) : null,
```
교체:
```javascript
      d1_ipm: a.imp > 0 ? (a.retained_d1 / a.imp) * 1000 : null,
      d1_cpi: (a.retained_d1 > 0 && a.cost > 0) ? (a.cost / a.retained_d1) : null,
```

`creativeLayerView` 의 CPA 찾을 문자열(94):
```javascript
        CPA: (m.mmp_installs > 0) ? (m.mmp_cost || 0) / m.mmp_installs : null,
```
교체:
```javascript
        CPA: (m.mmp_cost > 0 && m.mmp_installs > 0) ? m.mmp_cost / m.mmp_installs : null,
```
(IPM 95는 이미 `m.mmp_impressions > 0 ? ... : null` ✓. ROAS 는 precomputed `mmp_d7_roas`로 cost<=0시 null ✓.)

`js/layer-metrics.js` 의 캐시버스터 버전쿼리를 사용하는 페이지(step1_integrated.html·step2_clustering.html)의 `?v=` 문자열을 한 단계 올림(예 `20260623a` → `20260626a`) — JS 편집 반영용.

- [ ] **Step 5: 통과 확인**

```bash
cd C:\claude\cloop_dashboard
.venv\Scripts\python.exe -m pytest tests/test_mmp_score.py -q 2>&1 | tail -6
```
기대: 추가 2개 포함 전부 PASSED.

- [ ] **Step 6: 커밋**

```bash
cd C:\claude\cloop_dashboard
git add pipeline/mmp_metrics.py js/layer-metrics.js step1_integrated.html step2_clustering.html tests/test_mmp_score.py
git commit -m "fix(mmp): 분모 가드 — 비용/노출 0이면 CPI·IPM·ROAS '—'(AppsFlyer 비용결측 오표시 방지)"
```

---

## Task 4: 등록부 appsflyer 분기

**Files:**
- Modify: `pipeline/registry.py:91-96`
- Test: `tests/test_registry.py`

**Interfaces — Consumes:** 기존 `_map_row(row: dict, repo_root: Path) -> dict`

---

- [ ] **Step 1: 테스트 작성** (`tests/test_registry.py` 에 추가)

```python
def test_map_row_appsflyer_provider(tmp_path):
    from pipeline.registry import _map_row
    row = {
        "타이틀 ID": "gd-global", "타이틀명": "갓앤데몬", "로컬 스캔 경로": "G:\\x",
        "광고 성과 연동": "Y", "MMP 종류": "appsflyer",
        "MMP 앱 식별자": "com.com2us.gd.android.google.global.normal",
    }
    t = _map_row(row, tmp_path)
    assert t["_pipeline_mmp_provider"] == "appsflyer"
    assert t["_pipeline_appsflyer_app_id"] == "com.com2us.gd.android.google.global.normal"
    assert t["_pipeline_airbridge_usd_to_krw"] == 1500


def test_map_row_airbridge_sets_provider(tmp_path):
    from pipeline.registry import _map_row
    row = {"타이틀 ID": "pepp-us", "타이틀명": "펩", "로컬 스캔 경로": "G:\\x",
           "광고 성과 연동": "Y", "MMP 종류": "airbridge"}
    t = _map_row(row, tmp_path)
    assert t["_pipeline_mmp_provider"] == "airbridge"
    assert t["_pipeline_airbridge_enabled"] is True
```

- [ ] **Step 2: 실패 확인**

```bash
cd C:\claude\cloop_dashboard
.venv\Scripts\python.exe -m pytest tests/test_registry.py -q 2>&1 | tail -8
```
기대: `test_map_row_appsflyer_provider` FAIL(`KeyError: '_pipeline_mmp_provider'`).

- [ ] **Step 3: 구현** (`pipeline/registry.py`)

찾을 문자열(91-96):
```python
        mmp = (row.get("MMP 종류") or "").strip().lower()
        if mmp == "airbridge":
            t["_pipeline_airbridge_enabled"] = True
            t["_pipeline_airbridge_exclude_channels"] = list(_DEF_AB_EXCLUDE)
            t["_pipeline_airbridge_usd_to_krw"] = _DEF_USD_KRW
        # AppsFlyer: 소스 미구현 — 종류 보존만(범위 밖)
```
교체:
```python
        mmp = (row.get("MMP 종류") or "").strip().lower()
        if mmp == "airbridge":
            t["_pipeline_mmp_provider"] = "airbridge"
            t["_pipeline_airbridge_enabled"] = True
            t["_pipeline_airbridge_exclude_channels"] = list(_DEF_AB_EXCLUDE)
            t["_pipeline_airbridge_usd_to_krw"] = _DEF_USD_KRW
        elif mmp == "appsflyer":
            t["_pipeline_mmp_provider"] = "appsflyer"
            t["_pipeline_appsflyer_app_id"] = (row.get("MMP 앱 식별자") or "").strip()
            t["_pipeline_airbridge_usd_to_krw"] = _DEF_USD_KRW  # MMP fx(USD→KRW) 공용
```

- [ ] **Step 4: 통과 확인**

```bash
cd C:\claude\cloop_dashboard
.venv\Scripts\python.exe -m pytest tests/test_registry.py -q 2>&1 | tail -6
```
기대: 추가 2개 포함 전부 PASSED.

- [ ] **Step 5: 커밋**

```bash
cd C:\claude\cloop_dashboard
git add pipeline/registry.py tests/test_registry.py
git commit -m "feat(registry): MMP 종류 appsflyer 분기 — provider·app_id 매핑"
```

---

## Task 5: 라이브 검증 + 펩 회귀 + 셋업 가이드

**Files:**
- Create: `docs/appsflyer-setup-guide.md`
- (검증만 — 코드 변경 없음. 단, 라이브 검증 결과로 `_fetch_master_csv` kpis/`MASTER_HEADER_MAP` 조정 가능)

---

- [ ] **Step 1: 펩(Airbridge) 회귀 — 분모 가드 영향 확인** (토큰 불요, 지금 실행 가능)

```bash
cd C:\claude\cloop_dashboard
$env:PYTHONUTF8=1; $env:PYTHONIOENCODING='utf-8'
.venv\Scripts\python.exe -m pipeline.main --title pepp-us 2>&1 | Select-Object -Last 8
```
기대: 정상 완료, `airbridge N행 fetch`. → 산출 JSON의 mmp_quality_score 가 가드 전 대비 큰 붕괴 없는지 확인(비용/노출 0 행만 CPI/IPM '—'로 바뀜 = 의도된 개선):
```bash
.venv\Scripts\python.exe -c "import json; d=json.loads(open('public/data/pepp-us.json',encoding='utf-8-sig').read()); n=sum(1 for c in d['creatives'] if (c.get('mmp_quality_score') or {}).get('total') is not None); print('MMP 품질점수 보유 소재:', n)"
```
기대: 가드 전과 동일 수준(예 14건 내외) — 0으로 붕괴하지 않음.

- [ ] **Step 2: 대시보드 가드 — preview 확인** (step1)

dev 서버 기동 후 `step1_integrated.html?title=pepp-us` 로드 → MMP 레이어 전환 → 콘솔 오류 0 + 표의 CPA/IPM 가 비용/노출 없는 소재에서 '—' 로 표시되는지 스냅샷 확인. (펩은 대부분 비용 보유라 시각 변화 적을 수 있음 — 콘솔 0·정상 렌더가 핵심.)

- [ ] **Step 3: 셋업 가이드 작성** (`docs/appsflyer-setup-guide.md` 신규)

```markdown
# AppsFlyer MMP 연동 가이드

AppsFlyer를 메인 MMP로 쓰는 타이틀의 소재 성과를 대시보드에 연동합니다.

## 1. API 토큰 (담당자 1회)
1. AppsFlyer 대시보드 → 우상단 계정 → **Security Center → Manage your AppsFlyer API tokens**.
2. **API Token V2.0**(Bearer) 복사.
3. 프로젝트 `.env` 에 추가:
   ```
   APPSFLYER_API_TOKEN=복사한_토큰
   ```
   토큰은 조직 단위 1개로 계정 내 모든 앱에 사용됩니다.

## 2. 타이틀 등록 (등록부)
등록부 xlsx 에서:
- **MMP 종류** = `appsflyer`
- **MMP 앱 식별자** = AppsFlyer App ID (예 `com.com2us.rheroes.android.google.global.normal`, iOS 는 `id...`)
- **광고 성과 연동** = `Y`

> 한 타이틀에 Airbridge·AppsFlyer 둘 다 연동된 경우, **MMP 종류**가 메인을 정합니다.
> 메인만 매일 수집됩니다. 메인 전환은 MMP 종류 값을 바꾸면 됩니다(보조 식별자는 titles_overrides.json).

## 3. 동작 / 한계
- 수집: 소재(af_ad)×매체×캠페인×일자 — 노출·클릭·비용·설치·매출. **Google 매체는 항상 제외**(Google Ads는 별도 레이어).
- 비용/노출이 없는 기간·소재는 CPI·IPM·ROAS 가 '—'(설치·매출은 표시).
- v1 은 D1 잔존·코호트 D7 정밀화 미포함(후속).
```

- [ ] **Step 4: AppsFlyer 라이브 검증** (APPSFLYER_API_TOKEN 설정 후 — 토큰 없으면 이 스텝 보류)

> ⚠️ 빌드-어헤드: 토큰 미설정 시 nightly 는 graceful skip(`💠 MMP(appsflyer): 토큰/앱ID 미설정 → 건너뜀`). 아래는 토큰 확보 후 실행.

비용 집행이 살아있는 앱·기간을 찾아 소스를 직접 실행(검증 스크립트):
```python
# scripts/_verify_appsflyer.py (검증 후 삭제 가능 — _ 접두사로 gitignore 대상)
from datetime import date, timedelta
from pipeline.sources.appsflyer import AppsFlyerMmpSource
APP = "com.com2us.gd.android.google.global.normal"  # 비용 집행 확인된 앱으로 교체
src = AppsFlyerMmpSource.from_env(app_id=APP, usd_to_krw=1500)
end = date.today() - timedelta(days=1); start = end - timedelta(days=30)
rows = src.fetch_mmp_window(start, end)
print("행:", len(rows), "| cost>0:", sum(1 for r in rows if r.cost > 0),
      "| installs>0:", sum(1 for r in rows if r.installs > 0))
print("샘플:", rows[0] if rows else "없음")
```
```bash
cd C:\claude\cloop_dashboard
$env:PYTHONUTF8=1; .venv\Scripts\python.exe scripts/_verify_appsflyer.py
```
기대: 행>0, **cost>0 행 존재**(비용 완비 앱·기간), 소재명이 파이프라인 명명규칙과 일치. CSV 헤더가 `MASTER_HEADER_MAP` 와 다르거나 cost 가 0뿐이면 — `_fetch_master_csv` 의 `kpis`(cost→calculated_kpis) / `MASTER_HEADER_MAP` 를 응답에 맞게 조정 후 재실행. MCP `fetch_aggregated_data`(소재 단위)로 기대값 교차 대조.

- [ ] **Step 5: 커밋**

```bash
cd C:\claude\cloop_dashboard
git add docs/appsflyer-setup-guide.md
git commit -m "docs(appsflyer): MMP 연동 셋업 가이드 + 라이브 검증"
git push origin main
```

---

## 검증 체크리스트

- [ ] `pytest tests/test_appsflyer_source.py` 5개 PASSED(파서·제외·graceful·청크)
- [ ] `pytest tests/test_mmp_provider.py` 4개 PASSED(appsflyer·airbridge·폴백·none)
- [ ] `pytest tests/test_mmp_score.py` 가드 2개 PASSED
- [ ] `pytest tests/test_registry.py` appsflyer 2개 PASSED
- [ ] 전체 `pytest tests/` 무회귀 + `from pipeline import main` import OK
- [ ] 펩(Airbridge) 재실행 무붕괴(분모 가드 영향 = 비용/노출 0 행만 '—')
- [ ] step1 MMP 레이어 preview 콘솔 0
- [ ] (토큰 확보 시) AppsFlyer 라이브 cost>0 행 검증 + 명명규칙 일치
