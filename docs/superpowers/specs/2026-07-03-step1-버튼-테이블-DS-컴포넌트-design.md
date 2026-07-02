# step1 버튼·테이블 공식 DS 컴포넌트 교체 — 설계

**작성일:** 2026-07-03
**대상:** `step1_integrated.html`
**상위 맥락:** 2026-07-02 "DS 토큰 구조 정렬"(스펙 `2026-07-02-index-step1-ds-정렬-design.md`)에서 범위 밖으로 명시했던 "컴포넌트 레벨 교체"의 후속. 사용자가 브라우저 목업 비교(실제 CSS 값 재현)를 보고 **버튼 B(공식 필)·테이블 B(공식 DS)** 를 선택해 확정.

## 배경 조사

- step1은 2026-07-02 작업으로 공식 DS 파일(`assets/ds/colors_and_type.css?v=20260702a`)을 이미 로드 중.
- **이름 충돌 발견**: step1 로컬 `<style>`에 공식 DS와 **동명의 `.ds-table`** 이 정의돼 있음(860~875줄). 현재는 로컬 정의가 캐스케이드 순서(로컬 `<style>`이 뒤)로 이겨 시각적 문제는 없으나 잠재 충돌 상태.
- **디자인 자체가 다름**: 로컬 `.ds-btn-primary`(각진 사각, radius 8px, padding 10px 16px) vs 공식 `.ds-pill--primary`(캡슐형, radius 9999px, height 40px). 로컬 `.ds-table`(패딩 7px 10px, 헤더 10px/본문 13px) vs 공식 `.ds-table`(패딩 12~14px 16px, 헤더 12px/본문 15px, `.ds-cell-key` 레드 강조).
- **공식 DS에 대응 컴포넌트가 없는 것들**: 탭(`.ds-tab*`)·사이드바(`.ds-sidebar*`)·통계칩(`.ds-stat-chip*`)·앱셸(`.ds-app-body`/`.ds-main`) — DS 파일은 셸/탭/사이드바를 정의하지 않음. 이들은 이름 충돌도 없어 교체 대상이 아니라 step1 고유 컴포넌트로 유지.
- 사용처 실측:
  - 버튼: `.ds-btn-primary` 3곳(1442 CSV 불러오기 · 1579 분석 실행 · 1752 피로도 적용) + `.ds-btn-ghost` 1곳(1753 피로도 초기화). 정의 101~127줄.
  - 테이블: `class="ds-table"` 4곳(1664 `#resultTable` · 1760 `#fatigueTable` · 4131 모달 내 소형(인라인 `font-size:12px` 오버라이드 보유) · 5913 유형 요약). `.num` 셀/헤더는 공식 DS도 동일 문법 지원. 1위 행 `rank-top`은 JS 5163줄에서 부여.

## 확정된 결정 (사용자, 목업 비교 후)

- 버튼: **B — 공식 `.ds-pill--primary`/`--ghost`(캡슐형)로 교체.**
- 테이블: **B — 공식 `.ds-table`(여유 패딩 + `.ds-cell-key` 레드 강조)로 교체.**

## 설계

### 1. 버튼 교체 (4곳)

- 로컬 CSS 정의 삭제: `/* ── DS 버튼 ── */` 블록 전체(100~127줄) — `.ds-btn-primary`(101~109)·`.ds-btn-secondary`(110~118, **사용처 0곳인 죽은 CSS로 grep 확인됨** — 함께 삭제)·`.ds-btn-ghost`(119~127).
- 사용처 클래스 교체:
  - `class="ds-btn-primary"` → `class="ds-pill ds-pill--primary"` (3곳)
  - `class="ds-btn-ghost"` → `class="ds-pill ds-pill--ghost"` (1곳)
- 인라인 스타일 처리 원칙: 공식 `.ds-pill`은 자체 높이(40px)·패딩(0 18px) 모델 → 충돌하는 오버라이드(`padding:7px`, `padding:8px 20px;font-size:13px`)는 **제거**, 레이아웃 성격(`width:100%`, `margin-top:6px`)은 **유지**.

### 2. 테이블 교체 (4곳, 클래스명 변경 없음)

- 로컬 `.ds-table` CSS 블록(860~875줄, 8개 규칙) **삭제** → 이미 로드 중인 공식 DS의 `.ds-table`이 자동 적용. HTML의 `class="ds-table"`은 그대로(이름이 같으므로) — 이 삭제 하나로 **이름 충돌도 해소**.
- `.num`: 공식 DS가 `.ds-table .num, .ds-table th.num` 동일 지원 — JS/HTML 변경 불필요.
- 1위 행: JS 5163줄 `tr.classList.add('rank-top')` → `'is-active'` 한 단어 교체(공식 DS의 왼쪽 레드 인디케이터 + 소프트 배경). 로컬 `rank-top` 규칙은 삭제되는 블록에 포함.
- 종합점수 컬럼: 결과 테이블 행 생성 JS에서 점수 `<td>`에 공식 `ds-cell-key` 클래스 추가(레드 볼드 + tabular-nums) — 목업 B의 "핵심 수치 레드 강조". 정확한 행 생성 위치는 plan에서 확정.
- 4131줄 소형 테이블의 인라인 `font-size:12px` 오버라이드는 유지(모달 내 축소 표시 의도).

## 불변

- 탭·사이드바·통계칩·앱셸 클래스(공식 DS에 대응 없음) — 무변경.
- 모든 계산 로직·데이터·정렬·필터 동작 — 무변경 (CSS/클래스명만).
- `assets/ds/colors_and_type.css` — 내용 무변경.

## 리스크

- **R1 시각적 밀도 변화**: 공식 테이블은 패딩·폰트가 커서 결과 테이블(min-width 1180px, 다컬럼)이 더 커짐 — 목업으로 확인 후 사용자가 선택한 사항. 실사용에서 과하면 후속 조정.
- **R2 버튼 인라인 오버라이드 누락**: 4곳 각각 인라인 스타일이 달라 개별 확인 필요 — plan에서 4곳 모두 before/after 명시.
- **R3 `.ds-table` 삭제 부수효과**: 로컬 블록에만 있던 `tbody tr` 보더(`--hairline-warm`)가 공식(`--border-default`)으로 바뀜 — 의도된 교체의 일부.

## 검증 (preview)

1. 4개 테이블(결과·피로도·모달 소형·유형 요약) 렌더링 — 공식 스타일(패딩 12~14px, 헤더 12px 배경 `--bg-subtle`) 적용 확인.
2. 4개 버튼 캡슐형 렌더링 + hover 동작.
3. 상호작용 무회귀: 컬럼 정렬, 행 클릭 → 모달, 피로도 분석 적용/초기화, CSV 불러오기 버튼.
4. 1위 행 `is-active` 레드 인디케이터, 점수 컬럼 `ds-cell-key` 레드 강조 확인.
5. 콘솔 error 0.

## 범위 밖

- 탭·사이드바·통계칩의 DS 컴포넌트화(공식 DS에 대응 없음 — 필요 시 DS 파일 확장은 별도 작업).
- step2/live_dashboard의 동종 작업.
- 인라인 `style=` 전면 정리.
