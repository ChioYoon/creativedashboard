# 캠페인 타입 필터 (Phase 2) — 설계 문서

**작성일**: 2026-06-26
**선행**: Phase 1 — Google Ads 전환 기준 캐노니컬화 (`pipeline/campaign_canonical.py` 구축 완료)
**관련**: `docs/superpowers/specs/2026-06-26-google-ads-전환기준-캐노니컬-design.md`

## 목표

캠페인명에서 추출한 캐노니컬 필드(ua_type/country/os/media/product)를 파이프라인 출력 JSON에 저장하고, step1·라이브 대시보드에 캠페인 유형별 필터를 추가하여 **동질 비교**(사전예약만/설치캠만, 지역·OS·매체·상품별)를 가능하게 한다.

## 비목표 (YAGNI)

- 한글 라벨맵(NU-Pre→사전예약 등) — 조직 컨벤션대로 원시 코드 노출
- date(캠페인 시작일) 범위 필터
- agency/executor 필터
- 세그먼트 나란히-비교(side-by-side) 뷰
- LTV 프로젝트 소관인 media→media_group 룩업·country/product 마스터 정규화

→ 추후 필요 시 별도 Phase.

## 아키텍처 (A안: 파이프라인 top-level 맵 + 캠페인명 집합 선택기)

```
파이프라인 (campaign_canonical.py + main.py)
  └ 고유 campaign_name 수집 → 필드별 추출 → campaign_canonical 맵
       {campaign_name: {ua_type, country, os, media, product}}
            │  (CreativeDataset 새 top-level 키)
            ▼
  public/data/{title}.json  ── 맵 1개, 캠페인당 1행(일별 행마다 반복 X)
            │
            ▼
대시보드 (step1 / live)
  └ 맵 로드 → 캐노니컬 필터 UI 5종 → 선택값을 campaign_name 집합으로 변환
       → step1: 기존 KPI-swap(gcamps)에 교집합 주입
       → live : 기존 Set 필터 게이트에 주입
```

**원칙**: 파이썬 파서를 유일한 진실 소스로 둔다. 라이브의 기존 JS `parseCountry`/`parseOS`가 검증한 로직을 Python으로 이식하여 라이브 출력과 동일하게 유지(무회귀)하면서 중복/드리프트를 제거한다.

### 필드별 추출 전략 (positional 한계 보완)

| 필드 | 방법 | 근거 |
|---|---|---|
| `ua_type` | 기존 `campaign_ua_type`(token 정확일치, NU-Pre 우선) 재사용 | Phase 1에서 positional 불안정 확인 → token 채택 |
| `country` | 신규 `campaign_country`: `XX-XX`(예: US-EN) 정규식 스캔 후 `-` 앞부분 | 라이브 JS `parseCountry`와 동일 로직 이식 |
| `os` | 신규 `campaign_os`: ios/aos/android/web 토큰 스캔 → iOS/Android/Web | 라이브 JS `parseOS`와 동일 로직 이식 |
| `media` | positional(`parse_campaign_canonical["media"]`) best-effort | 검증된 JS 등가물 없음 |
| `product` | positional(`parse_campaign_canonical["product"]`) best-effort | 검증된 JS 등가물 없음 |

추출 실패 시 빈 문자열(`""`) → 대시보드가 **`미상`** 버킷으로 처리(절대 행 제외 안 함).

## 컴포넌트 상세

### C1. 파이프라인 — `pipeline/campaign_canonical.py`

견고 추출 헬퍼 2개 + 맵 빌더 1개 추가 (기존 `parse_campaign_canonical`·`campaign_ua_type` 유지):

```python
_COUNTRY_RE = re.compile(r"^[A-Z]{2,4}-[A-Z]{2}$")   # US-EN, CA-FR …
_OS_MAP = {"ios": "iOS", "aos": "Android", "android": "Android", "web": "Web"}

def campaign_country(name: str) -> str:
    """캠페인명에서 country 추출 — XX-XX 세그먼트 스캔 후 '-' 앞부분. 없으면 ''."""
    # segs를 순회하며 _COUNTRY_RE 첫 매칭의 prefix 반환

def campaign_os(name: str) -> str:
    """캠페인명에서 os 추출 — 토큰 소문자 매칭 → iOS/Android/Web. 없으면 ''."""
    # segs 소문자화하여 _OS_MAP 첫 매칭 반환

def build_campaign_canonical(campaign_names) -> dict:
    """고유 campaign_name → {ua_type, country, os, media, product}.
       빈 문자열은 누락 표시(대시보드가 '미상' 처리). 빈 입력 → {}."""
    out = {}
    for cn in {c for c in campaign_names if c}:
        pos = parse_campaign_canonical(cn)
        out[cn] = {
            "ua_type": campaign_ua_type(cn),
            "country": campaign_country(cn),
            "os":      campaign_os(cn),
            "media":   pos["media"] or "",
            "product": pos["product"] or "",
        }
    return out
```

### C2. 파이프라인 — `pipeline/schemas.py`

`CreativeDataset`에 top-level 필드 추가 (`metrics` 다음):

```python
campaign_canonical: dict = Field(default_factory=dict,
                                 description="campaign_name→캐노니컬 필드 맵")
```

Pydantic 모델이므로 `model_dump(by_alias=True)`가 자동 직렬화. 기본값 `{}`로 하위호환.

### C3. 파이프라인 — `pipeline/main.py`

`CreativeDataset(...)` 생성 직전(~line 1011):
- `creatives`의 `kpi_daily` + `mmp_daily` 행에서 모든 `campaign_name` 수집(set)
- `build_campaign_canonical(names)` → `campaign_canonical=...` 인자 전달
- 기존 쓰기 경로(`model_dump` → `json.dumps` → `write_text`) 그대로

**비용/영향**: 순수 문자열 파싱, 추가 API 호출 0. KPI 미연동 타이틀(도원암귀)은 campaign_name이 없어 맵 `{}`.

### C4. 대시보드 — `step1_integrated.html` (기존 KPI-swap 재활용)

- 캠페인 필터 패널 위에 **"캠페인 유형"** 섹션 신설 — 5개 접이식 체크박스 그룹(ua_type/country/os/media/product), 기존 `populateCampaignFilter` UI 스타일 그대로.
- 신규 `resolveCanonicalCampaigns()`: 선택된 캐노니컬 값 → 충족 campaign_name 집합 반환(차원 간 AND, 차원 내 OR). 누락값은 `미상` 버킷.
- 이 집합을 기존 `currentCampaign`/`gcamps` 흐름에 **교집합**으로 주입 → 기존 `aggGadsWindow`/`aggMmpWindow`(이미 `campaign_name` 필터링)가 그대로 동작. **집계 로직 변경 0.**
- 캐노니컬 필터 변경 시 하단 캠페인 체크박스 목록도 해당 집합으로 좁혀 표시(일관성).

### C5. 대시보드 — `live_dashboard.js`

- `LIVE.canon = dataset.campaign_canonical || {}` 로드.
- `allDailies()`의 `LIVE.parseCountry/parseOS` 호출 → `LIVE.canon[cn]?.country/os` 조회로 교체(파서 일원화). **폴백은 조회 단위** — `LIVE.canon[cn]`의 country/os 값이 비어있거나(`""`) 해당 campaign_name 항목 자체가 없으면 그 행에 한해 기존 JS 파서 사용(구 JSON 전체 부재·부분 누락 모두 동일 경로로 무회귀).
- `buildFilters()`에 ua_type/media/product 동적 체크박스 추가(기존 countries/oses/campaigns 옆), `applyFilters()`에 동일 Set 게이트 3개 추가.
- 트렌드 그래프·그리드 모두 `applyFilters()` 경유라 자동 반영.

**라벨**: ua_type 등 원시 코드(NU-Pre/RT/AOS…) 조직 컨벤션대로 노출.

## 필터 동작 규칙 (공통)

- 차원 간 **AND**, 차원 내 **OR** (예: `ua_type∈{NU-Pre}` AND `country∈{US,JP}`).
- 빈 선택 = 필터 미적용(전체 표시) — 기존 패턴 일치.
- 누락값(`""`)은 **`미상`** 버킷으로 표시, 절대 제외 안 함.

## 에러 처리 / 하위호환

| 상황 | 동작 |
|---|---|
| 구 JSON(`campaign_canonical` 키 부재) | step1: 캐노니컬 필터 섹션 **숨김**. live: country/os **기존 JS 파서 폴백**, ua_type/media/product 필터 미표시. 무크래시·무회귀. |
| 필드 누락/미파싱(`""`) | **`미상`** 버킷, 행 제외 안 함 |
| KPI 미연동 타이틀(도원암귀) | 맵 `{}` → "구 JSON" 경로와 동일 |
| 빈 선택 | 필터 미적용(전체), 기존 패턴 일치 |

## 테스트

### 파이프라인 (pytest, `tests/test_campaign_canonical.py` 확장)
- `campaign_country`: `HQ_HQ_PH_US-EN_GA_NU_AD_ACA-PU_260429 → "US"`, `XX-XX` 미존재 → `""`.
- `campaign_os`: `aos→Android`, `ios→iOS`, `web→Web`, 토큰 미존재 → `""`.
- `build_campaign_canonical`: dedup(중복 campaign_name 1행), 미상(`""`) 케이스, 5필드 구조, 빈/None 입력 → `{}`.
- 회귀: 기존 78 테스트 + `campaign_ua_type` 견고성(NU-Pre≠NU, 미파싱→install 분기) 유지.

### 대시보드 (수동/preview — 정적 HTML, JS 테스트 하니스 없음)
- 맵 포함 JSON 로드 → 캐노니컬 필터 5종 채워짐 확인.
- ua_type=NU-Pre 선택 → step1 KPI-swap·live 그리드/트렌드가 해당 캠페인만 반영.
- `미상` 버킷 동작 확인.
- 구 JSON(맵 없음) 로드 → step1 필터 숨김·live JS 폴백, 무크래시 확인.
- 스크린샷으로 증빙.

### 실측 회귀
- pepp/gd JSON 재생성 후 맵 존재·필터 채움 확인(파이프라인 재실행은 quota/수동 — 맵 빌더는 샘플 campaign_name 리스트로 격리 단위테스트 가능).

## 파일 변경 요약

| 파일 | 변경 |
|---|---|
| `pipeline/campaign_canonical.py` | `campaign_country`·`campaign_os`·`build_campaign_canonical` 추가 |
| `pipeline/schemas.py` | `CreativeDataset.campaign_canonical` 필드 추가 |
| `pipeline/main.py` | campaign_name 수집 + `build_campaign_canonical` 호출·전달 |
| `step1_integrated.html` | 캐노니컬 필터 섹션 + `resolveCanonicalCampaigns()` + KPI-swap 주입 |
| `js/live-dashboard.js` | `LIVE.canon` 로드, 파서 일원화(폴백 유지), 필터 3종 추가 |
| `tests/test_campaign_canonical.py` | 신규 헬퍼·맵 빌더 테스트 확장 |
