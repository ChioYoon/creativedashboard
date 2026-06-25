# 캐시 carry-forward + 도원암귀 점진 재태깅 설계 스펙

작성 2026-06-25 · 브레인스토밍 합의 기반.

---

## 0. 한 줄 요약

무료 Gemini quota(RPD ~20)로는 전량 재태깅을 하루에 못 하므로, **태깅 안 된 소재가 출력에서 드롭되지 않고 이전 버전 태그를 유지(carry-forward)** 하도록 파이프라인을 보강한 뒤, **도원암귀 버전핀을 제거**해 며칠에 걸쳐 안전하게 dark-fantasy로 점진 수렴시킨다.

---

## 1. 배경 · 문제

- 장르별 instruction·게임 컨텍스트를 적용하려면 **재태깅**이 필요(캐시 키 = `sha::prompt_version`, 버전 바뀌면 전량 무효화).
- **무료 quota 한도(RPD ~20/일)** 로는 도원암귀 28 + 펩 70 ≈ 98건을 하루에 재태깅 불가.
- **현재 파이프라인은 현재 버전으로 태깅 안 된 소재를 출력에서 드롭** (`main.py` 태깅 루프 `daily_quota_exhausted` 시 `skipped_quota += 1; continue` → `records` 미append). → 버전 bump 후 며칠 점진 재태깅 시 그 기간 동안 대시보드가 붕괴(2026-06-24 펩 70→3 사고와 동일 원인).
- 유료 전환(빌링)은 비용이 작으나(전량 ≈ 수백 원) **회사 정책상 어려움** → 무료 유지.

---

## 2. 확정 결정 (브레인스토밍 Q&A)

| 항목 | 결정 |
|------|------|
| quota 경로 | **무료 유지** (유료 빌링 어려움) |
| 재태깅 범위 | **도원암귀 먼저** (잘못된 무협 태그 → dark-fantasy 교정, ~2일 수렴). 펩 게임 컨텍스트는 이후 별도 |
| 안전장치 | **carry-forward** — 미태깅 소재는 드롭 대신 이전 버전 태그 유지 (공통 인프라) |

---

## 3. 아키텍처

```
도원암귀 _pipeline_prompt_version_pin 제거
   → prompt_version = darkfantasy-v1 (현 캐시엔 production 엔트리 없음 → 전량 miss)

매 nightly (main.py 태깅 루프):
   for 소재:
     cache.get(sha, darkfantasy-v1)
       ├─ hit → 사용
       └─ miss:
            quota 남음 → Gemini 태깅(darkfantasy-v1) → 캐시 저장   [매일 ~20건 전환]
            quota 소진 → cache.get_any(sha)  (이전 non-pilot 버전 태그)
                          ├─ 있음 → 그 태그로 record 생성 (carried_forward++)  [드롭 안 함]
                          └─ 없음(신규) → skip
   → 출력 = 전환된 dark-fantasy 태그 + carry-forward된 구 태그 = 항상 28건 유지
   → 며칠 반복 → carried_forward 0 → 전량 dark-fantasy 수렴
```

---

## 4. 컴포넌트 상세

### 4-A. `TagCache.get_any(sha)` (`pipeline/cache.py`)

```python
def get_any(self, sha: str, exclude_version: str | None = None) -> tuple[dict, str] | None:
    """같은 파일(sha)의 이전 버전 태그 폴백. non-pilot 버전 중 최신(버전 문자열 max).
    현재 버전 캐시가 없을 때 carry-forward 용. 없으면 None."""
    prefix = f"{sha}::"
    best_ver, best_payload = None, None
    for key, payload in self._data.items():
        if not key.startswith(prefix):
            continue
        ver = key[len(prefix):]
        if ver.endswith("-pilot"):      # 파일럿 테스트 엔트리 제외
            continue
        if exclude_version and ver == exclude_version:
            continue
        if best_ver is None or ver > best_ver:   # 버전 문자열 lexical max ≈ 최신
            best_ver, best_payload = ver, payload
    return (best_payload, best_ver) if best_ver is not None else None
```

### 4-B. main.py 태깅 루프 carry-forward (`pipeline/main.py`)

현행(line ~731):
```python
            if daily_quota_exhausted:
                skipped_quota += 1
                continue
```
변경:
```python
            if daily_quota_exhausted:
                fb = cache.get_any(sha, exclude_version=pversion)
                if fb is not None:
                    tag_dict, _fb_ver = fb
                    carried_forward += 1
                    # 드롭하지 않고 아래 record append 로 진행
                else:
                    skipped_quota += 1
                    continue
            else:
                try:
                    ... (현행 태깅 try/except 블록 그대로) ...
```
- `carried_forward = 0` 을 `skipped_quota = 0` 근처(line ~711)에 초기화.
- carry-forward 시 `tag_dict` 가 채워져 기존 `records.append(...)` 흐름을 그대로 탐(드롭 방지).
- **구조 주의:** 현행 `else:`(miss) 블록 안에 quota 분기와 태깅 try/except 가 함께 있음 — quota-skip 분기만 carry-forward 로 교체하고, 태깅 try/except(폴백 모델 재시도 포함)는 변경하지 않음.

### 4-C. 도원암귀 재태깅 트리거 (`js/titles.json`)

`tougenanki` 항목에서 **`_pipeline_prompt_version_pin` 제거**:
```json
"_pipeline_genre": "dark_fantasy_card_rpg",
"_pipeline_game_context_file": "pipeline/game_context/tougenanki.md",
"drive_folder_url": "..."
```
(핀 줄 삭제 → `prompt_version("dark_fantasy_card_rpg")` = `v3.3-...-darkfantasy-v1` 적용)

> ⚠️ 타이틀 셀프 등록 등록부가 활성화된 경우, 이 변경은 `js/titles_overrides.json` 의 tougenanki 항목에서 핀을 제거하는 것으로 갈음(등록부가 titles.json 을 덮어쓰므로). 현재는 등록부 미활성(수동 titles.json)이라 titles.json 직접 수정.

### 4-D. 수렴 모니터링

- 실행 요약(`✅ 완료`)과 metrics dict 에 **`carried_forward`** 추가 출력 (현행 `캐시 히트`·`quota 보류` 옆).
- 이메일(notify) 에도 노출되면 좋으나, 최소 콘솔/metrics 만으로 충분(범위: 콘솔 + metrics dict).
- 운영자는 매일 `carried_forward` 가 줄어드는지 확인 → **0 = 도원암귀 전량 dark-fantasy 수렴 완료.**

---

## 5. 범위 밖 (이후 별도)

- **펩 게임 컨텍스트 재태깅**: carry-forward 인프라가 준비되므로, 원할 때 펩 버전 bump(예: char-rpg suffix 부여)만 하면 동일하게 안전 점진 수렴. (이번 회차 미실시 — 펩 현 태그 양호)
- 유료 전환(빌링) — 회사 정책상 보류.
- AppsFlyer·멀티타이틀 MMP 등 무관 항목.

---

## 6. 테스트 전략

| # | 검증 | 방법 |
|---|------|------|
| T1 | `get_any` — 같은 sha 이전 버전 태그 반환(최신), pilot 제외, 없으면 None | 단위테스트(여러 버전 캐시 fixture) |
| T2 | `get_any` — exclude_version 동작 | 단위테스트 |
| T3 | 태깅 루프: quota 소진 + 이전 태그 있음 → carry-forward(record 유지, carried_forward++) | 단위테스트(quota 소진 mock + 캐시 fixture) 또는 함수 분리 후 테스트 |
| T4 | quota 소진 + 이전 태그 없음(신규) → skip | 단위테스트 |
| T5 | 도원암귀 핀 제거 → prompt_version = darkfantasy-v1 | titles.json 확인 + `prompt_version("dark_fantasy_card_rpg")` 단위 |
| T6 | 기존 태깅 테스트 무회귀 | `pytest tests/` |

> T3·T4 는 main.py 태깅 루프가 큰 함수라, **carry-forward 판정 로직을 작은 헬퍼로 추출**해 단위테스트(권장). 추출 어려우면 cache.get_any(T1·T2)로 핵심 보장 + 루프 변경은 코드리뷰로.

---

## 7. 구현 범위 (이번 회차)

- [ ] `pipeline/cache.py`: `TagCache.get_any(sha, exclude_version=None)` + 단위테스트(T1·T2)
- [ ] `pipeline/main.py`: 태깅 루프 quota-skip → carry-forward 분기 + `carried_forward` 카운트/출력
- [ ] `js/titles.json`: 도원암귀 `_pipeline_prompt_version_pin` 제거
- [ ] (가능 시) carry-forward 판정 헬퍼 추출 + T3·T4
- [ ] 전체 테스트 무회귀(T6)
