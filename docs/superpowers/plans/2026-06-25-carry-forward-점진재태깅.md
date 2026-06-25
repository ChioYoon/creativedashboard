# 캐시 carry-forward + 도원암귀 점진 재태깅 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** quota 소진으로 현재 버전 태깅이 안 된 소재를 출력에서 드롭하지 않고 이전 버전 태그를 유지(carry-forward)하도록 보강한 뒤, 도원암귀 버전핀을 제거해 며칠에 걸쳐 안전하게 dark-fantasy로 점진 수렴시킨다.

**Architecture:** `TagCache.get_any(sha)`가 같은 파일의 이전 non-pilot 버전 태그를 폴백 제공. `main.py` 태깅 루프의 quota-skip 지점이 드롭 대신 `get_any` 폴백으로 record를 유지(`carried_forward` 카운트). 도원암귀 `_pipeline_prompt_version_pin` 제거가 재태깅을 트리거.

**Tech Stack:** Python 3.12, pytest. 무료 Gemini(RPD ~20)·기존 캐시 구조(`cache/{title}_tags.json`, 키 `sha::version`).

## Global Constraints

- carry-forward는 **태깅 루프의 `daily_quota_exhausted` 스킵 지점에서만** 적용(quota 남으면 정상 태깅).
- `get_any`는 **`-pilot` 로 끝나는 버전 제외**, 같은 sha의 non-pilot 버전 중 **버전 문자열 lexical max**(≈최신) 반환, 없으면 `None`.
- carry-forward 시 record를 정상 생성(드롭 금지) + `carried_forward` 증가. 정말 아무 non-pilot 버전도 없으면(신규) 그때만 `skipped_quota` + skip.
- 도원암귀 트리거 = `js/titles.json` 의 tougenanki `_pipeline_prompt_version_pin` 제거 → `prompt_version("dark_fantasy_card_rpg")` = `v3.3-2026.06.13-character-split-single-darkfantasy-v1`.
- 기존 태깅/스코어 로직 무회귀. `--pilot` 검증은 production JSON 미오염(`{title}.pilot.json`), 검증 후 정리(미커밋).

---

## 파일 맵

| 파일 | 변경 |
|------|------|
| `pipeline/cache.py` | `TagCache.get_any(sha, exclude_version=None)` 추가 |
| `tests/test_cache.py` (신규) | get_any 단위테스트 |
| `pipeline/main.py` | 태깅 루프 carry-forward 분기 + `carried_forward` init/metrics/요약 |
| `js/titles.json` | 도원암귀 `_pipeline_prompt_version_pin` 제거 (트리거) |

---

## Task 1: `TagCache.get_any` + 단위테스트

**Files:**
- Modify: `pipeline/cache.py`
- Create: `tests/test_cache.py`

**Interfaces — Produces:**
- `TagCache.get_any(self, sha: str, exclude_version: str | None = None) -> tuple[dict, str] | None`

---

- [ ] **Step 1: 테스트 작성** (`tests/test_cache.py`)

```python
"""TagCache.get_any (carry-forward 폴백) 단위 테스트."""
from pipeline.cache import TagCache


def test_get_any_returns_latest_non_pilot(tmp_path):
    c = TagCache(tmp_path, "t")
    c.put("sha1", "v3.0-2026.06.10", {"x": 1})
    c.put("sha1", "v3.3-2026.06.13", {"x": 2})
    c.put("sha2", "v3.0-2026.06.10", {"y": 9})
    res = c.get_any("sha1")
    assert res is not None
    payload, ver = res
    assert ver == "v3.3-2026.06.13"
    assert payload == {"x": 2}


def test_get_any_excludes_pilot(tmp_path):
    c = TagCache(tmp_path, "t")
    c.put("sha1", "v3.3-2026.06.13", {"x": 2})
    c.put("sha1", "v9.9-zzz-pilot", {"x": 99})   # pilot 제외 → v3.3 선택
    payload, ver = c.get_any("sha1")
    assert ver == "v3.3-2026.06.13"
    assert payload == {"x": 2}


def test_get_any_exclude_version(tmp_path):
    c = TagCache(tmp_path, "t")
    c.put("sha1", "v3.0-2026.06.10", {"x": 1})
    c.put("sha1", "v3.3-2026.06.13", {"x": 2})
    payload, ver = c.get_any("sha1", exclude_version="v3.3-2026.06.13")
    assert ver == "v3.0-2026.06.10"
    assert payload == {"x": 1}


def test_get_any_none_when_no_match(tmp_path):
    c = TagCache(tmp_path, "t")
    c.put("sha1", "v3.3-2026.06.13", {"x": 2})
    assert c.get_any("nope") is None


def test_get_any_none_when_only_pilot(tmp_path):
    c = TagCache(tmp_path, "t")
    c.put("sha1", "v1-pilot", {"x": 1})
    assert c.get_any("sha1") is None   # pilot만 있으면 폴백 없음
```

- [ ] **Step 2: 실패 확인**

```bash
cd C:\claude\cloop_dashboard
.venv\Scripts\python.exe -m pytest tests/test_cache.py -q 2>&1 | tail -12
```
기대: `AttributeError: 'TagCache' object has no attribute 'get_any'`

- [ ] **Step 3: `get_any` 구현** (`pipeline/cache.py`)

`TagCache` 클래스의 `get` 메서드(line ~69-71) 바로 다음에 추가:
```python
    def get_any(
        self, sha: str, exclude_version: str | None = None
    ) -> Optional[tuple[dict, str]]:
        """같은 파일(sha)의 이전 버전 태그 폴백 (carry-forward 용).
        non-pilot 버전 중 버전 문자열 lexical max(≈최신) 반환. 없으면 None.
        """
        prefix = f"{sha}::"
        best_ver: Optional[str] = None
        best_payload: Optional[dict] = None
        for key, payload in self._data.items():
            if not key.startswith(prefix):
                continue
            ver = key[len(prefix):]
            if ver.endswith("-pilot"):
                continue
            if exclude_version is not None and ver == exclude_version:
                continue
            if best_ver is None or ver > best_ver:
                best_ver, best_payload = ver, payload
        if best_ver is None:
            return None
        return (best_payload, best_ver)
```
(`Optional`, `tuple` 은 이미 `from typing import Optional` 존재 — `tuple` 은 내장.)

- [ ] **Step 4: 통과 확인**

```bash
cd C:\claude\cloop_dashboard
.venv\Scripts\python.exe -m pytest tests/test_cache.py -q 2>&1 | tail -8
```
기대: 5개 PASSED.

- [ ] **Step 5: 커밋**

```bash
cd C:\claude\cloop_dashboard
git add pipeline/cache.py tests/test_cache.py
git commit -m "feat(cache): TagCache.get_any — 이전 버전 태그 폴백(carry-forward)"
```

---

## Task 2: main.py carry-forward 배선 + 도원암귀 트리거

**Files:**
- Modify: `pipeline/main.py`
- Modify: `js/titles.json`

**Interfaces — Consumes:** `TagCache.get_any(sha, exclude_version=None)` (Task 1)

---

- [ ] **Step 1: `carried_forward` 초기화** (`pipeline/main.py` line ~711)

찾을 문자열:
```python
    skipped_quota = 0  # quota 소진으로 이번 실행에서 건너뛴 캐시 미스 항목 (다음 실행 시 자동 재시도)
```
바로 다음 줄에 추가:
```python
    carried_forward = 0  # quota 소진 시 이전 버전 태그를 유지(carry-forward)한 소재 수
```

- [ ] **Step 2: 태깅 루프 carry-forward 분기** (`pipeline/main.py` line 731~788)

⚠️ 이 편집은 quota-skip 분기를 carry-forward로 교체하고, 기존 `try/except` 블록을 `else:` 아래로 **4칸 들여쓰기**한다. 아래 **전체 블록**을 그대로 교체할 것.

찾을 문자열(현행 731-788 전체):
```python
            if daily_quota_exhausted:
                skipped_quota += 1
                continue
            try:
                # Stage 5-I: 풀 분포 + 이 소재 실제 KPI 백분위를 동적 컨텍스트로 주입
                tag = tagger.tag_creative(rep, extra_context=build_extra_context(c.creative_name), genre=genre)
                tag_dict = tag.model_dump()
                cache.put(sha, pversion, tag_dict)
                cache.save()
                misses += 1
            except Exception as e:
                err_msg = str(e)
                # ── quota 한도 도달 시 flash-lite 폴백 (Stage 4 신규) ──
                is_quota_exhausted = (
                    "GenerateRequestsPerDayPer" in err_msg
                    or ("429" in err_msg and "quota" in err_msg.lower())
                )
                if (
                    is_quota_exhausted
                    and not cfg["no_fallback"]
                    and not metrics["fallback_used"]
                ):
                    tqdm.write(
                        f"   [폴백] {cfg['model']} quota 한도 → "
                        f"{fallback_model} 으로 전환하여 재시도"
                    )
                    cfg["model"] = fallback_model
                    _carry_usage = dict(tagger.usage)  # 1차 태거 토큰 실측 이어받기
                    tagger = GeminiTagger(api_key=cfg["api_key"], model=fallback_model)
                    for _k, _v in _carry_usage.items():
                        tagger.usage[_k] += _v
                    metrics["fallback_used"] = True
                    daily_quota_exhausted = False
                    # 같은 소재 재시도 (Stage 5-I: 동일 컨텍스트 주입)
                    try:
                        tag = tagger.tag_creative(rep, extra_context=build_extra_context(c.creative_name), genre=genre)
                        tag_dict = tag.model_dump()
                        cache.put(sha, pversion, tag_dict)
                        cache.save()
                        misses += 1
                    except Exception as e2:
                        tqdm.write(f"   [실패] {c.creative_name} (폴백 후): {e2}")
                        failures += 1
                        continue
                elif is_quota_exhausted and metrics["fallback_used"]:
                    # 폴백 모델도 한도 도달 — 이후 Gemini 호출은 스킵하되
                    # 캐시 히트 항목은 계속 처리 (break 금지: 산출 JSON 퇴보 방지)
                    tqdm.write(
                        f"   [quota] {c.creative_name}: 폴백 모델 quota도 한도 도달 — "
                        f"이후 신규 태깅은 건너뛰고 캐시 항목만 처리"
                    )
                    skipped_quota += 1
                    daily_quota_exhausted = True
                    continue
                else:
                    tqdm.write(f"   [실패] {c.creative_name}: {e}")
                    failures += 1
                    continue
```
교체 후:
```python
            if daily_quota_exhausted:
                # carry-forward: 현재 버전 미태깅이라도 이전 버전 태그가 있으면 유지(드롭 방지)
                fb = cache.get_any(sha, exclude_version=pversion)
                if fb is not None:
                    tag_dict, _fb_ver = fb
                    carried_forward += 1
                else:
                    skipped_quota += 1
                    continue
            else:
                try:
                    # Stage 5-I: 풀 분포 + 이 소재 실제 KPI 백분위를 동적 컨텍스트로 주입
                    tag = tagger.tag_creative(rep, extra_context=build_extra_context(c.creative_name), genre=genre)
                    tag_dict = tag.model_dump()
                    cache.put(sha, pversion, tag_dict)
                    cache.save()
                    misses += 1
                except Exception as e:
                    err_msg = str(e)
                    # ── quota 한도 도달 시 flash-lite 폴백 (Stage 4 신규) ──
                    is_quota_exhausted = (
                        "GenerateRequestsPerDayPer" in err_msg
                        or ("429" in err_msg and "quota" in err_msg.lower())
                    )
                    if (
                        is_quota_exhausted
                        and not cfg["no_fallback"]
                        and not metrics["fallback_used"]
                    ):
                        tqdm.write(
                            f"   [폴백] {cfg['model']} quota 한도 → "
                            f"{fallback_model} 으로 전환하여 재시도"
                        )
                        cfg["model"] = fallback_model
                        _carry_usage = dict(tagger.usage)  # 1차 태거 토큰 실측 이어받기
                        tagger = GeminiTagger(api_key=cfg["api_key"], model=fallback_model)
                        for _k, _v in _carry_usage.items():
                            tagger.usage[_k] += _v
                        metrics["fallback_used"] = True
                        daily_quota_exhausted = False
                        # 같은 소재 재시도 (Stage 5-I: 동일 컨텍스트 주입)
                        try:
                            tag = tagger.tag_creative(rep, extra_context=build_extra_context(c.creative_name), genre=genre)
                            tag_dict = tag.model_dump()
                            cache.put(sha, pversion, tag_dict)
                            cache.save()
                            misses += 1
                        except Exception as e2:
                            tqdm.write(f"   [실패] {c.creative_name} (폴백 후): {e2}")
                            failures += 1
                            continue
                    elif is_quota_exhausted and metrics["fallback_used"]:
                        # 폴백 모델도 한도 도달 — 이후 Gemini 호출은 스킵하되
                        # 캐시 히트 항목은 계속 처리 (break 금지: 산출 JSON 퇴보 방지)
                        tqdm.write(
                            f"   [quota] {c.creative_name}: 폴백 모델 quota도 한도 도달 — "
                            f"이후 신규 태깅은 건너뛰고 캐시 항목만 처리"
                        )
                        skipped_quota += 1
                        daily_quota_exhausted = True
                        continue
                    else:
                        tqdm.write(f"   [실패] {c.creative_name}: {e}")
                        failures += 1
                        continue
```

- [ ] **Step 3: metrics + 요약 출력에 carried_forward 추가**

metrics dict(line ~930) — `"fallback_used": metrics["fallback_used"],` 다음 줄에 추가:
```python
            "carried_forward": carried_forward,
```
요약 출력(line ~950) — `skipped_quota` print 다음에 추가:
```python
    if carried_forward:
        print(f"   carry-forward: {carried_forward}건 (이전 버전 태그 유지 — 재태깅 수렴 중)")
```

- [ ] **Step 4: import + 회귀 테스트**

```bash
cd C:\claude\cloop_dashboard
.venv\Scripts\python.exe -c "from pipeline import main; print('import OK')"
.venv\Scripts\python.exe -m pytest tests/ -q 2>&1 | tail -6
```
기대: `import OK` + 전체 테스트 PASSED(test_cache 5 + test_registry 12 + test_tagger_genre 12 등).

- [ ] **Step 5: `--pilot` 로 carry-forward 통합 검증 (도원암귀)**

> production JSON 미오염(`tougenanki.pilot.json`). 오늘 quota가 거의 소진된 상태라 carry-forward 가 실제로 발동될 가능성이 큼. **핵심: 출력이 28건으로 유지(드롭 없음)** 되는지 확인.

```bash
cd C:\claude\cloop_dashboard
$env:PYTHONUTF8=1; $env:PYTHONIOENCODING='utf-8'
.venv\Scripts\python.exe -m pipeline.main --title tougenanki --pilot 2>&1 | Select-Object -Last 14
.venv\Scripts\python.exe -c "import json; d=json.loads(open('public/data/tougenanki.pilot.json',encoding='utf-8-sig').read()); print('pilot creatives:', len(d.get('creatives',[])))"
Remove-Item public/data/tougenanki.pilot.json -ErrorAction SilentlyContinue
```
기대: 요약에 `carry-forward N건`(quota 소진 시) + `pilot creatives: 28`(드롭 없이 전량 유지). **만약 28보다 크게 작으면(예: 3) carry-forward 미동작 — 분기 재점검.** (quota가 남아 전량 태깅됐다면 carry-forward 0 + 28건도 정상.)

- [ ] **Step 6: carry-forward 커밋**

```bash
cd C:\claude\cloop_dashboard
git add pipeline/main.py
git commit -m "feat(main): 태깅 루프 carry-forward — quota 소진 소재는 이전 버전 태그 유지(드롭 방지)"
```

- [ ] **Step 7: 도원암귀 재태깅 트리거 — 핀 제거** (carry-forward 검증 후)

`js/titles.json` 의 tougenanki 항목에서 핀 줄 삭제.

찾을 문자열:
```json
    "_pipeline_game_context_file": "pipeline/game_context/tougenanki.md",
    "_pipeline_prompt_version_pin": "v3.3-2026.06.13-character-split-single",
    "drive_folder_url": "https://drive.google.com/drive/folders/1N3lnsfKTeiYLfT-OWwZ1aI-ou74u9pDJ"
```
교체 후:
```json
    "_pipeline_game_context_file": "pipeline/game_context/tougenanki.md",
    "drive_folder_url": "https://drive.google.com/drive/folders/1N3lnsfKTeiYLfT-OWwZ1aI-ou74u9pDJ"
```

- [ ] **Step 8: 트리거 확인 + 커밋 + push**

```bash
cd C:\claude\cloop_dashboard
.venv\Scripts\python.exe -c "import json; d=json.load(open('js/titles.json',encoding='utf-8')); t=[x for x in d if x['id']=='tougenanki'][0]; print('pin:', t.get('_pipeline_prompt_version_pin','(제거됨)'))"
git add js/titles.json
git commit -m "feat(retag): 도원암귀 버전핀 제거 — darkfantasy-v1 점진 재태깅 트리거"
git push origin main
```
기대: `pin: (제거됨)`, push 성공.

---

## 검증 체크리스트 (완료 기준)

- [ ] `pytest tests/test_cache.py -v` 5개 PASSED (get_any: 최신 non-pilot·pilot제외·exclude·None)
- [ ] 전체 `pytest tests/` 무회귀
- [ ] `--pilot` 도원암귀 출력 **28건 유지**(드롭 없음), carry-forward 카운트 노출
- [ ] 도원암귀 `_pipeline_prompt_version_pin` 제거 확인 + push
- [ ] (이후) 다음 nightly부터 `carried_forward` 가 매일 줄어 **0 → 전량 dark-fantasy 수렴**(~2일, 운영자 모니터링)
