# index/step1/live_dashboard DS 토큰 구조 정렬 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `index.html`·`step1_integrated.html`·`live_dashboard.html`이 각자 손으로 복제한 `:root` 토큰(또는 미해결 `var()` 폴백)을 걷어내고, 실제로 공식 `assets/ds/colors_and_type.css`를 로드해 토큰을 공유하도록 구조를 정리한다.

**Architecture:** 각 페이지의 `<head>`에 `assets/ds/colors_and_type.css` `<link>`를 (로컬 `<style>` 블록보다 앞에) 추가하고, 로컬 `:root` 블록을 삭제한다. 토큰 값은 이미 DS 파일과 거의 100% 일치하므로 시각적 변화는 없어야 한다. step1의 확인된 죽은 CSS(`.ds-topbar*`)도 함께 제거한다. 컴포넌트/레이아웃 클래스, 인라인 `style=`는 무변경.

**Tech Stack:** 순수 HTML/CSS 편집(빌드 스텝 없는 정적 사이트). 이 프로젝트엔 HTML/CSS용 자동화 테스트가 없으므로 "테스트"는 `mcp__Claude_Preview__*` 도구로 브라우저에서 직접 검증한다(변경 전/후 `getComputedStyle` 비교 + 콘솔 에러 0). `pytest`는 Python 파이프라인 무회귀 확인용 세이프티넷.

## Global Constraints

- DS 파일 `<link>`는 각 페이지의 로컬 `<style>` 블록보다 **반드시 앞**에 위치(캐스케이드 우선순위). 다른 `<link>`와의 상대 순서는 무관.
- 컴포넌트/레이아웃 클래스(`.hero`, `.ds-btn-primary`, `.ds-table`, `.live-*` 등)는 **무변경**.
- 인라인 `style="..."` 속성은 **무변경**.
- `assets/ds/colors_and_type.css`는 **내용 무변경** — 이 파일을 로드하는 5개 페이지(index/step1/live_dashboard/step2_clustering/step2_column_selector) 전부 `?v=20260702a` 버전 쿼리로 통일.
- 각 태스크 완료 시 콘솔 error 0, 브랜드 레드(`rgb(220, 40, 40)`) 등 대표 요소 computed style이 변경 전과 동일함을 preview로 확인.
- step1 전체(7,523줄) 죽은 코드 전수 감사는 범위 밖 — `.ds-topbar`처럼 이미 확인된 사례만 처리.

---

## Task 1: step2_clustering.html · step2_column_selector.html — 캐시버스팅 쿼리 통일

이미 `colors_and_type.css`를 정상 로드 중인 두 페이지에 버전 쿼리만 추가한다. 내용 변경이 없는 파일이므로 가장 낮은 리스크로 먼저 검증해, 이후 태스크(신규 소비자 추가)의 기준선을 확보한다.

**Files:**
- Modify: `step2_clustering.html:625`
- Modify: `step2_column_selector.html:11`

**Interfaces:**
- Consumes: 없음(순수 정적 HTML 편집).
- Produces: `?v=20260702a` 캐시버스팅 컨벤션 — 이후 Task 2~4가 동일 쿼리 문자열을 재사용.

- [ ] **Step 1: step2_clustering.html 캐시버스팅 쿼리 추가**

`step2_clustering.html:625`의 다음 줄:
```html
  <link rel="stylesheet" href="assets/ds/colors_and_type.css">
```
을 다음으로 교체:
```html
  <link rel="stylesheet" href="assets/ds/colors_and_type.css?v=20260702a">
```

- [ ] **Step 2: step2_column_selector.html 캐시버스팅 쿼리 추가**

`step2_column_selector.html:11`의 다음 줄:
```html
  <link rel="stylesheet" href="assets/ds/colors_and_type.css">
```
을 다음으로 교체:
```html
  <link rel="stylesheet" href="assets/ds/colors_and_type.css?v=20260702a">
```

- [ ] **Step 3: preview로 두 페이지 무회귀 확인**

`mcp__Claude_Preview__preview_list`로 실행 중인 서버의 `serverId`를 확인한 뒤, 각 페이지에서 다음을 실행(`serverId`는 실제 값으로 치환):

```js
// step2_clustering.html
window.location.href = '/step2_clustering.html'; 'nav'
```
800ms 대기 후:
```js
(async () => {
  await new Promise(r=>setTimeout(r,800));
  const l = document.querySelector('link[href*="colors_and_type.css"]');
  return { href: l && l.href, loaded: !!l };
})()
```
Expected: `href`가 `...colors_and_type.css?v=20260702a`로 끝남.

동일 패턴으로 `/step2_column_selector.html`도 확인.

두 페이지 모두 `mcp__Claude_Preview__preview_console_logs`(`level: "error"`) 결과가 빈 배열인지 확인.

- [ ] **Step 4: Commit**

```bash
git add step2_clustering.html step2_column_selector.html
git commit -m "chore(ds): colors_and_type.css 캐시버스팅 쿼리 추가 (v=20260702a)"
```

---

## Task 2: index.html — DS 파일 연결 + 로컬 :root 삭제

**Files:**
- Modify: `index.html:14` (신규 `<link>` 추가)
- Modify: `index.html:16-45` (로컬 `:root` 블록 삭제)
- Modify: `index.html:55-93` (Step 2 반영 후 기준 — 죽은 `.topbar*`/`.version-badge` CSS 삭제)

**Interfaces:**
- Consumes: `assets/ds/colors_and_type.css`의 `:root` 토큰(전량 이미 검증 완료 — 값 100% 일치, `--font-kr`만 폴백 체인이 더 완전해짐).
- Produces: 없음(터미널 태스크, 다른 태스크가 이 결과에 의존하지 않음).

- [ ] **Step 1: DS 파일 `<link>` 추가**

`index.html:14`의 다음 줄:
```html
  <link rel="stylesheet" href="assets/cl-shell.css?v=20260702a">
```
을 다음으로 교체(DS 파일 링크를 앞에 추가):
```html
  <link rel="stylesheet" href="assets/ds/colors_and_type.css?v=20260702a">
  <link rel="stylesheet" href="assets/cl-shell.css?v=20260702a">
```

- [ ] **Step 2: 로컬 `:root` 블록 삭제**

`index.html`의 다음 블록(현재 16~45줄, `<style>` 태그 직후 `/* ── Com2uS Design System tokens ── */` 주석부터 `:root { ... }` 닫는 줄까지):
```html
  <style>
    /* ── Com2uS Design System tokens ── */
    :root {
      --brand-primary:        #DC2828;
      --brand-primary-hover:  #A51E1E;
      --brand-primary-active: #891110;
      --text-primary:   #191919;
      --text-secondary: #666666;
      --text-muted:     #999999;
      --text-disabled:  #B2B2B2;
      --text-on-brand:  #FFFFFF;
      --bg-base:        #FFFFFF;
      --surface-soft:   #FAF9F7;
      --surface-card:   #F4F2EF;
      --surface-sink:   #ECEAE6;
      --hairline-warm:  #E4E1DC;
      --border-default: #CCCCCC;
      --shadow-sm:  0 1px 2px rgba(0,0,0,.06), 0 1px 3px rgba(0,0,0,.08);
      --shadow-md:  0 2px 8px rgba(0,0,0,.08), 0 4px 16px rgba(0,0,0,.06);
      --shadow-lg:  0 8px 28px rgba(0,0,0,.12), 0 2px 8px rgba(0,0,0,.06);
      --radius-sm:   4px;
      --radius-md:   8px;
      --radius-lg:   16px;
      --radius-full: 9999px;
      --font-kr: "Noto Sans KR", "Apple SD Gothic Neo", sans-serif;
      --dur-fast: 120ms;
      --dur-base: 200ms;
      --ease-standard: cubic-bezier(.2, 0, 0, 1);
    }

    * { margin: 0; padding: 0; box-sizing: border-box; }
```
을 다음으로 교체(주석·`:root` 블록·뒤따르는 빈 줄만 제거, `<style>` 태그와 `* { ... }` 규칙은 유지):
```html
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
```

- [ ] **Step 3: 죽은 `.topbar*`/`.version-badge` CSS 삭제**

Step 2 반영 후 기준으로, 다음 블록(`/* ── Topbar ── */` 주석부터 `.version-badge` 닫는 줄 + 뒤따르는 빈 줄까지, `/* ── Page body ── */` 주석 앞):
```css
    /* ── Topbar ── */
    .topbar {
      position: fixed; top: 0; left: 0; right: 0; z-index: 200;
      height: 44px;
      background: var(--brand-primary);
      display: flex; align-items: center; padding: 0 20px;
      gap: 12px;
      box-shadow: 0 1px 4px rgba(0,0,0,.2);
    }
    .topbar-logo {
      display: flex; align-items: center; gap: 8px;
      color: var(--text-on-brand); font-size: 15px; font-weight: 700;
      text-decoration: none; flex-shrink: 0;
    }
    .topbar-logo svg { width: 20px; height: 20px; }
    .topbar-sub {
      font-size: 12px; font-weight: 500;
      color: rgba(255,255,255,.6); flex: 1;
    }
    .topbar-nav { display: flex; align-items: center; gap: 6px; margin-left: auto; }
    .topbar-nav a {
      color: rgba(255,255,255,.85); font-size: 13px; font-weight: 600;
      text-decoration: none; padding: 5px 12px;
      background: rgba(255,255,255,.12); border-radius: var(--radius-md);
      border: 1px solid rgba(255,255,255,.2);
      transition: background var(--dur-fast), color var(--dur-fast);
      white-space: nowrap;
    }
    .topbar-nav a:hover { background: rgba(255,255,255,.22); color: white; }
    .topbar-nav a.active { background: rgba(255,255,255,.28); color: white; border-color: rgba(255,255,255,.45); }
    .version-badge {
      background: rgba(255,255,255,.15);
      color: rgba(255,255,255,.9);
      padding: 3px 10px; border-radius: var(--radius-full);
      font-size: 12px; font-weight: 600;
      border: 1px solid rgba(255,255,255,.25);
      letter-spacing: .02em;
    }

    /* ── Page body ── */
```
을 다음으로 교체(`.topbar*`/`.version-badge` 9개 규칙만 제거, `/* ── Page body ── */` 주석은 유지):
```css
    /* ── Page body ── */
```

- [ ] **Step 4: 삭제 전 실제 사용처 0건 재확인**

```bash
grep -n 'class="topbar"\|class="topbar \|class="topbar-\|class="[^"]*\bversion-badge\b' index.html
```
Expected: 매치 없음(exit code 1). 매치가 있으면 Step 3을 되돌리고 해당 태스크를 중단·보고.

- [ ] **Step 5: preview로 시각적 무변화 확인**

```js
window.location.href = '/index.html'; 'nav'
```
800ms 대기 후:
```js
(async () => {
  await new Promise(r=>setTimeout(r,800));
  const root = getComputedStyle(document.documentElement);
  return {
    hasLocalRoot: [...document.querySelectorAll('style')].some(s => s.textContent.includes(':root')),
    brandPrimaryVar: root.getPropertyValue('--brand-primary').trim(),
    clTopbarBg: getComputedStyle(document.querySelector('.cl-topbar')).backgroundColor,
    btnPrimaryBg: getComputedStyle(document.querySelector('.btn-primary')).backgroundColor,
    topbarRuleGone: ![...document.styleSheets].some(ss => {
      try { return [...ss.cssRules].some(r => r.selectorText === '.topbar'); } catch(e) { return false; }
    }),
  };
})()
```
Expected: `brandPrimaryVar`가 `#DC2828`(또는 DS 파일이 정의한 값), `clTopbarBg`와 `btnPrimaryBg` 둘 다 `rgb(220, 40, 40)`, `hasLocalRoot`가 `false`, `topbarRuleGone`이 `true`.

`mcp__Claude_Preview__preview_console_logs`(`level: "error"`)로 콘솔 에러 0 확인.

- [ ] **Step 6: Commit**

```bash
git add index.html
git commit -m "refactor(index): 공식 DS 토큰 파일 연결, 손복제 :root + 죽은 .topbar CSS 삭제"
```

---

## Task 3: step1_integrated.html — DS 파일 연결 + 로컬 :root 삭제 + 죽은 CSS 제거

**Files:**
- Modify: `step1_integrated.html:16` (신규 `<link>` 추가)
- Modify: `step1_integrated.html:31-60` (로컬 `:root` 블록 삭제)
- Modify: `step1_integrated.html:73-99` (죽은 `.ds-topbar*` CSS 삭제)

**Interfaces:**
- Consumes: `assets/ds/colors_and_type.css`의 `:root` 토큰(Task 2와 동일 패턴, 값 100% 일치 확인됨).
- Produces: 없음(터미널 태스크).

- [ ] **Step 1: DS 파일 `<link>` 추가**

`step1_integrated.html:16`의 다음 줄:
```html
  <link rel="stylesheet" href="assets/cl-shell.css?v=20260702a">
```
을 다음으로 교체:
```html
  <link rel="stylesheet" href="assets/ds/colors_and_type.css?v=20260702a">
  <link rel="stylesheet" href="assets/cl-shell.css?v=20260702a">
```

- [ ] **Step 2: 로컬 `:root` 블록 삭제**

`step1_integrated.html`의 다음 블록(현재 31~60줄):
```html
  <style>
    /* ── Com2uS Design System tokens ── */
    :root {
      --brand-primary:        #DC2828;
      --brand-primary-hover:  #A51E1E;
      --brand-primary-active: #891110;
      --text-primary:   #191919;
      --text-secondary: #666666;
      --text-disabled:  #B2B2B2;
      --text-on-brand:  #FFFFFF;
      --bg-base:        #FFFFFF;
      --bg-subtle:      #E5E5E5;
      --surface-soft:   #FAF9F7;
      --surface-card:   #F4F2EF;
      --surface-sink:   #ECEAE6;
      --hairline-warm:  #E4E1DC;
      --border-default: #CCCCCC;
      --shadow-sm:  0 1px 2px rgba(0,0,0,.06), 0 1px 3px rgba(0,0,0,.08);
      --shadow-md:  0 2px 8px rgba(0,0,0,.08), 0 4px 16px rgba(0,0,0,.06);
      --shadow-lg:  0 8px 28px rgba(0,0,0,.12), 0 2px 8px rgba(0,0,0,.06);
      --shadow-modal: 0 16px 48px rgba(0,0,0,.18);
      --radius-sm:   4px;
      --radius-md:   8px;
      --radius-lg:   16px;
      --radius-full: 9999px;
      --font-kr: "Noto Sans KR", "Pretendard", "Apple SD Gothic Neo", sans-serif;
      --dur-fast: 120ms;
      --dur-base: 200ms;
      --ease-standard: cubic-bezier(.2, 0, 0, 1);
    }
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }
```
을 다음으로 교체(주석·`:root` 블록만 제거, `<style>` 태그와 `* { ... }` 규칙은 유지):
```html
  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }
```

- [ ] **Step 3: 죽은 `.ds-topbar*` CSS 삭제**

같은 파일에서 (Step 2 반영 후 기준) 다음 블록을 찾는다 — `/* ── Shell Layout ── */` 주석 뒤에 이어지는 `.ds-topbar` 관련 7개 규칙:
```css
    /* ── Shell Layout ── */
    .ds-topbar {
      position: fixed; top: 0; left: 0; right: 0; z-index: 200;
      height: 44px;
      background: var(--brand-primary);
      display: flex; align-items: center; padding: 0 16px;
      gap: 12px;
    }
    .ds-topbar-logo {
      display: flex; align-items: center; gap: 8px;
      color: var(--text-on-brand); font-size: 15px; font-weight: 700;
      text-decoration: none; flex-shrink: 0;
    }
    .ds-topbar-logo svg { width: 20px; height: 20px; }
    .ds-topbar-title {
      font-size: 12px; font-weight: 500;
      color: rgba(255,255,255,.7); flex: 1;
    }
    .ds-topbar-right { display: flex; align-items: center; gap: 8px; margin-left: auto; }
    .ds-topbar-icon-btn {
      display: flex; align-items: center; justify-content: center;
      width: 32px; height: 32px; border-radius: var(--radius-md);
      background: rgba(255,255,255,.12); border: none; cursor: pointer;
      color: var(--text-on-brand); transition: background var(--dur-fast);
    }
    .ds-topbar-icon-btn:hover { background: rgba(255,255,255,.22); }

    .ds-app-body {
```
을 다음으로 교체(`/* ── Shell Layout ── */` 주석은 `.ds-app-body`용으로 유지, `.ds-topbar*` 7개 규칙만 제거):
```css
    /* ── Shell Layout ── */
    .ds-app-body {
```

- [ ] **Step 4: 삭제 전 실제 사용처 0건 재확인**

```bash
grep -n 'class="[^"]*ds-topbar' step1_integrated.html
```
Expected: 매치 없음(exit code 1). 매치가 있으면 Step 3을 되돌리고 해당 태스크를 중단·보고.

- [ ] **Step 5: preview로 시각적 무변화 확인**

```js
window.location.href = '/step1_integrated.html'; 'nav'
```
1200ms 대기 후(데이터 로드 포함):
```js
(async () => {
  await new Promise(r=>setTimeout(r,1200));
  const btn = document.querySelector('.ds-btn-primary');
  const topbar = document.querySelector('.cl-topbar');
  return {
    hasLocalRoot: [...document.querySelectorAll('style')].some(s => s.textContent.includes(':root')),
    btnPrimaryBg: btn ? getComputedStyle(btn).backgroundColor : null,
    clTopbarBg: topbar ? getComputedStyle(topbar).backgroundColor : null,
    dsTopbarRuleGone: ![...document.styleSheets].some(ss => {
      try { return [...ss.cssRules].some(r => r.selectorText === '.ds-topbar'); } catch(e) { return false; }
    }),
  };
})()
```
Expected: `hasLocalRoot: false`, `btnPrimaryBg`와 `clTopbarBg` 둘 다 `rgb(220, 40, 40)`, `dsTopbarRuleGone: true`.

`mcp__Claude_Preview__preview_console_logs`(`level: "error"`)로 콘솔 에러 0 확인.

- [ ] **Step 6: Commit**

```bash
git add step1_integrated.html
git commit -m "refactor(step1): 공식 DS 토큰 파일 연결, 손복제 :root + 죽은 .ds-topbar CSS 삭제"
```

---

## Task 4: live_dashboard.html — DS 파일 연결

가장 작은 태스크. 로컬 `:root`가 없어 삭제할 것도 없고, 기존 `var(--token, fallback)` 패턴이 그대로 실제 DS 값을 받게 된다.

**Files:**
- Modify: `live_dashboard.html:9` (신규 `<link>` 추가)

**Interfaces:**
- Consumes: `assets/ds/colors_and_type.css`의 `:root` 토큰(`var(--brand-primary, #DC2828)` 등 기존 폴백값과 동일해 시각적 차이 없음).
- Produces: 없음(터미널 태스크).

- [ ] **Step 1: DS 파일 `<link>` 추가**

`live_dashboard.html:9`의 다음 줄:
```html
  <link rel="stylesheet" href="assets/cl-shell.css?v=20260702a">
```
을 다음으로 교체:
```html
  <link rel="stylesheet" href="assets/ds/colors_and_type.css?v=20260702a">
  <link rel="stylesheet" href="assets/cl-shell.css?v=20260702a">
```

- [ ] **Step 2: preview로 시각적 무변화 확인**

```js
window.location.href = '/live_dashboard.html?title=zeus'; 'nav'
```
900ms 대기 후:
```js
(async () => {
  await new Promise(r=>setTimeout(r,900));
  const l = document.querySelector('link[href*="colors_and_type.css"]');
  const activeBtn = document.querySelector('.live-metric-btn.active');
  return {
    dsLinkLoaded: !!l,
    activeBtnBg: activeBtn ? getComputedStyle(activeBtn).backgroundColor : null,
  };
})()
```
Expected: `dsLinkLoaded: true`, `activeBtnBg`가 `rgb(220, 40, 40)`(변경 전과 동일).

`mcp__Claude_Preview__preview_console_logs`(`level: "error"`)로 콘솔 에러 0 확인.

- [ ] **Step 3: Commit**

```bash
git add live_dashboard.html
git commit -m "refactor(live): 공식 DS 토큰 파일 연결"
```

---

## Task 5: 전체 무회귀 확인 + push 준비

**Files:**
- 없음(검증 전용 태스크).

**Interfaces:**
- Consumes: Task 1~4의 전체 결과.
- Produces: 없음.

- [ ] **Step 1: pytest 전체 실행**

```bash
python -m pytest -q --ignore=tests/test_mmp_score.py --ignore=tests/test_registry.py
```
Expected: 기존 통과 건수(97) 그대로, 실패 0. (CSS/HTML만 변경했으므로 Python 로직 영향 없음 — 회귀 발생 시 즉시 원인 조사.)

- [ ] **Step 2: 5개 페이지 최종 일괄 콘솔 체크**

각 페이지(`index.html`, `step1_integrated.html`, `live_dashboard.html?title=zeus`, `step2_clustering.html`, `step2_column_selector.html`)를 순서대로 로드하고 매번 `mcp__Claude_Preview__preview_console_logs`(`level: "error"`)로 에러 0 확인. 하나라도 에러 발생 시 해당 페이지의 소속 Task로 돌아가 수정.

- [ ] **Step 3: git log로 커밋 4개(Task1~4) 확인 후 사용자에게 push 확인 요청**

```bash
git log --oneline -4
```
사용자에게 "origin/main에 push할까요?"로 명시적 확인 후에만 `git push origin main` 실행(프로젝트 컨벤션 — 매 push 전 명시적 확인 필수).
