# ROAS 모드 저매출·비변별 스코어링 교정 설계 (B + C)

**작성일:** 2026-07-06

## Goal

소재 스코어링에서 **ROAS가 무의미한데도 총점을 부풀리는** 문제를 두 가지로 교정한다.
- **B (목표 연동):** 자동 모드에서 캠페인 전환기준이 `사전예약`이면 ROAS를 제외(`off`)한다 — Level 2 컬럼 dim과 일치.
- **C (비변별 교정):** ROAS가 소재 간 변별력이 없으면(전원 동점) ROAS를 제외·재배분한다.

## 배경 / 진단 (확정 증거)

`calculateCreativeScores`(step1_integrated.html:4731)는 rank 기반으로 각 지표를 0~100 점수화한다. zeus(사전예약) 실측:
- 파이프라인이 노이즈 수준 매출(₩15~173)을 7/9 소재에 넣어 `revenueRatio`=78% > 30% → 자동 모드가 `strict` 선택.
- 전 소재 ROAS가 극미(0~0.000086)하고 tie 임계(`< 0.0001`) 안에 들어 **전원 동점 → 전원 ROASRank=1 → 전원 ROAS점수=100**.
- `roasWeight`=0.25 → **모든 총점이 일괄 +25점 인플레이션**. 상대 순위는 불변이나 절대 총점·등급(최우수 ≥80)이 과다.

근본 원인: (1) 자동 임계가 매출 "보유 개수"만 보고 "규모/변별성"은 안 봄. (2) rank 스코어링이 "전원 동점(=비변별)"을 rank 1(=100점)으로 부여.

## 접근

B와 C 모두 **`effectiveRoasMode = 'off'`로 수렴**시켜, 기존 off 재배분 로직(4767-4778: roasWeight를 나머지 3지표에 비례 재배분)을 재사용한다. 신규 스코어링 경로를 만들지 않는다.

### B — 목표 연동 (auto + 사전예약 → off)

`calculateCreativeScores`의 auto 판정(4756-4764) 첫 분기에 추가:
- `detectConversionBasis() === '사전예약'`이면 `effectiveRoasMode = 'off'` (기존 no-revenue/30% 분기보다 우선).
- **auto 모드에만 적용.** 사용자가 수동으로 엄격/공정/제외를 고르면 그 선택을 존중.
- `window._roasMeta.offReason = 'prereg'`로 사유 기록.

### C — 비변별 ROAS 제외 (모든 ROAS-랭크 경로)

ROAS가 랭크될 모집단에서 **전원 동점(비변별)** 이면 `effectiveRoasMode='off'`로 전환. 재배분(4767) **직전**에 삽입(그래야 기존 재배분·off 스코어링이 그대로 동작).
- 비변별 판정 헬퍼 `roasIsNonDiscriminating(pop)`: `pop`의 ROAS를 오름차순 정렬 후 **인접 차이가 모두 tie 임계(`0.0001`) 미만**이면 `true`(= assignRankWithTies가 전원 rank 1을 부여하는 조건과 동일).
- 모집단: `effectiveRoasMode==='exclude'`면 매출>0 소재, 아니면 전체(strict/auto→strict).
- 조건: `effectiveRoasMode !== 'off' && roasWeight > 0 && pop.length > 0 && roasIsNonDiscriminating(pop)` → `effectiveRoasMode='off'`, `window._roasMeta.offReason='nondiscriminating'`.
- **수동 모드 포함** 적용(모드 선택이 아니라 정확성 교정).

### 파생 — off 안내 메시지 사유별 정정

기존 off 메시지(5235-5237)는 "매출 데이터 부재" 하나뿐. `_roasMeta.offReason`에 따라 분기:
- `prereg` → "사전예약 캠페인 → ROAS 제외 (전환·CPA·IPM으로 평가)"
- `nondiscriminating` → "ROAS 값이 소재 간 변별력 없음 → 제외·재배분"
- `norevenue`(기존) → "매출 데이터 부재 → ROAS 가중치 자동 재배분"

no-revenue 분기(4758)에도 `offReason='norevenue'` 기록.

## 변경 대상

- `step1_integrated.html`:
  - auto 블록(4756-4764) — B 분기 + offReason 기록.
  - 재배분 직전(4766 앞) — C 헬퍼 호출 + effectiveRoasMode 전환.
  - `roasIsNonDiscriminating` 헬퍼 신규(calculateCreativeScores 내부 또는 인접).
  - off 안내 메시지(5230-5245) — offReason 분기.

## Error Handling / Edge Cases

- `detectConversionBasis` 미정의/맵 없음 → `typeof` 가드, 기본 '설치' → B 미발동(안전).
- `roasWeight`=0(사용자가 ROAS 가중치 0) → B/C 무의미(이미 ROAS 미반영), 재배분 조건(`roasWeight>0`)으로 스킵.
- 매출이 실제로 변별되는 타이틀 → `roasIsNonDiscriminating`=false → 무변화(회귀 없음).
- exclude 모드에서 매출>0 소재가 1개 → 그 1개는 자동으로 "전원 동점"(단일 원소) → C가 off로 전환(합리적: 1개로는 ROAS 변별 불가).

## Testing / Verification

preview MCP(브라우저):
1. **zeus(사전예약)**: 분석 실행 → `_roasMeta.effectiveMode==='off'`, `offReason==='prereg'`, redistributed=true. 전 소재 ROAS점수가 총점에 미반영(이전 +25 인플레 제거) — 최우수 수/총점이 이전보다 정상화.
2. **비변별 강제 케이스**: (zeus에서 수동 '엄격' 선택해도) C가 비변별 감지 → off 전환 확인.
3. **회귀(변별 타이틀)**: 매출이 실제 변별되는 타이틀(예: 펩 등 설치·매출 있는 타이틀)에서 `effectiveMode`가 strict/exclude 유지, ROAS점수가 소재별로 상이(변별) — 무변화 확인.
4. off 안내 메시지가 사유별로 정확히 표기.
5. pytest 114 passed(HTML만 변경). 콘솔 에러 0.

## Out of Scope (YAGNI)

- 자동 임계(30%) 값 자체 튜닝 — B/C로 근본 해결되므로 유지.
- tie 임계(0.0001) 값 변경 — 비변별 판정에만 활용, 기존 랭크 로직 불변.
- conv/CPA/IPM 등 다른 지표의 비변별 교정 — 이번은 ROAS만(확정된 문제).
- 파이프라인이 사전예약에 노이즈 매출을 emit하는 것 자체 — 대시보드 측 방어로 충분, 파이프라인 수정 별도.
- 수동 '엄격' 모드에서 사전예약 강제 off — B는 auto만(수동 존중).
