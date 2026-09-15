# 게임 성격 맥락 주입 — AI 인사이트·성과 보고서 (설계)

> 일자: 2026-09-15 | 브랜치: `claude/suspicious-ardinghelli-8a844a`
> 목적: AI 분석기(인사이트·보고서)가 "이게 무슨 게임인지" 알고 소재를 해석하도록 브랜드/게임 성격 맥락을 주입.

## 1. 문제

현재 두 AI 기능이 게임 맥락 없이 태그·수치만으로 분석한다.

- **AI 인사이트** (`scoringInsight`): `context` 인자를 받도록 설계돼 있으나 **호출부(step1 ~8780)에서 전달하지 않음** → 게임 맥락 0.
- **성과 보고서** (`buildReportNarrativePrompt`): `_extractUaContext`로 `game_context/{tid}.md`의 **UA 전략~금기(§4-5)만** 슬라이스. 브랜드 특성·핵심 루프·게임성(§1-3)은 **의도적 제외**("로어 유입 방지").

결과: 보고서 프롬프트가 "태그명만 나열 금지, 화면 묘사로 서술"을 요구해도 게임이 뭘 하는 게임인지 몰라 근거가 약하다.

## 2. 접근

**원본 md 통짜(§1-2 로어) 주입은 하지 않는다** — 원래 코드가 피한 것이 옳다(토큰 낭비·분석 희석). 대신 **`brand_briefs.json`이 이미 그 압축 distillation**(장르·톤·소구·캐릭터, 로어 제거). 이를 맥락으로 주입한다.

- 실효: **전 타이틀·무료 키에서 즉시**(맥락은 입력 토큰이라 무료 출력 예산 2000 잠식 없음. 보고서는 이미 1500자 UA 맥락 주입 중).
- 폐기: 이전에 검토한 "가드/금지선 주입"은 게이트 IP 집행 후에나 실효 → 제외. IP 제약은 제작 브리프 모달이 이미 담당.

## 3. 유닛

### 3-1. `GeminiPrompts.buildGameCharacterContext(bb)` (신규, 순수, gemini-api.js)

- 입력: brand_briefs 엔트리 객체(`window._brandBriefs[tid]`). falsy면 `''`.
- 출력: 압축 텍스트 블록(존재 필드만, ~400자 상한):
  ```
  [게임 성격 — 분석 배경. 소재가 무엇을 소구하는지 해석에만 사용, 데이터 판단이 우선]
  - 장르/핵심 루프: <genre>            (선택 필드)
  - 브랜드 톤: <tone>
  - 핵심 소구: <core_appeals>          (선택 필드)
  - CTA 톤: <cta_tone>
  - 등장 캐릭터: <characters 상위 절단>
  ```
- 규칙: 필드 없으면 해당 줄 생략. slogan은 이미 인사이트/보고서서 별도 사용하므로 제외(중복 방지). 전체 400자 초과 시 말미 절단.

### 3-2. 인사이트 주입 (step1 ~8780)

```js
const bb = (window._brandBriefs && window._brandBriefs[tid]) || null;
const gameCtx = GeminiPrompts.buildGameCharacterContext(bb);
const prompts = GeminiPrompts.scoringInsight(highPerf, lowPerf, { tagCols, isPaid, context: gameCtx });
```
- `context`는 이미 프롬프트에 삽입됨(gemini-api.js:551). 삽입 위치가 "배경 맥락"으로 읽히는지 확인, 필요 시 라벨 보강.

### 3-3. 보고서 주입 (step1 generateSummaryReport → buildReportNarrativePrompt)

- `buildReportNarrativePrompt(data, tags, note, sharedContext, gameChar)` — 파라미터 1개 추가.
- 프롬프트에 기존 `[게임/UA 컨텍스트]` 블록 **앞에** `[게임 성격]` 블록 삽입. 둘은 성격이 다름(성격=무엇을 소구하는 게임 / UA=전략·금기).
- `generateSummaryReport`에서 `gameChar = GeminiPrompts.buildGameCharacterContext(bb)` 생성 후 전달.

### 3-4. 데이터 보강 (brand_briefs.json — 선택 필드)

전 타이틀에 `tone`·`cta_tone`·`characters`는 이미 존재 → 데이터 추가 없이 기본 동작. "장르·핵심 루프·소구 우선순위"를 위해 **선택 필드 2종을 실 출처에서 소싱해 추가**:
- `genre`: 한 줄 장르/핵심 루프.
- `core_appeals`: 핵심 소구 축(우선순위순).
- 소싱: 도원암귀=`brief_tougenanki.json`(fact.genre / usp[]). 제우스=`pipeline/game_context/zeus.md`. gd·pepp-us=후속 백필(없으면 줄 생략, graceful).
- 원칙: **날조 금지** — 실 출처 없는 타이틀은 추가하지 않음.

## 4. 데이터 흐름

```
step1 로드 → window._brandBriefs (기존)
  ├─ 인사이트: tid→bb→buildGameCharacterContext→ scoringInsight(opts.context)
  └─ 보고서:   tid→bb→buildGameCharacterContext→ buildReportNarrativePrompt(gameChar)
```
gemini-api.js 프롬프트 빌더는 순수 유지(window 접근 없음, 맥락을 인자로 수령 — 기존 `sharedContext` 패턴 동일).

## 5. 회귀·안전

- 순수 가산: 신규 함수 1 + 인자 전달. 점수·등급·피로도·제외추천 무관(KPI 기반).
- graceful: bb 없거나 필드 없으면 빈 블록 → 기존 동작 그대로.
- 무료 키: 맥락은 입력 토큰. 출력 예산(2000) 잠식 없음. 인사이트 winning 슬롯 서술이 게임 맥락으로 강화됨.
- 프롬프트 문자열 변경이라 파싱 스키마(슬롯 키) 불변 → parseScoringSlots/parseReport 무영향.

## 6. 테스트

- `buildGameCharacterContext`: 빈 bb→'', 필드 유무별 줄 포함/생략, 400자 상한, 캐릭터 절단. gemini-api.js에 인라인 self-check(기존 `__main__` 패턴 없으면 pytest 아님 → JS라 브라우저 javascript_tool 검증 또는 노드 미사용 → 수동 assert 함수).
- 통합: 인사이트/보고서 프롬프트 문자열에 게임 성격 블록이 bb 있을 때 포함, 없을 때 미포함(브라우저 javascript_tool로 buildProductionBrief 검증했던 방식 재사용).

## 7. 스코프 밖 (YAGNI)

- 가드/금지선 주입(게이트 IP 집행 후 재검토).
- 보고서 theme_primary 분포 vs 소구 우선순위 대조 섹션(제우스 usp 데이터 부재 + 도원암귀 미집행 → 현재 무용).
- gd·pepp-us genre/core_appeals 백필(줄 생략으로 graceful, 데이터 확보 시 추가).
