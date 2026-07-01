# 타이틀별 Airbridge 토큰 지원 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 파이프라인이 타이틀별로 다른 Airbridge 토큰(`AIRBRIDGE_API_TOKEN_<ID>`, 폴백 `AIRBRIDGE_API_TOKEN`)을 쓰게 한다. 제우스(별도 계정) 연동 준비.

**Architecture:** `pipeline/main.py`에 `_resolve_airbridge_token` 헬퍼 + `resolve_config`가 cfg에 주입 + `make_mmp_source`가 `src.token` 오버라이드. 앱 이름은 기존 titles.json.

**Tech Stack:** Python. pytest.

## Global Constraints

- 하위호환: `AIRBRIDGE_API_TOKEN_<ID>` 없으면 기존 `AIRBRIDGE_API_TOKEN` 사용 → 펩 무변경.
- 토큰 값은 사용자가 .env에 입력. 코드는 env 변수명만 안다.
- 접미사: 타이틀 id 영숫자 외 → `_`, 대문자.

---

### Task 1: per-title Airbridge 토큰

**Files:** Modify `pipeline/main.py`(`make_mmp_source` 근처 헬퍼 · `resolve_config` 494/542 · `make_mmp_source` 121), Create `tests/test_airbridge_token.py`.

- [ ] **Step 1: 헬퍼 추가**

`def make_mmp_source(cfg: dict):`(101) **앞**에 추가:
```python
def _resolve_airbridge_token(title: str, env: "dict | None" = None) -> str:
    """타이틀별 Airbridge 토큰: AIRBRIDGE_API_TOKEN_<ID> 우선, 없으면 기본 AIRBRIDGE_API_TOKEN."""
    env = env if env is not None else os.environ
    suffix = "".join(c if c.isalnum() else "_" for c in (title or "")).upper()
    return (env.get(f"AIRBRIDGE_API_TOKEN_{suffix}", "") or env.get("AIRBRIDGE_API_TOKEN", "")).strip()


```

- [ ] **Step 2: make_mmp_source 토큰 오버라이드**

`main.py:121-122`(airbridge app_name 오버라이드) 다음에 추가:
```python
        if cfg.get("airbridge_app_name"):
            src.app_name = cfg["airbridge_app_name"]   # per-title Airbridge 앱 (멀티타이틀 — .env 단일앱 오버라이드)
        if cfg.get("airbridge_token"):
            src.token = cfg["airbridge_token"]   # per-title Airbridge 토큰 (별도 계정 — .env 단일토큰 오버라이드)
```

- [ ] **Step 3: resolve_config 토큰 주입**

`return {`(514) **앞**(빈 줄, line 513 근처)에 추가:
```python
    airbridge_token = _resolve_airbridge_token(title)

```
cfg dict의 `"airbridge_app_name": airbridge_app_name,`(542) 다음에 추가:
```python
        "airbridge_token": airbridge_token,
```

- [ ] **Step 4: 단위 테스트**

Create `tests/test_airbridge_token.py`:
```python
from pipeline.main import _resolve_airbridge_token


def test_per_title_token_priority():
    env = {"AIRBRIDGE_API_TOKEN_ZEUS": "ztok", "AIRBRIDGE_API_TOKEN": "deftok"}
    assert _resolve_airbridge_token("zeus", env) == "ztok"


def test_fallback_to_default():
    env = {"AIRBRIDGE_API_TOKEN": "deftok"}
    assert _resolve_airbridge_token("zeus", env) == "deftok"
    assert _resolve_airbridge_token("pepp-us", env) == "deftok"


def test_suffix_normalization():
    env = {"AIRBRIDGE_API_TOKEN_PEPP_US": "ptok", "AIRBRIDGE_API_TOKEN": "deftok"}
    assert _resolve_airbridge_token("pepp-us", env) == "ptok"


def test_empty_when_none_set():
    assert _resolve_airbridge_token("zeus", {}) == ""


def test_trims_whitespace():
    assert _resolve_airbridge_token("zeus", {"AIRBRIDGE_API_TOKEN_ZEUS": "  ztok  "}) == "ztok"
```

- [ ] **Step 5: 테스트 실행**

Run: `PYTHONUTF8=1 PYTHONPATH=/c/claude/cloop_dashboard python -m pytest tests/test_airbridge_token.py -q`
Expected: 5 passed.

- [ ] **Step 6: 전체 회귀**

Run: `PYTHONUTF8=1 PYTHONPATH=/c/claude/cloop_dashboard python -m pytest -q --ignore=tests/test_mmp_score.py --ignore=tests/test_registry.py`
Expected: 이전 92 + 5 = 97 passed.

- [ ] **Step 7: Commit**
```bash
git add pipeline/main.py tests/test_airbridge_token.py
git commit -m "feat(pipeline): 타이틀별 Airbridge 토큰 지원 (AIRBRIDGE_API_TOKEN_<ID>)"
```

---

## 실행 메모
- 코드 반영 후 사용자가 `.env`에 `AIRBRIDGE_API_TOKEN_ZEUS` 추가 → zeus MMP 재활성화 + 실행은 **후속 단계**(이 플랜 밖).
