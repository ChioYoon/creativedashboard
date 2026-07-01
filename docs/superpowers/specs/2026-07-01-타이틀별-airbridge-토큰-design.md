# 타이틀별 Airbridge 토큰 지원 설계

**작성일:** 2026-07-01
**대상:** `pipeline/main.py`(`resolve_config`·`make_mmp_source`), `tests/`
**요구:** 제우스 Airbridge가 펩(relicheros)과 **다른 계정/토큰**이라, 파이프라인이 타이틀별로 다른 Airbridge API 토큰을 쓸 수 있어야 함.

## 현황

- `AirbridgeMmpSource.from_env()`(`pipeline/sources/airbridge.py:112`): **단일** `AIRBRIDGE_API_TOKEN` + `AIRBRIDGE_APP_NAME` 사용.
- `make_mmp_source(cfg)`(`main.py:118`): airbridge 분기에서 `from_env()` 후 **app_name만** per-title 오버라이드(`src.app_name = cfg["airbridge_app_name"]`). 토큰은 공유.
- 진단: 제우스 앱 `zeuskr`가 펩 계정(Com2us_RMKT org)에 없음(404). 제우스는 **별도 Airbridge 계정 = 별도 토큰**(사용자 확인).

## 설계 — env 변수 컨벤션

타이틀별 토큰을 **`AIRBRIDGE_API_TOKEN_<타이틀ID>`** env 변수로. 없으면 기존 `AIRBRIDGE_API_TOKEN`으로 폴백.
- 제우스 → **`AIRBRIDGE_API_TOKEN_ZEUS`**.
- 접미사 규칙: 타이틀 id의 영숫자 외 문자는 `_`로 치환 후 대문자. `zeus`→`ZEUS`, `pepp-us`→`PEPP_US`.
- 앱 이름은 기존대로 titles.json `_pipeline_airbridge_app_name`(zeus=`zeuskr`).

### 신규 헬퍼 (테스트 용이)
```python
def _resolve_airbridge_token(title: str, env: dict | None = None) -> str:
    env = env if env is not None else os.environ
    suffix = "".join(c if c.isalnum() else "_" for c in (title or "")).upper()
    return (env.get(f"AIRBRIDGE_API_TOKEN_{suffix}", "") or env.get("AIRBRIDGE_API_TOKEN", "")).strip()
```

### resolve_config
`title` 확정(`if not title: sys.exit`, 494) 후 `return {` 앞에:
```python
    airbridge_token = _resolve_airbridge_token(title)
```
cfg dict에 추가(`"airbridge_app_name": airbridge_app_name,` 다음):
```python
        "airbridge_token": airbridge_token,
```

### make_mmp_source
airbridge 분기(`main.py:121-122`)에서 app_name 오버라이드 다음:
```python
        if cfg.get("airbridge_token"):
            src.token = cfg["airbridge_token"]   # per-title Airbridge 토큰 (별도 계정 — .env 단일토큰 오버라이드)
```

## 하위호환

- 기존 타이틀(펩)은 `AIRBRIDGE_API_TOKEN_PEPP_US`가 없으므로 기본 `AIRBRIDGE_API_TOKEN` 사용 → **완전 무변경**.
- `airbridge_token`은 항상 값이 있음(기본 폴백) → `if cfg.get("airbridge_token")`는 사실상 항상 참이나, 값이 빈 경우 방어.

## 보안

- **코드만 작성. 토큰 값은 사용자가 `.env`에 직접 입력**(`AIRBRIDGE_API_TOKEN_ZEUS=<값>`). 나는 값을 읽거나 출력하지 않음(키 존재/길이만 확인).

## 적용 순서 (범위 밖 = 후속 단계)

1. 본 코드 반영(+테스트).
2. 사용자가 `.env`에 `AIRBRIDGE_API_TOKEN_ZEUS` 추가.
3. zeus MMP 재활성화(titles.json `_pipeline_mmp_provider="airbridge"`·`_pipeline_airbridge_enabled=true` 복원) + 파이프라인 실행 → 검증(`zeuskr` 앱명 정합·MMP 행 수).

## 비목표

- 앱 이름 자동 검증(실행 시 403/404로 확인).
- AppsFlyer per-title 토큰(현재 단일 `APPSFLYER_API_TOKEN`, 필요 시 동일 패턴 후속).

## 검증

- 단위 테스트 `tests/test_airbridge_token.py`:
  1. `_resolve_airbridge_token("zeus", {"AIRBRIDGE_API_TOKEN_ZEUS":"ztok","AIRBRIDGE_API_TOKEN":"deftok"})` == `"ztok"` (per-title 우선).
  2. `_resolve_airbridge_token("pepp-us", {"AIRBRIDGE_API_TOKEN":"deftok"})` == `"deftok"` (폴백).
  3. 접미사 정규화: `pepp-us` → `AIRBRIDGE_API_TOKEN_PEPP_US` 조회.
  4. 공백 trim.
- 전체 pytest 무회귀.
