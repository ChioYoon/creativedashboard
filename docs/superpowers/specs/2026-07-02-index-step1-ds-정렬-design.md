# index.html / step1_integrated.html / live_dashboard.html — DS 토큰 구조 정렬 설계

**작성일:** 2026-07-02
**대상:** `index.html`, `step1_integrated.html`, `live_dashboard.html` (+ `assets/ds/colors_and_type.css`·`step2_clustering.html`·`step2_column_selector.html`은 캐시버스팅 쿼리만)
**요구:** step1/index 전체 디자인 시스템 완전 정렬 — 범위는 "구조 정리"로 확정(사용자 선택).

## 현황

공식 DS 토큰·컴포넌트 파일은 `assets/ds/colors_and_type.css`이지만, 실제로 이 파일을 `<link>`로 로드하는 페이지는 `step2_clustering.html`·`step2_column_selector.html` 뿐이다.

- **index.html**: `assets/ds/colors_and_type.css` 미로드. 자체 `<style>` 블록에 `:root` 토큰(24개)을 손으로 복제해 사용. `.hero`/`.btn-primary` 등 독자 클래스명. **추가 확인(plan 작성 중 발견)**: `.topbar`/`.topbar-logo`/`.topbar-sub`/`.topbar-nav`/`.version-badge`(56~93줄, `/* ── Topbar ── */` 주석 포함)도 step1의 `.ds-topbar`와 동일한 패턴 — 실제 헤더는 `cl-topbar`(공유 셸)를 쓰면서 완전히 죽은 코드로 남음(본문 `class=` 참조 0건, grep 재확인).
- **step1_integrated.html**(7,523줄): 마찬가지로 미로드. 자체 `:root`(26개) 복제 + `.ds-btn-primary`/`.ds-table`/`.ds-topbar` 등 **"ds-" 접두사 클래스를 자체 정의**(이름만 DS처럼 보이고 공식 파일과 무관). `.ds-topbar*`(5개 셀렉터, 74~98줄)는 실제 헤더가 `cl-topbar`(공유 셸, `assets/cl-shell.css`)를 쓰면서 완전히 죽은 코드로 남아있음(본문 `class=` 참조 0건, grep으로 확인).
- **live_dashboard.html**: 로컬 `:root` 자체가 없고 `var(--brand-primary, #DC2828)` 형태의 미해결 폴백 패턴만 사용 — DS 파일이 없으니 항상 폴백값으로 렌더링됨.

**토큰 값 비교 결과**(직접 diff): step1·index가 로컬로 복제한 토큰명은 전부 DS 파일에 동일 이름으로 존재하며, 값도 거의 100% 일치한다. 예외 1건:
- `--font-kr` 폴백 체인 — index/step1 로컬 버전엔 `"Pretendard"`·`"Malgun Gothic"` 폴백이 일부 빠져있음(DS 파일 쪽이 더 완전함). 웹폰트(Noto Sans KR)가 항상 우선 로드되므로 실사용상 시각적 차이는 없음.

**정정**: `index.html`의 `--text-muted: #999999`는 선언만 있고 실제 `var(--text-muted...)` 참조는 0곳(재확인 grep 결과) — 죽은 토큰이라 DS 파일에 별칭을 추가할 필요 없음. `assets/ds/colors_and_type.css` 자체는 이번 작업에서 **내용 변경 없음**(버전 쿼리만 추가, 아래 §4).

## 설계 — 3개 페이지를 공식 DS 파일로 통일

**공통 규칙(link 배치)**: DS 파일 `<link>`는 각 페이지의 로컬 `<style>` 블록보다 **반드시 앞**에 위치해야 한다(캐스케이드 우선순위상 로컬 규칙이 DS 기본값을 이겨야 하므로). 다른 `<link>` 태그들과의 상대 순서는 무관.

### 1. `index.html`

- `<head>`에 `<link rel="stylesheet" href="assets/ds/colors_and_type.css?v=20260702a">` 추가(로컬 `<style>` 블록보다 앞).
- 로컬 `<style>` 내 `:root { ... }` 블록(24개 토큰) 전체 삭제.
- 죽은 CSS 삭제: `.topbar`·`.topbar-logo`·`.topbar-logo svg`·`.topbar-sub`·`.topbar-nav`·`.topbar-nav a`·`.topbar-nav a:hover`·`.topbar-nav a.active`·`.version-badge`(56~93줄, `.ds-topbar`와 동일 근거로 처리 — step1과 같은 카테고리의 이미 확인된 사례).
- `.hero`/`.btn-primary` 등 실제 사용 중인 나머지 클래스는 무변경 — `var(--token)` 참조가 이제 DS 파일에서 값을 받음.

### 2. `step1_integrated.html`

- `<head>`에 `<link rel="stylesheet" href="assets/ds/colors_and_type.css?v=20260702a">` 추가(`assets/cl-shell.css` 인접 위치, 로컬 `<style>` 블록보다 앞).
- 로컬 `<style>` 내 `:root { ... }` 블록(26개 토큰) 전체 삭제.
- 죽은 CSS 삭제: `.ds-topbar`·`.ds-topbar-logo`·`.ds-topbar-logo svg`·`.ds-topbar-title`·`.ds-topbar-right`·`.ds-topbar-icon-btn`·`.ds-topbar-icon-btn:hover`(74~98줄, 주석 `/* ── Shell Layout ── */` 라인은 `.ds-app-body`용으로 재사용되므로 유지).
- `.ds-btn-primary`/`.ds-table` 등 자체 컴포넌트 클래스, 인라인 `style=`는 **무변경**(범위 밖).

### 3. `live_dashboard.html`

- `<head>`에 `<link rel="stylesheet" href="assets/ds/colors_and_type.css?v=20260702a">` 추가.
- 로컬 `:root`가 없으므로 삭제할 것 없음. 기존 `var(--token, fallback)` 패턴이 그대로 실제 DS 값을 받게 됨.

### 4. 캐시버스팅 (버전 쿼리 통일)

`colors_and_type.css` 내용은 무변경이지만, 이 파일을 로드하는 페이지가 2개(step2_*)에서 5개로 늘어나므로 **일관성을 위해 5개 페이지 전부** 버전 쿼리를 `?v=20260702a`로 통일:
- `index.html`(신규), `step1_integrated.html`(신규), `live_dashboard.html`(신규) — 위 §1~3에서 추가하며 함께 부여
- `step2_clustering.html`, `step2_column_selector.html` — 기존 `<link>`에 쿼리 없음 → `?v=20260702a` 추가

## 불변

- 각 페이지의 레이아웃·컴포넌트 클래스(`.hero`, `.ds-btn-primary`, `.ds-table`, `.live-*` 등)는 무변경.
- 인라인 `style="..."` 속성(step1 420곳 등)은 무변경.
- step1 전체(7,523줄) 죽은 코드 전수 감사는 이번 범위 밖 — `.ds-topbar`처럼 이미 확인된 사례만 처리.

## 검증 (preview)

각 페이지 로드 후:
1. 콘솔 error 0.
2. `getComputedStyle`로 대표 요소 확인 — 브랜드 레드 배경(`.cl-nav-cta`/`.live-metric-btn.active` 등)이 `rgb(220, 40, 40)`, 카드 배경(각 페이지 카드류)이 변경 전과 동일한지.
3. index.html/step1_integrated.html: `.topbar`/`.ds-topbar` 관련 DOM/CSS 잔존 참조 0건 재확인.
4. `pytest` 무회귀(CSS/HTML 변경만이라 영향 없을 것으로 예상, 그래도 실행).
