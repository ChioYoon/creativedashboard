# Dashboard Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `step1_integrated.html`의 전체 UI를 Com2uS 디자인 시스템으로 재구성 — 사이드바 레이아웃 + 탭 구조 + 텍스트 최소화.

**Architecture:** 기존 수직 스크롤 섹션 구조를 `topbar(44px) + sidebar(240px) + main(flex-1)` 레이아웃으로 전환. 결과 영역은 탭 3개(소재 목록 / 전체 성과 요약 / 피로도)로 분리. 기존 JS 함수(calculateScores, displayScoringResults 등)는 유지하고 새 UI 함수만 추가.

**Tech Stack:** Vanilla HTML/CSS/JS (단일 파일), Noto Sans KR (Google Fonts CDN), Lucide icons (unpkg CDN), Com2uS DS 토큰 변수

---

## File Map

| 파일 | 변경 유형 | 설명 |
|---|---|---|
| `step1_integrated.html:1-17` | Modify | `<head>` — 폰트 CDN + Lucide CDN 추가 |
| `step1_integrated.html:18-1051` | Modify | 기존 CSS → DS 토큰 + 신규 레이아웃 CSS 추가 |
| `step1_integrated.html:1053-1599` | Modify | `<body>` HTML 전체 재구성 |
| `step1_integrated.html:1630+` | Modify | JS — 신규 함수 추가 + displayScoringResults 수정 |

---

## Task 1: Design System Foundation

**Files:**
- Modify: `step1_integrated.html:1-17` (head tags)
- Modify: `step1_integrated.html:18-30` (style block opening, body styles)

### Step 1.1: Google Fonts + Lucide CDN 삽입

`<head>` 블록 안, 기존 `<!-- Chart.js -->` 주석 **앞**에 삽입 (현재 line 10 앞):

- [ ] `step1_integrated.html` line 9 뒤에 다음 두 줄 삽입:

```html
  <!-- Com2uS DS: Noto Sans KR -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
  <!-- Lucide icons -->
  <script src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>
```

### Step 1.2: DS 토큰 변수 블록 삽입

`<style>` 블록 최상단(현재 line 18 직후, `* { margin:0;...}` 앞)에 삽입:

- [ ] 다음 `:root {}` 블록을 `<style>` 바로 다음 줄에 삽입:

```css
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
```

### Step 1.3: body 기본 스타일 교체

기존 `body { font-family: -apple-system,...; background: linear-gradient(...)... }` 를 교체:

- [ ] 기존 `body { ... }` 블록을 다음으로 교체:

```css
    body {
      font-family: var(--font-kr);
      background: var(--surface-soft);
      min-height: 100vh;
      color: var(--text-primary);
    }
```

### Step 1.4: 기존 `.container` 스타일 제거

- [ ] 기존 `.container { max-width: 1400px; margin: 0 auto; background: white; border-radius: 16px; box-shadow: ...; overflow: hidden; }` 블록 삭제 (신규 layout CSS로 대체)

### Step 1.5: 브라우저 검증

- [ ] 파일을 브라우저에서 열어 페이지 로드 확인 (폰트가 Noto Sans KR로 변경됐는지 확인)

### Step 1.6: Commit

- [ ] `git add step1_integrated.html && git commit -m "style: apply DS token variables and Noto Sans KR font"`

---

## Task 2: Shell Layout HTML + CSS

**Files:**
- Modify: `step1_integrated.html` — CSS 추가 (style 블록 내)
- Modify: `step1_integrated.html:1053-1060` — body 최상위 HTML 구조 교체

### Step 2.1: Shell Layout CSS 추가

기존 `.top-nav` CSS 블록(line 40 근방) **앞**에 삽입:

- [ ] 다음 CSS를 `/* 상단 고정 네비게이션 */` 주석 앞에 삽입:

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
      display: flex;
      height: calc(100vh - 44px);
      margin-top: 44px;
      overflow: hidden;
    }

    /* ── Sidebar ── */
    .ds-sidebar {
      width: 240px; flex-shrink: 0;
      background: var(--bg-base);
      border-right: 1px solid var(--hairline-warm);
      display: flex; flex-direction: column;
      overflow: hidden;
      transition: width var(--dur-base) var(--ease-standard);
    }
    .ds-sidebar.collapsed { width: 40px; }
    .ds-sidebar-header {
      display: flex; align-items: center; justify-content: space-between;
      padding: 0 12px; height: 40px; flex-shrink: 0;
      border-bottom: 1px solid var(--hairline-warm);
    }
    .ds-sidebar-toggle {
      display: flex; align-items: center; justify-content: center;
      width: 28px; height: 28px; border-radius: var(--radius-sm);
      background: none; border: none; cursor: pointer;
      color: var(--text-secondary);
      transition: background var(--dur-fast);
    }
    .ds-sidebar-toggle:hover { background: var(--surface-sink); }
    .ds-sidebar.collapsed .ds-sidebar-label { display: none; }
    .ds-sidebar-label { font-size: 11px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; color: var(--text-secondary); }
    .ds-sidebar-scroll { flex: 1; overflow-y: auto; overflow-x: hidden; }
    .ds-sidebar-footer { padding: 12px; border-top: 1px solid var(--hairline-warm); flex-shrink: 0; }
    .ds-sidebar.collapsed .ds-sidebar-section-body { display: none; }
    .ds-sidebar.collapsed .ds-sidebar-footer-label { display: none; }

    /* ── Main Content ── */
    .ds-main {
      flex: 1; overflow-y: auto;
      display: flex; flex-direction: column;
      background: var(--surface-soft);
      min-width: 0;
    }
    .ds-main-toolbar {
      display: flex; align-items: center; gap: 8px;
      padding: 8px 20px; flex-shrink: 0;
      background: var(--bg-base);
      border-bottom: 1px solid var(--hairline-warm);
      min-height: 44px;
    }
    .ds-main-content { flex: 1; overflow-y: auto; padding: 20px; }
```

### Step 2.2: 기존 `.top-nav`, `.nav-*` CSS 유지 여부

- [ ] `.top-nav` 및 `.nav-*` CSS 블록 전체 삭제 (topbar로 대체됨, scrollToSection 버튼들 제거)

단, `scrollToSection()` JS 함수는 제거하지 않음 — 다른 곳에서 참조될 수 있음.

### Step 2.3: 새 HTML 구조 삽입

`<body>` 바로 다음 줄(현재 `<div class="container">` — line 1054)을 다음으로 교체:

- [ ] 기존 `<div class="container">` 오프닝 태그를 다음으로 교체:

```html
  <!-- ── Top Navigation Bar ── -->
  <header class="ds-topbar">
    <a href="index.html" class="ds-topbar-logo">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>
      <span>CLOOP</span>
    </a>
    <span class="ds-topbar-title">광고 소재 분석 대시보드</span>
    <div class="ds-topbar-right">
      <!-- 타이틀 셀렉터 -->
      <select id="titleSelector"
              onchange="onTitleSelectorChange(this.value)"
              title="분석할 타이틀 선택"
              style="padding:4px 10px;border:1.5px solid rgba(255,255,255,.35);border-radius:6px;
                     background:rgba(255,255,255,.12);color:#fff;font-size:12px;font-weight:600;
                     cursor:pointer;max-width:200px;">
        <option value="">타이틀 선택 (직접 업로드)</option>
      </select>
      <button class="ds-topbar-icon-btn gai-nav-key-btn" onclick="openGeminiModal()" title="Gemini AI 분석 설정">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
      </button>
      <a class="ds-topbar-icon-btn" id="step2Link" href="step2_column_selector.html" title="Step 2 군집화">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
      </a>
    </div>
  </header>

  <!-- ── App Body: Sidebar + Main ── -->
  <div class="ds-app-body">
    <!-- Sidebar -->
    <aside id="sidebar" class="ds-sidebar">
      <div class="ds-sidebar-header">
        <span class="ds-sidebar-label">메뉴</span>
        <button class="ds-sidebar-toggle" onclick="toggleSidebar()" title="사이드바 접기/펼치기">
          <svg id="sidebarToggleIcon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>
        </button>
      </div>
      <div class="ds-sidebar-scroll" id="sidebarScroll">
        <!-- 사이드바 콘텐츠: Task 3에서 채움 -->
      </div>
      <div class="ds-sidebar-footer">
        <button class="ds-btn-primary" style="width:100%;" onclick="calculateScores()">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
          <span class="ds-sidebar-footer-label">점수 계산 실행</span>
        </button>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="ds-main" id="mainContent">
      <!-- 탭 바 + 콘텐츠: Task 4에서 채움 -->
    </main>
  </div>
```

### Step 2.4: 기존 `<nav class="top-nav">`, `<div class="header">` 및 `.container` 닫는 `</div>` 제거

- [ ] 기존 `<nav class="top-nav">...</nav>` 블록 전체 삭제 (line 1055–1091)
- [ ] 기존 `<div class="header">...</div>` 블록 전체 삭제 (line 1094–1098)
- [ ] line 1599의 `</div>` (`.container` 닫는 태그) 삭제

### Step 2.5: Primary 버튼 CSS 추가

`<style>` 블록 내에 추가:

- [ ] 다음 CSS 추가:

```css
    /* ── DS 버튼 ── */
    .ds-btn-primary {
      display: inline-flex; align-items: center; justify-content: center; gap: 6px;
      padding: 10px 16px;
      background: var(--brand-primary); color: var(--text-on-brand);
      border: none; border-radius: var(--radius-md);
      font-family: var(--font-kr); font-size: 14px; font-weight: 700;
      cursor: pointer; transition: background var(--dur-fast);
    }
    .ds-btn-primary:hover { background: var(--brand-primary-hover); }
    .ds-btn-secondary {
      display: inline-flex; align-items: center; justify-content: center; gap: 6px;
      padding: 8px 14px;
      background: var(--bg-base); color: var(--brand-primary);
      border: 1.5px solid var(--brand-primary); border-radius: var(--radius-md);
      font-family: var(--font-kr); font-size: 13px; font-weight: 600;
      cursor: pointer; transition: background var(--dur-fast);
    }
    .ds-btn-secondary:hover { background: #fff1f1; }
    .ds-btn-ghost {
      display: inline-flex; align-items: center; justify-content: center; gap: 6px;
      padding: 6px 12px;
      background: none; color: var(--text-secondary);
      border: none; border-radius: var(--radius-md);
      font-family: var(--font-kr); font-size: 13px; font-weight: 500;
      cursor: pointer; transition: background var(--dur-fast);
    }
    .ds-btn-ghost:hover { background: var(--surface-sink); }
```

### Step 2.6: `toggleSidebar()` JS 함수 추가

`<script>` 블록 최상단(line 1632, `const NON_TAG_COLS` 앞)에 추가:

- [ ] 다음 함수 추가:

```javascript
/* ── UI: 사이드바 접기/펼치기 ── */
function toggleSidebar() {
  const sb = document.getElementById('sidebar');
  const icon = document.getElementById('sidebarToggleIcon');
  const isCollapsed = sb.classList.toggle('collapsed');
  if (icon) {
    icon.innerHTML = isCollapsed
      ? '<polyline points="9 18 15 12 9 6"/>'
      : '<polyline points="15 18 9 12 15 6"/>';
  }
}
```

### Step 2.7: 브라우저 검증

- [ ] 파일을 브라우저에서 열기 — 빨간 topbar + 빈 사이드바(240px) + 빈 main 영역이 보여야 함
- [ ] 사이드바 토글 버튼 클릭 시 40px 아이콘 레일로 축소되는지 확인

### Step 2.8: Commit

- [ ] `git add step1_integrated.html && git commit -m "layout: add fixed sidebar + main area shell"`

---

## Task 3: Sidebar Content (Controls Migration)

**Files:**
- Modify: `step1_integrated.html` — sidebar HTML + accordion CSS + JS

### Step 3.1: Sidebar Accordion CSS 추가

`<style>` 블록에 추가:

- [ ] 다음 CSS 추가:

```css
    /* ── Sidebar Accordion ── */
    .sb-section { border-bottom: 1px solid var(--hairline-warm); }
    .sb-section-header {
      display: flex; align-items: center; justify-content: space-between;
      padding: 10px 12px; cursor: pointer;
      user-select: none; transition: background var(--dur-fast);
    }
    .sb-section-header:hover { background: var(--surface-soft); }
    .sb-section-title {
      font-size: 10px; font-weight: 700; letter-spacing: .06em;
      text-transform: uppercase; color: var(--text-secondary);
      display: flex; align-items: center; gap: 6px;
    }
    .sb-section-title svg { width: 13px; height: 13px; flex-shrink: 0; }
    .sb-chevron { width: 14px; height: 14px; color: var(--text-secondary); transition: transform var(--dur-fast); }
    .sb-section.open .sb-chevron { transform: rotate(180deg); }
    .sb-section-body { padding: 8px 12px 12px; }
    .sb-section.closed .sb-section-body { display: none; }
    /* icon-rail 접힘 시 섹션 헤더 아이콘만 */
    .ds-sidebar.collapsed .sb-section-title span { display: none; }
    .ds-sidebar.collapsed .sb-section-header { justify-content: center; padding: 10px 0; }
    .ds-sidebar.collapsed .sb-chevron { display: none; }
    .ds-sidebar.collapsed .sb-section-body { display: none !important; }

    /* ── Sidebar Form Controls ── */
    .sb-label {
      display: block; font-size: 11px; font-weight: 600;
      color: var(--text-secondary); letter-spacing: .02em;
      text-transform: uppercase; margin-bottom: 6px; margin-top: 10px;
    }
    .sb-label:first-child { margin-top: 0; }
    .sb-radio-group, .sb-chip-group { display: flex; flex-wrap: wrap; gap: 5px; }
    .sb-radio-item {
      display: flex; align-items: center; gap: 4px;
      padding: 4px 10px; border: 1px solid var(--border-default);
      border-radius: var(--radius-full); cursor: pointer;
      font-size: 12px; font-weight: 500; color: var(--text-primary);
      transition: all var(--dur-fast);
    }
    .sb-radio-item input[type="radio"],
    .sb-radio-item input[type="checkbox"] { display: none; }
    .sb-radio-item.selected {
      background: var(--brand-primary); color: var(--text-on-brand);
      border-color: var(--brand-primary);
    }
    .sb-input {
      width: 100%; padding: 7px 10px;
      border: 1px solid var(--border-default); border-radius: var(--radius-md);
      font-family: var(--font-kr); font-size: 12px; color: var(--text-primary);
      background: var(--bg-base); outline: none;
      transition: border-color var(--dur-fast);
    }
    .sb-input:focus { border-color: var(--brand-primary); }
    .sb-date-row { display: flex; align-items: center; gap: 6px; }
    .sb-date-row .sb-input { flex: 1; }
    .sb-date-sep { font-size: 11px; color: var(--text-secondary); flex-shrink: 0; }
    /* 체크박스 그룹 (캠페인) */
    .sb-checkbox-group {
      max-height: 120px; overflow-y: auto;
      border: 1px solid var(--border-default); border-radius: var(--radius-md);
      padding: 4px 0; margin-top: 6px;
    }
    .sb-checkbox-item {
      display: flex; align-items: center; gap: 6px;
      padding: 3px 10px; font-size: 12px; cursor: pointer;
    }
    .sb-checkbox-item:hover { background: var(--surface-soft); }
    .sb-checkbox-item input[type="checkbox"] { accent-color: var(--brand-primary); }
    .sb-selected-count { font-size: 10px; color: var(--text-secondary); margin-top: 4px; }
    /* 슬라이더 */
    .sb-slider-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
    .sb-slider-label { font-size: 12px; color: var(--text-primary); width: 60px; flex-shrink: 0; }
    .sb-slider { flex: 1; accent-color: var(--brand-primary); }
    .sb-slider-val { font-size: 12px; font-weight: 700; color: var(--brand-primary); width: 36px; text-align: right; }
    /* 토글 스위치 */
    .sb-toggle-row {
      display: flex; align-items: center; justify-content: space-between;
      padding: 8px 0; border-top: 1px solid var(--hairline-warm); margin-top: 8px;
    }
    .sb-toggle-label { font-size: 12px; color: var(--text-primary); flex: 1; }
    .sb-toggle { position: relative; display: inline-block; width: 36px; height: 20px; }
    .sb-toggle input { opacity: 0; width: 0; height: 0; }
    .sb-toggle-track {
      position: absolute; inset: 0; background: var(--border-default);
      border-radius: var(--radius-full); cursor: pointer;
      transition: background var(--dur-fast);
    }
    .sb-toggle input:checked + .sb-toggle-track { background: var(--brand-primary); }
    .sb-toggle-track::after {
      content: ''; position: absolute; top: 2px; left: 2px;
      width: 16px; height: 16px; background: white;
      border-radius: 50%; transition: transform var(--dur-fast);
    }
    .sb-toggle input:checked + .sb-toggle-track::after { transform: translateX(16px); }
    /* ROAS 모드 칩 (single select) */
    .sb-mode-chip {
      padding: 4px 10px; border: 1px solid var(--border-default);
      border-radius: var(--radius-full); font-size: 11px; font-weight: 600;
      cursor: pointer; background: var(--bg-base); color: var(--text-primary);
      transition: all var(--dur-fast);
    }
    .sb-mode-chip.active {
      background: #fff1f1; color: var(--brand-primary);
      border-color: var(--brand-primary);
    }
```

### Step 3.2: 업로드 섹션 (`#sidebarScroll`) HTML 채우기

Task 2에서 추가한 `<div class="ds-sidebar-scroll" id="sidebarScroll">` 내부를 다음으로 채움:

- [ ] `id="sidebarScroll"` 내부에 다음 HTML 삽입:

```html
        <!-- [데이터] 섹션 -->
        <div class="sb-section open" id="sbData">
          <div class="sb-section-header" onclick="toggleSidebarSection('sbData')">
            <span class="sb-section-title">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
              <span>데이터</span>
            </span>
            <svg class="sb-chevron" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="18 15 12 9 6 15"/></svg>
          </div>
          <div class="sb-section-body">
            <!-- 업로드 탭 -->
            <div style="display:flex;gap:0;margin-bottom:0;border-bottom:1px solid var(--hairline-warm);">
              <button id="tabFile" onclick="switchUploadTab('file')"
                style="padding:6px 12px;font-size:12px;font-weight:600;border:none;border-bottom:2px solid var(--brand-primary);background:var(--bg-base);color:var(--brand-primary);cursor:pointer;border-radius:4px 4px 0 0;">
                파일 업로드
              </button>
              <button id="tabPaste" onclick="switchUploadTab('paste')"
                style="padding:6px 12px;font-size:12px;font-weight:600;border:none;border-bottom:2px solid transparent;background:var(--surface-card);color:var(--text-secondary);cursor:pointer;border-radius:4px 4px 0 0;">
                CSV 붙여넣기
              </button>
            </div>
            <!-- 파일 업로드 -->
            <div id="panelFile">
              <div class="upload-area" id="uploadArea" style="position:relative;cursor:pointer;padding:20px 12px;border-radius:0 0 8px 8px;">
                <input type="file" id="fileInput" accept=".csv"
                       style="position:absolute;inset:0;width:100%;height:100%;opacity:0;cursor:pointer;z-index:10;" title="CSV">
                <div style="pointer-events:none;text-align:center;">
                  <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--text-secondary)" stroke-width="1.5" style="margin-bottom:6px;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                  <div style="font-size:12px;font-weight:600;color:var(--text-primary);">CSV 파일 업로드</div>
                  <div style="font-size:11px;color:var(--text-secondary);margin-top:2px;">클릭 또는 드래그</div>
                </div>
              </div>
            </div>
            <!-- CSV 붙여넣기 -->
            <div id="panelPaste" style="display:none;">
              <textarea id="csvPasteArea" placeholder="CSV 데이터를 붙여넣으세요..."
                style="width:100%;height:80px;padding:8px;border:1px solid var(--border-default);
                       border-radius:var(--radius-md);font-size:11px;resize:vertical;
                       font-family:monospace;color:var(--text-primary);"></textarea>
              <button class="ds-btn-primary" style="width:100%;margin-top:6px;padding:7px;" onclick="parsePastedCsv()">불러오기</button>
            </div>
          </div>
        </div>

        <!-- [필터] 섹션 -->
        <div class="sb-section open" id="sbFilter">
          <div class="sb-section-header" onclick="toggleSidebarSection('sbFilter')">
            <span class="sb-section-title">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>
              <span>필터</span>
            </span>
            <svg class="sb-chevron" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="18 15 12 9 6 15"/></svg>
          </div>
          <div class="sb-section-body">
            <span class="sb-label">분석 기준</span>
            <div class="sb-radio-group">
              <label class="sb-radio-item selected" id="sbGroupByName" onclick="setSbRadio('groupBy','소재명')">
                <input type="radio" name="groupBy" value="소재명" checked>소재명
              </label>
              <label class="sb-radio-item" id="sbGroupByFile" onclick="setSbRadio('groupBy','파일명')">
                <input type="radio" name="groupBy" value="파일명">파일명
              </label>
            </div>

            <span class="sb-label">소재 유형</span>
            <div class="sb-chip-group">
              <label class="sb-radio-item selected" id="sbChipBNR">
                <input type="checkbox" id="type_BNR" value="BNR" checked onchange="updateTypeFilter();updateSbChips()">BNR
              </label>
              <label class="sb-radio-item selected" id="sbChipVID">
                <input type="checkbox" id="type_VID" value="VID" checked onchange="updateTypeFilter();updateSbChips()">VID
              </label>
            </div>

            <span class="sb-label">캠페인</span>
            <input type="text" id="campaignSearchInput" class="sb-input" placeholder="캠페인 검색..." oninput="filterCampaignList()" style="margin-bottom:4px;">
            <div class="sb-checkbox-group" id="campaignCheckboxGroup">
              <div class="sb-checkbox-item">
                <input type="checkbox" id="campaign_all" value="" checked onchange="toggleAllCampaigns(this)">
                <label for="campaign_all" style="font-weight:700;font-size:12px;">전체 선택</label>
              </div>
            </div>
            <div class="sb-selected-count" id="campaignSelectedCount">전체 캠페인 선택됨</div>

            <span class="sb-label">날짜 범위</span>
            <div class="sb-date-row">
              <input type="date" id="startDate" class="sb-input">
              <span class="sb-date-sep">~</span>
              <input type="date" id="endDate" class="sb-input">
            </div>

            <!-- 저노출/저전환 소재 제외 토글 -->
            <div class="sb-toggle-row">
              <span class="sb-toggle-label">저노출·저전환 제외
                <span style="font-size:10px;color:var(--text-secondary);display:block;">평균의 10% 미만 소재</span>
              </span>
              <label class="sb-toggle">
                <input type="checkbox" id="lowExposureToggle" onchange="syncLowExposureToggle(this)">
                <span class="sb-toggle-track"></span>
              </label>
            </div>
          </div>
        </div>

        <!-- [가중치] 섹션 -->
        <div class="sb-section open" id="sbWeight">
          <div class="sb-section-header" onclick="toggleSidebarSection('sbWeight')">
            <span class="sb-section-title">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
              <span>가중치</span>
            </span>
            <svg class="sb-chevron" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="18 15 12 9 6 15"/></svg>
          </div>
          <div class="sb-section-body">
            <div class="sb-slider-row">
              <span class="sb-slider-label">전환수</span>
              <input type="range" class="sb-slider" id="wConv" name="wConv" min="0" max="100" value="25" oninput="updateWeightDisplay(this,'wConvVal');syncWeights()">
              <span class="sb-slider-val" id="wConvVal">25%</span>
            </div>
            <div class="sb-slider-row">
              <span class="sb-slider-label">CPA</span>
              <input type="range" class="sb-slider" id="wCpa" name="wCpa" min="0" max="100" value="25" oninput="updateWeightDisplay(this,'wCpaVal');syncWeights()">
              <span class="sb-slider-val" id="wCpaVal">25%</span>
            </div>
            <div class="sb-slider-row">
              <span class="sb-slider-label">IPM</span>
              <input type="range" class="sb-slider" id="wIpm" name="wIpm" min="0" max="100" value="25" oninput="updateWeightDisplay(this,'wIpmVal');syncWeights()">
              <span class="sb-slider-val" id="wIpmVal">25%</span>
            </div>
            <div class="sb-slider-row">
              <span class="sb-slider-label">ROAS</span>
              <input type="range" class="sb-slider" id="wRoas" name="wRoas" min="0" max="100" value="25" oninput="updateWeightDisplay(this,'wRoasVal');syncWeights()">
              <span class="sb-slider-val" id="wRoasVal">25%</span>
            </div>

            <span class="sb-label" style="margin-top:12px;">ROAS 모드</span>
            <div class="sb-chip-group">
              <span class="sb-mode-chip active" id="roasModeChipAuto" onclick="setSbRoasMode('auto')">자동</span>
              <span class="sb-mode-chip" id="roasModeChipExclude" onclick="setSbRoasMode('exclude')">공정</span>
              <span class="sb-mode-chip" id="roasModeChipStrict" onclick="setSbRoasMode('strict')">엄격</span>
              <span class="sb-mode-chip" id="roasModeChipOff" onclick="setSbRoasMode('off')">제외</span>
            </div>
            <!-- 히든 라디오 — 기존 JS 호환 -->
            <div style="display:none;">
              <input type="radio" name="roasMode" value="auto" id="_roasModeAuto" checked>
              <input type="radio" name="roasMode" value="exclude" id="_roasModeExclude">
              <input type="radio" name="roasMode" value="strict" id="_roasModeStrict">
              <input type="radio" name="roasMode" value="off" id="_roasModeOff">
            </div>
          </div>
        </div>
```

### Step 3.3: 사이드바 UI 연결 JS 함수 추가

`toggleSidebar()` 함수 아래에 추가:

- [ ] 다음 함수 추가:

```javascript
/* ── 사이드바 아코디언 ── */
function toggleSidebarSection(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.toggle('open');
  el.classList.toggle('closed');
}

/* ── 사이드바 라디오 칩 ── */
function setSbRadio(name, value) {
  document.querySelectorAll(`input[name="${name}"]`).forEach(r => {
    r.checked = r.value === value;
  });
  if (name === 'groupBy') {
    document.getElementById('sbGroupByName').classList.toggle('selected', value === '소재명');
    document.getElementById('sbGroupByFile').classList.toggle('selected', value === '파일명');
  }
}

function updateSbChips() {
  const bnr = document.getElementById('type_BNR');
  const vid = document.getElementById('type_VID');
  if (bnr) document.getElementById('sbChipBNR')?.classList.toggle('selected', bnr.checked);
  if (vid) document.getElementById('sbChipVID')?.classList.toggle('selected', vid.checked);
}

/* ── 저노출 토글 → 기존 thresholdFilter 라디오 동기화 ── */
function syncLowExposureToggle(cb) {
  const val = cb.checked ? '10' : '0';
  const radio = document.querySelector(`input[name="thresholdFilter"][value="${val}"]`);
  if (radio) radio.checked = true;
  if (typeof updateThresholdLabel === 'function') updateThresholdLabel();
}

/* ── ROAS 모드 칩 → 히든 라디오 동기화 ── */
function setSbRoasMode(mode) {
  ['auto','exclude','strict','off'].forEach(m => {
    const chip = document.getElementById(`roasModeChip${m.charAt(0).toUpperCase()+m.slice(1)}`);
    if (chip) chip.classList.toggle('active', m === mode);
    const radio = document.getElementById(`_roasMode${m.charAt(0).toUpperCase()+m.slice(1)}`);
    if (radio) radio.checked = m === mode;
  });
}

/* ── 가중치 슬라이더 표시 업데이트 ── */
function updateWeightDisplay(slider, valId) {
  const el = document.getElementById(valId);
  if (el) el.textContent = slider.value + '%';
}

/* ── 기존 JS의 가중치 슬라이더 ID 호환 (syncWeights는 calculateScores에서 읽음) ── */
function syncWeights() {
  // 기존 코드가 weightConv/weightCpa/weightIpm/weightRoas ID를 읽는다면
  // 새 sb-slider들로 값이 전달됨 — calculateScores()는 window.getWeights()나
  // querySelector('[name=wConv]')로 읽으므로 ID name 일치 확인 필요
}
```

> **주의:** 기존 `calculateScores()`가 가중치 값을 읽는 방식을 확인 후, 슬라이더 ID/name이 맞는지 검증. 기존 코드가 다른 ID(`weightConv` 등)를 사용한다면 슬라이더의 `id`와 `name`을 기존과 일치하도록 수정.

### Step 3.4: 기존 `<section id="upload">` 제거

- [ ] `<section id="upload" class="section">` ~ `</section>` (line 1101–1315) 전체 삭제
- [ ] 단, `<section>` 내부에 있던 `.settings-grid.filter-grid` (기존 필터 행)도 삭제 (이미 sidebar로 이동됨)

> **중요:** `thresholdFilter` radio 버튼들 (value=0/10/20/30)은 히든으로 body 내에 보존해야 기존 JS가 동작함:

- [ ] `</body>` 직전에 다음 히든 필터 라디오 보존 블록 추가:

```html
  <!-- 기존 JS 호환: 히든 필터 라디오 -->
  <div style="display:none;">
    <input type="radio" name="thresholdFilter" value="0" checked id="thresh-0">
    <input type="radio" name="thresholdFilter" value="10" id="thresh-10">
    <input type="radio" name="thresholdFilter" value="20" id="thresh-20">
    <input type="radio" name="thresholdFilter" value="30" id="thresh-30">
    <!-- 피로도 분석 기준 -->
    <input type="radio" name="fatigueGroupBy" value="소재명" checked>
    <input type="radio" name="fatigueGroupBy" value="파일명">
  </div>
```

### Step 3.5: 브라우저 검증

- [ ] 브라우저에서 열기 — 사이드바에 데이터/필터/가중치 3개 섹션 보이는지 확인
- [ ] 각 섹션 헤더 클릭 시 accordion 접기/펼치기 동작 확인
- [ ] 사이드바 접기 시 아이콘만 보이는지 확인
- [ ] CSV 파일 업로드 후 캠페인 드롭다운 자동 채워지는지 확인

### Step 3.6: Commit

- [ ] `git add step1_integrated.html && git commit -m "layout: migrate controls to sidebar accordion"`

---

## Task 4: Tab System + displayScoringResults 업데이트

**Files:**
- Modify: `step1_integrated.html` — main tab HTML + CSS + JS + displayScoringResults 수정

### Step 4.1: Tab CSS 추가

`<style>` 블록에 추가:

- [ ] 다음 CSS 추가:

```css
    /* ── Main Tabs ── */
    .ds-tab-bar {
      display: flex; align-items: flex-end; gap: 0;
      border-bottom: 2px solid var(--hairline-warm);
      background: var(--bg-base); padding: 0 20px; flex-shrink: 0;
    }
    .ds-tab {
      padding: 10px 18px; font-size: 13px; font-weight: 600;
      color: var(--text-secondary); background: none; border: none;
      border-bottom: 3px solid transparent; cursor: pointer;
      margin-bottom: -2px; transition: color var(--dur-fast), border-color var(--dur-fast);
    }
    .ds-tab:hover { color: var(--text-primary); }
    .ds-tab.active { color: var(--brand-primary); border-bottom-color: var(--brand-primary); }
    .ds-tab-panel { padding: 20px; }
    .ds-tab-panel.hidden { display: none; }

    /* ── Stats Row (소재 목록 탭 상단) ── */
    .ds-stats-row {
      display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px;
    }
    .ds-stat-chip {
      display: flex; flex-direction: column;
      background: var(--bg-base); border: 1px solid var(--hairline-warm);
      border-radius: var(--radius-md); padding: 10px 14px;
      min-width: 90px;
    }
    .ds-stat-chip-label { font-size: 10px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 4px; }
    .ds-stat-chip-value { font-size: 20px; font-weight: 800; color: var(--text-primary); }
```

### Step 4.2: Main content HTML 삽입

Task 2에서 추가한 `<main class="ds-main" id="mainContent">` 내부를 채움:

- [ ] `<main class="ds-main">` 내부에 다음 HTML 삽입:

```html
      <!-- 분석 레이어 바 (MMP 연동 시만 노출) -->
      <div id="analysisLayerBar" class="analysis-layer-bar" style="padding:8px 20px;background:var(--bg-base);border-bottom:1px solid var(--hairline-warm);">
        <span style="font-size:12px;font-weight:700;color:var(--text-secondary);">분석 레이어</span>
        <div class="layer-toggle-group">
          <button id="layerBtnAds" class="layer-toggle-btn active-ads" onclick="switchAnalysisLayer('ads')">Google Ads 기준</button>
          <button id="layerBtnMmp" class="layer-toggle-btn" onclick="switchAnalysisLayer('mmp')">MMP 품질 기준</button>
        </div>
        <span id="layerHint" class="layer-hint">Google Ads 종합점수 기준으로 정렬 중</span>
      </div>

      <!-- 탭 바 (결과 존재 시 노출) -->
      <nav id="mainTabBar" class="ds-tab-bar" style="display:none;">
        <button class="ds-tab active" data-tab="creative-list" onclick="switchMainTab('creative-list')">소재 목록</button>
        <button class="ds-tab" data-tab="summary" onclick="switchMainTab('summary')">전체 성과 요약</button>
        <button class="ds-tab" data-tab="fatigue" onclick="switchMainTab('fatigue')">피로도</button>
      </nav>

      <!-- 탭 패널 1: 소재 목록 -->
      <div id="tabCreativeList" class="ds-tab-panel hidden">
        <!-- 통계 칩 행 -->
        <div class="ds-stats-row">
          <div class="ds-stat-chip"><span class="ds-stat-chip-label">전체 소재</span><span class="ds-stat-chip-value" id="statTotal">0</span></div>
          <div class="ds-stat-chip"><span class="ds-stat-chip-label">최고 점수</span><span class="ds-stat-chip-value" id="statMax">0</span></div>
          <div class="ds-stat-chip"><span class="ds-stat-chip-label">평균 점수</span><span class="ds-stat-chip-value" id="statAvg">0</span></div>
          <div class="ds-stat-chip"><span class="ds-stat-chip-label">최우수</span><span class="ds-stat-chip-value" id="statExcellent" style="color:var(--brand-primary);">0</span></div>
          <div class="ds-stat-chip"><span class="ds-stat-chip-label">개선필요</span><span class="ds-stat-chip-value" id="statPoor" style="color:#6b7280;">0</span></div>
        </div>

        <!-- 필터 요약 슬롯 -->
        <div id="filterSummarySlot"></div>

        <!-- AI 인사이트 버튼 -->
        <div class="gai-section-action">
          <button class="gai-trigger-btn" onclick="runScoringAIInsight()">
            <span class="gai-btn-icon">AI 인사이트 생성</span>
          </button>
          <span class="gai-key-status" style="font-size:11.5px;font-weight:600;margin-left:auto;"></span>
        </div>
        <div id="scoringAIBox"></div>

        <!-- 정렬 바 -->
        <div id="resultSortBar" style="display:none;margin:0 0 12px;font-size:13px;color:var(--text-primary);">
          <label style="font-weight:600;margin-right:6px;">정렬</label>
          <select id="resultSortSelect" onchange="applyResultSort(this.value)" style="padding:5px 10px;border:1px solid var(--border-default);border-radius:var(--radius-md);font-size:13px;background:var(--bg-base);color:var(--text-primary);font-weight:600;">
            <option value="score">종합 점수 (기본)</option>
            <option value="ctr">CTR 풀 백분위 높은 순</option>
            <option value="cvr">CVR 풀 백분위 높은 순</option>
            <option value="cpa">CPA 풀 백분위 높은 순</option>
            <option id="resultSortMmpOpt" value="mmpscore" style="display:none;">MMP 품질점수 높은 순</option>
          </select>
          <!-- 내보내기 버튼 -->
          <button class="ds-btn-secondary" style="margin-left:12px;" onclick="exportResultHTML()">
            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            HTML 추출
          </button>
        </div>
        <div id="exportBtnContainer" style="display:none;">
          <button class="ds-btn-secondary" onclick="exportCreativeBrief()">제작 브리프 추출</button>
        </div>

        <!-- 소재 테이블 -->
        <div class="table-container">
          <table id="resultTable">
            <thead>
              <tr>
                <th>미리보기</th>
                <th>소재명</th>
                <th>유형</th>
                <th class="has-tooltip" data-tip="설치 또는 목표 행동 완료 횟수">전환 <span class="th-info">?</span></th>
                <th class="has-tooltip" data-tip="비용 ÷ 전환수 · 낮을수록 효율적">CPA <span class="th-info">?</span></th>
                <th class="has-tooltip" data-tip="(전환수 ÷ 노출수) × 1,000 · 높을수록 우수">IPM <span class="th-info">?</span></th>
                <th class="has-tooltip" data-tip="(매출 ÷ 비용) × 100% · Revenue 컬럼 없으면 —">ROAS <span class="th-info">?</span></th>
                <th class="has-tooltip" data-tip="전환수·CPA·IPM·ROAS 점수의 가중치 합산">총점 <span class="th-info">?</span></th>
                <th class="has-tooltip" data-tip="총점 기준 등급 · 최우수≥80 / 우수≥60 / 양호≥40">등급 <span class="th-info">?</span></th>
                <th class="col-pctile has-tooltip" data-tip="풀 대비 백분위 · CTR/CVR/CPA · Google Ads KPI 보유 소재">성과 <span class="th-info">?</span></th>
                <th class="col-mmp has-tooltip" data-tip="소재 품질(MMP) · D1 IPM·D1 CPI·D7 ROAS·D1 잔존 종합">MMP <span class="th-info">?</span></th>
                <th class="has-tooltip" data-tip="일별 전환수 추이">추이 <span class="th-info">?</span></th>
              </tr>
            </thead>
            <tbody id="tableBody">
              <tr><td colspan="12" style="text-align:center;padding:40px;color:var(--text-secondary);">점수 계산을 실행하세요</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 탭 패널 2: 전체 성과 요약 -->
      <div id="tabSummary" class="ds-tab-panel hidden">
        <!-- 캠페인 비교 (기존 유지) -->
        <div id="campaignCompareContainer"></div>
        <!-- 유형별 요약 (Task 6에서 교체) -->
        <div id="typeSummaryContainer"></div>
        <!-- 교차 성과 (Task 6에서 추가) -->
        <div id="crossPerformanceContainer"></div>
        <!-- AI 태그 (Task 6에서 추가) -->
        <div id="signalDistributionPanel"></div>
      </div>

      <!-- 탭 패널 3: 피로도 (Task 7에서 채움) -->
      <div id="tabFatigue" class="ds-tab-panel hidden">
        <div id="fatigueTabContent"></div>
      </div>
```

### Step 4.3: `switchMainTab()` JS 함수 추가

- [ ] 다음 함수 추가:

```javascript
/* ── 메인 탭 전환 ── */
function switchMainTab(tab) {
  const PANELS = {
    'creative-list': 'tabCreativeList',
    'summary': 'tabSummary',
    'fatigue': 'tabFatigue'
  };
  document.querySelectorAll('.ds-tab').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === tab);
  });
  Object.entries(PANELS).forEach(([key, id]) => {
    const el = document.getElementById(id);
    if (el) el.classList.toggle('hidden', key !== tab);
  });
}
```

### Step 4.4: `displayScoringResults()` 수정

`displayScoringResults()` 함수 첫 줄(`document.getElementById('results').style.display = 'block';`)을 교체:

- [ ] 해당 줄을 다음으로 교체:

```javascript
      // 탭 바 표시 + 소재 목록 탭으로 초기화
      const mainTabBar = document.getElementById('mainTabBar');
      if (mainTabBar) mainTabBar.style.display = 'flex';
      switchMainTab('creative-list');
```

- [ ] 함수 말미 `scrollToSection('results');` 줄 삭제 (탭 전환으로 대체됨)

### Step 4.5: 기존 `section#results` HTML 제거

- [ ] `<section id="results" class="section">` ~ `</section>` 전체 삭제
  - 단, 내부 통계/테이블/정렬 HTML은 이미 Task 4.2에서 새 탭 패널에 재정의했으므로 안전하게 삭제 가능

### Step 4.6: `th-info` 툴팁 CSS 추가

```css
    /* ── 컬럼 헤더 툴팁 ── */
    .th-info {
      display: inline-flex; align-items: center; justify-content: center;
      width: 14px; height: 14px; border-radius: 50%;
      background: var(--surface-sink); color: var(--text-secondary);
      font-size: 9px; font-weight: 700; cursor: help; vertical-align: middle;
      margin-left: 3px;
    }
    .has-tooltip { position: relative; }
    .has-tooltip:hover::after {
      content: attr(data-tip);
      position: absolute; top: calc(100% + 4px); left: 0; z-index: 50;
      background: var(--text-primary); color: #fff;
      font-size: 11px; line-height: 1.5; font-weight: 400;
      padding: 6px 10px; border-radius: var(--radius-md);
      white-space: pre-wrap; max-width: 220px; pointer-events: none;
      box-shadow: var(--shadow-md);
    }
```

### Step 4.7: 브라우저 검증

- [ ] CSV 파일 업로드 후 점수 계산 → 탭 바 나타나는지 확인
- [ ] 탭 클릭 시 패널 전환 확인
- [ ] 기존 결과 테이블 내용 정상 출력 확인

### Step 4.8: Commit

- [ ] `git add step1_integrated.html && git commit -m "feat: add 3-tab layout and update displayScoringResults"`

---

## Task 5: ds-table (소재 목록 탭 테이블 스타일링)

**Files:**
- Modify: `step1_integrated.html` — CSS + renderResultTableRows 수정

### Step 5.1: ds-table CSS 추가

```css
    /* ── DS Table ── */
    .ds-table { width: 100%; border-collapse: collapse; }
    .ds-table thead th {
      background: var(--surface-card);
      padding: 7px 10px;
      text-align: left;
      font-size: 10px; font-weight: 700; letter-spacing: .06em;
      text-transform: uppercase; color: var(--text-secondary);
      border-bottom: 1px solid var(--border-default);
      white-space: nowrap;
    }
    .ds-table thead th.num { text-align: right; }
    .ds-table tbody tr { border-bottom: 1px solid var(--hairline-warm); }
    .ds-table tbody tr:hover { background: var(--surface-soft); }
    .ds-table tbody tr.rank-top { border-left: 3px solid var(--brand-primary); }
    .ds-table td { padding: 7px 10px; vertical-align: middle; font-size: 13px; }
    .ds-table td.num { text-align: right; font-variant-numeric: tabular-nums; }
    .ds-table .table-container { border: 1px solid var(--hairline-warm); border-radius: var(--radius-md); overflow: hidden; }
```

### Step 5.2: `#resultTable`에 `ds-table` 클래스 추가

- [ ] Task 4.2에서 정의한 `<table id="resultTable">` 태그에 `class="ds-table"` 추가:
  `<table id="resultTable" class="ds-table">`

### Step 5.3: `renderResultTableRows()` 수정 — 1위 행 강조

`renderResultTableRows()` 함수(line 4084)는 `creatives.forEach((c, i) => { ... rows.push(...) })` 구조로 각 행의 HTML 문자열을 조립함. 템플릿 리터럴에서 `<tr>` 태그를 찾아 수정:

- [ ] `renderResultTableRows()` 내 `<tr` 생성 위치를 찾고, 다음처럼 `rank-top` 클래스 조건 추가:

```javascript
// 수정 전 (기존 패턴):
//   `<tr>`
// 수정 후:
const rowClass = i === 0 ? 'rank-top' : '';
// 그 후 템플릿 리터럴 내 <tr> → <tr class="${rowClass}">
```

구체적으로 `grep -n "<tr>" step1_integrated.html` 으로 위치 확인 후, `renderResultTableRows` 함수 내에 있는 `<tr>` 하나만 수정 (헤더 `<tr>` 제외).

### Step 5.4: 브라우저 검증

- [ ] 점수 계산 후 테이블 헤더가 uppercase 소문자 크기로 스타일링됐는지 확인
- [ ] 1위 행에 좌측 빨간 인디케이터 확인
- [ ] 행 hover 시 warm 배경 변화 확인

### Step 5.5: Commit

- [ ] `git add step1_integrated.html && git commit -m "style: apply ds-table to 소재 목록 tab"`

---

## Task 6: 전체 성과 요약 탭

**Files:**
- Modify: `step1_integrated.html` — CSS + JS 신규 함수 3개

### Step 6.1: 전체 성과 요약 탭 CSS 추가

```css
    /* ── 전체 성과 요약 탭 ── */
    .summary-block { margin-bottom: 28px; }
    .summary-block-title {
      font-size: 12px; font-weight: 700; letter-spacing: .06em;
      text-transform: uppercase; color: var(--text-secondary);
      margin-bottom: 12px; padding-bottom: 6px;
      border-bottom: 1px solid var(--hairline-warm);
    }
    /* 교차 성과 카드 */
    .cross-perf-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .cross-perf-card {
      background: var(--bg-base); border: 1px solid var(--hairline-warm);
      border-radius: var(--radius-lg); padding: 16px;
    }
    .cross-perf-card.excellent { border-top: 3px solid var(--brand-primary); }
    .cross-perf-card.poor { border-top: 3px solid #9ca3af; }
    .cross-perf-card-title { font-size: 12px; font-weight: 700; color: var(--text-secondary); margin-bottom: 10px; }
    .cross-perf-item { display: flex; align-items: center; gap: 6px; padding: 5px 0; border-bottom: 1px solid var(--hairline-warm); font-size: 12px; }
    .cross-perf-item:last-child { border-bottom: none; }
    .cross-perf-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-primary); }
    .cross-badge-ads { padding: 1px 7px; border-radius: var(--radius-full); font-size: 10px; font-weight: 700; background: #fee2e2; color: #991b1b; }
    .cross-badge-mmp { padding: 1px 7px; border-radius: var(--radius-full); font-size: 10px; font-weight: 700; background: #ccfbf1; color: #115e59; }
    /* AI 태그 */
    .ai-tag-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .ai-tag-card { background: var(--bg-base); border: 1px solid var(--hairline-warm); border-radius: var(--radius-lg); padding: 14px; }
    .ai-tag-card-title { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; color: var(--text-secondary); margin-bottom: 10px; }
    .ai-tag-chips { display: flex; flex-wrap: wrap; gap: 6px; }
    .ai-tag-chip {
      padding: 4px 12px; border-radius: var(--radius-full);
      font-size: 12px; font-weight: 600; cursor: pointer;
      background: var(--surface-card); color: var(--text-primary);
      border: 1px solid var(--hairline-warm);
      transition: all var(--dur-fast); user-select: none;
    }
    .ai-tag-chip:hover { border-color: var(--text-primary); }
    .ai-tag-chip.selected { background: var(--text-primary); color: var(--text-on-brand); border-color: var(--text-primary); }
    /* 선택 태그 소재 리스트 패널 */
    .ai-tag-panel {
      display: none; margin-top: 16px; background: var(--bg-base);
      border: 1px solid var(--hairline-warm); border-radius: var(--radius-lg);
      overflow: hidden;
    }
    .ai-tag-panel.visible { display: block; }
    .ai-tag-panel-header {
      display: flex; align-items: center; gap: 8px;
      padding: 10px 14px; background: var(--surface-card);
      border-bottom: 1px solid var(--hairline-warm);
    }
    .ai-tag-panel-title { font-size: 12px; font-weight: 700; color: var(--text-secondary); }
    .ai-tag-panel-count { font-size: 12px; font-weight: 700; color: var(--text-primary); }
    .ai-tag-panel-clear { margin-left: auto; font-size: 11px; font-weight: 600; color: var(--brand-primary); cursor: pointer; background: none; border: none; }
    .ai-selected-badges { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
    .ai-selected-badge { padding: 2px 8px; border-radius: var(--radius-full); font-size: 10px; font-weight: 700; background: var(--text-primary); color: #fff; }
```

### Step 6.2: `renderTypeSummaryTable()` 함수 추가 (기존 `renderTypeSummary` 대체)

기존 `renderTypeSummary()` 함수를 찾아서, 그 **바로 아래**에 새 함수 추가:

- [ ] 다음 함수를 추가:

```javascript
/* ── 전체 성과 요약: 유형별 평균 ds-table ── */
function renderTypeSummaryTable(creatives) {
  const container = document.getElementById('typeSummaryContainer');
  if (!container) return;

  const types = {};
  (creatives || []).forEach(c => {
    const t = c.유형 || 'ETC';
    if (!types[t]) types[t] = { count: 0, convSum: 0, cpaSum: 0, ipmSum: 0, scoreSum: 0, mmpSum: 0, mmpCount: 0 };
    types[t].count++;
    types[t].convSum  += Number(c['전환'] || 0);
    types[t].cpaSum   += Number(c['CPA']  || 0);
    types[t].ipmSum   += Number(c['IPM']  || 0);
    types[t].scoreSum += Number(c.TotalScore || 0);
    const mmpScore = c.meta?.mmp_quality_score?.total;
    if (mmpScore != null) { types[t].mmpSum += mmpScore; types[t].mmpCount++; }
  });

  const rows = Object.entries(types).map(([type, d]) => {
    const n = d.count;
    const avgMmp = d.mmpCount > 0 ? (d.mmpSum / d.mmpCount).toFixed(1) : '—';
    return `<tr>
      <td>${escapeHtml(type)}</td>
      <td class="num">${n}</td>
      <td class="num">${(d.convSum/n).toFixed(0)}</td>
      <td class="num">${d.cpaSum > 0 ? '₩'+(d.cpaSum/n).toFixed(0) : '—'}</td>
      <td class="num">${(d.ipmSum/n).toFixed(2)}</td>
      <td class="num">${(d.scoreSum/n).toFixed(1)}</td>
      <td class="num">${avgMmp}</td>
    </tr>`;
  }).join('');

  container.innerHTML = `
    <div class="summary-block">
      <div class="summary-block-title">유형별 평균 성과</div>
      <table class="ds-table">
        <thead>
          <tr>
            <th>유형</th><th class="num">소재수</th>
            <th class="num">평균 전환</th><th class="num">평균 CPA</th>
            <th class="num">평균 IPM</th><th class="num">평균 총점</th>
            <th class="num">MMP 품질</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}
```

### Step 6.3: `computeCrossPerformance()` + `renderCrossPerformanceCards()` 추가

- [ ] 다음 함수 2개 추가:

```javascript
/* ── 교차 성과: Ads 상위30% × MMP 상위30% ── */
function computeCrossPerformance(creatives) {
  const withBoth = (creatives || []).filter(c =>
    c.TotalScore != null && c.meta?.mmp_quality_score?.total != null
  );
  if (withBoth.length < 3) return null;

  const n = withBoth.length;
  const top30 = Math.ceil(n * 0.3);
  const bottom30 = Math.ceil(n * 0.3);

  const byAds = [...withBoth].sort((a, b) => b.TotalScore - a.TotalScore);
  const byMmp = [...withBoth].sort((a, b) =>
    b.meta.mmp_quality_score.total - a.meta.mmp_quality_score.total
  );

  const adsTopSet  = new Set(byAds.slice(0, top30).map(c => c.key || c['소재명']));
  const adsBotSet  = new Set(byAds.slice(-bottom30).map(c => c.key || c['소재명']));
  const mmpTopSet  = new Set(byMmp.slice(0, top30).map(c => c.key || c['소재명']));
  const mmpBotSet  = new Set(byMmp.slice(-bottom30).map(c => c.key || c['소재명']));

  const excellent = withBoth.filter(c => {
    const k = c.key || c['소재명'];
    return adsTopSet.has(k) && mmpTopSet.has(k);
  }).sort((a, b) => b.TotalScore - a.TotalScore).slice(0, 5);

  const poor = withBoth.filter(c => {
    const k = c.key || c['소재명'];
    return adsBotSet.has(k) && mmpBotSet.has(k);
  }).sort((a, b) => a.TotalScore - b.TotalScore).slice(0, 5);

  return { excellent, poor };
}

function renderCrossPerformanceCards(crossData) {
  const container = document.getElementById('crossPerformanceContainer');
  if (!container) return;
  if (!crossData) { container.innerHTML = ''; return; }

  const makeItem = c => {
    const name = c.key || c['소재명'] || '';
    const adsScore = c.TotalScore?.toFixed(1) ?? '—';
    const mmpScore = c.meta?.mmp_quality_score?.total?.toFixed(1) ?? '—';
    return `<div class="cross-perf-item">
      <span class="cross-perf-name" title="${escapeHtml(name)}">${escapeHtml(name)}</span>
      <span class="cross-badge-ads">${adsScore}</span>
      <span class="cross-badge-mmp">${mmpScore}</span>
    </div>`;
  };

  const exItems = crossData.excellent.length > 0
    ? crossData.excellent.map(makeItem).join('')
    : '<div style="font-size:12px;color:var(--text-secondary);padding:8px 0;">해당 소재 없음</div>';
  const poItems = crossData.poor.length > 0
    ? crossData.poor.map(makeItem).join('')
    : '<div style="font-size:12px;color:var(--text-secondary);padding:8px 0;">해당 소재 없음</div>';

  container.innerHTML = `
    <div class="summary-block">
      <div class="summary-block-title">Google Ads × MMP 교차 성과</div>
      <div class="cross-perf-grid">
        <div class="cross-perf-card excellent">
          <div class="cross-perf-card-title">두 지표 모두 우수</div>
          ${exItems}
        </div>
        <div class="cross-perf-card poor">
          <div class="cross-perf-card-title">두 지표 모두 저조</div>
          ${poItems}
        </div>
      </div>
    </div>`;
}
```

### Step 6.4: `renderSignalDistribution()` 수정 → AI 태그 형식

기존 `renderSignalDistribution()` 함수 내부의 렌더링 로직을 수정:

- [ ] 함수 내 `panel.innerHTML = ...` 부분에서 기존의 `signal-dist-card` 방식을 다음으로 교체:

```javascript
  // 태그 칩 렌더
  const makeChips = (arr, type) =>
    arr.slice(0, 8).map(([label, cnt]) =>
      `<span class="ai-tag-chip" data-tag="${escapeHtml(label)}" data-type="${type}"
            onclick="toggleAiTag(this,'${type}')">${escapeHtml(label)} <span style="font-size:10px;opacity:.6;">${cnt}</span></span>`
    ).join('');

  panel.innerHTML = `
    <div class="summary-block">
      <div class="summary-block-title">AI 태그</div>
      <div class="ai-tag-grid">
        <div class="ai-tag-card">
          <div class="ai-tag-card-title">강점 태그</div>
          <div class="ai-tag-chips">${makeChips(strengths, 'strength')}</div>
        </div>
        <div class="ai-tag-card">
          <div class="ai-tag-card-title">약점 태그</div>
          <div class="ai-tag-chips">${makeChips(weaknesses, 'weakness')}</div>
        </div>
      </div>
      <div id="aiTagPanel" class="ai-tag-panel">
        <div class="ai-tag-panel-header">
          <div class="ai-tag-panel-title">선택된 태그</div>
          <div class="ai-selected-badges" id="aiSelectedBadges"></div>
          <div class="ai-tag-panel-count" id="aiTagPanelCount"></div>
          <button class="ai-tag-panel-clear" onclick="clearAllAiTags()">전체 해제</button>
        </div>
        <div id="aiTagCreativeList" style="padding:12px;"></div>
      </div>
    </div>`;
  panel.style.display = 'block';
```

### Step 6.5: `toggleAiTag()` + `renderTagCreativeList()` 추가

- [ ] 다음 함수 추가:

```javascript
/* ── AI 태그 다중 선택 ── */
window._selectedAiTags = new Set();

function toggleAiTag(el, type) {
  const tag = el.dataset.tag;
  if (window._selectedAiTags.has(tag)) {
    window._selectedAiTags.delete(tag);
    el.classList.remove('selected');
  } else {
    window._selectedAiTags.add(tag);
    el.classList.add('selected');
  }
  renderTagCreativeList(window.currentCreatives || []);
}

function clearAllAiTags() {
  window._selectedAiTags.clear();
  document.querySelectorAll('.ai-tag-chip.selected').forEach(el => el.classList.remove('selected'));
  renderTagCreativeList([]);
}

function renderTagCreativeList(creatives) {
  const panel = document.getElementById('aiTagPanel');
  const listEl = document.getElementById('aiTagCreativeList');
  const badgesEl = document.getElementById('aiSelectedBadges');
  const countEl = document.getElementById('aiTagPanelCount');
  if (!panel || !listEl) return;

  const selected = [...window._selectedAiTags];
  if (selected.length === 0) { panel.classList.remove('visible'); return; }

  // 선택 태그 배지 갱신
  if (badgesEl) {
    badgesEl.innerHTML = selected.map(t =>
      `<span class="ai-selected-badge">${escapeHtml(t)}</span>`
    ).join('');
  }

  // 유니온 매칭
  const matching = (creatives || []).filter(c => {
    const tags = [
      ...(c.meta?.strengths || []),
      ...(c.meta?.weaknesses || []),
      ...(c.meta?.test_ideas || [])
    ];
    return selected.some(t => tags.includes(t));
  });

  if (countEl) countEl.textContent = `${matching.length}개 소재`;

  const rows = matching.map((c, i) => {
    const name = c.key || c['소재명'] || '';
    const type = c.유형 || '';
    const adsScore = c.TotalScore?.toFixed(1) ?? '—';
    const mmpScore = c.meta?.mmp_quality_score?.total?.toFixed(1) ?? '—';
    const allTags = [
      ...(c.meta?.strengths || []).map(t => ({ t, cls: 'cross-badge-ads' })),
      ...(c.meta?.weaknesses || []).map(t => ({ t, cls: 'cross-badge-mmp' }))
    ];
    const matchedBadges = allTags
      .filter(({ t }) => selected.includes(t))
      .map(({ t, cls }) => `<span class="${cls}">${escapeHtml(t)}</span>`)
      .join('');
    return `<div class="cross-perf-item">
      <span style="font-size:11px;color:var(--text-secondary);width:20px;text-align:right;">${i+1}</span>
      <span class="cross-perf-name" title="${escapeHtml(name)}">${escapeHtml(name)}</span>
      <span style="display:flex;gap:3px;flex-wrap:wrap;">${matchedBadges}</span>
      <span style="font-size:11px;color:var(--text-secondary);">${escapeHtml(type)}</span>
      <span class="cross-badge-ads">${adsScore}</span>
      <span class="cross-badge-mmp">${mmpScore}</span>
    </div>`;
  }).join('') || '<div style="font-size:12px;color:var(--text-secondary);">매칭 소재 없음</div>';

  listEl.innerHTML = rows;
  panel.classList.add('visible');
}
```

### Step 6.6: `displayScoringResults()` 내 요약 탭 렌더 함수 호출 추가

기존 `renderTypeSummary(creatives);` 호출 줄을 다음으로 교체:

- [ ] 기존 `renderTypeSummary(creatives);` → `renderTypeSummaryTable(creatives);` 로 변경
- [ ] 그 바로 아래에 추가:

```javascript
      const crossData = computeCrossPerformance(creatives);
      renderCrossPerformanceCards(crossData);
      // AI 태그 선택 초기화
      window._selectedAiTags = new Set();
```

### Step 6.7: 브라우저 검증

- [ ] 점수 계산 후 "전체 성과 요약" 탭 클릭
- [ ] 유형별 평균 성과 ds-table 출력 확인
- [ ] AI 태그 칩 다중 클릭 → 소재 리스트 패널 하단 노출 확인
- [ ] "전체 해제" 클릭 시 패널 숨김 확인

### Step 6.8: Commit

- [ ] `git add step1_integrated.html && git commit -m "feat: 전체 성과 요약 탭 — 유형 요약, 교차 성과, AI 태그 다중선택"`

---

## Task 7: 피로도 탭 + 텍스트 최소화 Polish

**Files:**
- Modify: `step1_integrated.html` — 피로도 탭 내용 + 이모지 제거

### Step 7.1: 피로도 탭 HTML (`#fatigueTabContent`) 채우기

`<div id="fatigueTabContent">` 내부를 다음으로 채움:

- [ ] 다음 HTML 삽입:

```html
        <!-- 기간 설정 바 -->
        <div style="display:flex;align-items:center;flex-wrap:wrap;gap:12px;padding:14px 0;border-bottom:1px solid var(--hairline-warm);margin-bottom:16px;">
          <div style="display:flex;align-items:center;gap:6px;">
            <span style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:var(--text-secondary);">기준 기간</span>
            <input type="date" id="baselineStart" class="sb-input" style="width:130px;">
            <span style="font-size:11px;color:var(--text-secondary);">~</span>
            <input type="date" id="baselineEnd" class="sb-input" style="width:130px;">
          </div>
          <div style="display:flex;align-items:center;gap:6px;">
            <span style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:var(--text-secondary);">비교 기간</span>
            <input type="date" id="comparisonStart" class="sb-input" style="width:130px;">
            <span style="font-size:11px;color:var(--text-secondary);">~</span>
            <input type="date" id="comparisonEnd" class="sb-input" style="width:130px;">
          </div>
          <button class="ds-btn-primary" onclick="runFatigueAnalysis()" style="padding:8px 20px;font-size:13px;">적용</button>
          <button class="ds-btn-ghost" onclick="resetFatigue()">초기화</button>
        </div>

        <!-- 피로도 테이블 -->
        <div class="table-container">
          <table id="fatigueTable" class="ds-table">
            <thead>
              <tr>
                <th>소재명</th>
                <th>유형</th>
                <th class="num has-tooltip" data-tip="기준 기간 평균 CPA">기준 CPA <span class="th-info">?</span></th>
                <th class="num has-tooltip" data-tip="비교 기간 평균 CPA">비교 CPA <span class="th-info">?</span></th>
                <th class="num has-tooltip" data-tip="(비교 CPA - 기준 CPA) / 기준 CPA × 100%">변화율 <span class="th-info">?</span></th>
                <th>추이</th>
                <th class="has-tooltip" data-tip="Fresh: &lt;10% / Stable: 10~30% / Warning: 30~60% / Tired: &gt;60%">피로도 <span class="th-info">?</span></th>
              </tr>
            </thead>
            <tbody id="fatigueTableBody">
              <tr><td colspan="7" style="text-align:center;padding:40px;color:var(--text-secondary);">기간을 설정하고 적용 버튼을 클릭하세요</td></tr>
            </tbody>
          </table>
        </div>
```

### Step 7.2: 피로도 분석용 필터 컨트롤 — 피로도 탭 상단에 추가

피로도에도 분석기준/소재유형/캠페인 필터가 필요. 기간 설정 바 **앞**에 삽입:

- [ ] 기간 설정 바 앞에 다음 필터 행 추가:

```html
        <!-- 피로도 전용 필터 (간소) -->
        <div style="display:flex;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:12px;">
          <span style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:var(--text-secondary);">분석 기준</span>
          <div style="display:flex;gap:5px;">
            <label style="display:flex;align-items:center;gap:4px;padding:4px 10px;border:1px solid var(--border-default);border-radius:var(--radius-full);font-size:12px;cursor:pointer;">
              <input type="radio" name="fatigueGroupBy" value="소재명" checked style="accent-color:var(--brand-primary);">소재명
            </label>
            <label style="display:flex;align-items:center;gap:4px;padding:4px 10px;border:1px solid var(--border-default);border-radius:var(--radius-full);font-size:12px;cursor:pointer;">
              <input type="radio" name="fatigueGroupBy" value="파일명" style="accent-color:var(--brand-primary);">파일명
            </label>
          </div>
          <span style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:var(--text-secondary);margin-left:8px;">소재 유형</span>
          <label style="display:flex;align-items:center;gap:4px;font-size:12px;cursor:pointer;">
            <input type="checkbox" id="fatigue_type_BNR" value="BNR" checked onchange="updateFatigueTypeFilter()" style="accent-color:var(--brand-primary);">BNR
          </label>
          <label style="display:flex;align-items:center;gap:4px;font-size:12px;cursor:pointer;">
            <input type="checkbox" id="fatigue_type_VID" value="VID" checked onchange="updateFatigueTypeFilter()" style="accent-color:var(--brand-primary);">VID
          </label>
        </div>
```

### Step 7.3: 기존 `section#fatigue` 제거

- [ ] `<section id="fatigue" class="section">` ~ `</section>` (line 1451–1590) 전체 삭제
- [ ] `<section id="chart">` (line 1592–1598) 전체 삭제 (차트 섹션은 이 리디자인 범위 외)

### Step 7.4: 이모지 텍스트 전면 교체

다음 4개 위치가 이모지를 포함하며 각각 처리법이 다름:

**1) 파비콘** (line 8, `data:image/svg+xml,...📊...`):
- [ ] 다음으로 교체 (인라인 SVG 파비콘):
```html
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23DC2828' stroke-width='2'%3E%3Cpath d='M3 3v18h18'/%3E%3Cpath d='m19 9-5 5-4-4-3 3'/%3E%3C/svg%3E">
```

**2) `section-title` 이모지 레이블들** — Task 4.5/7.3에서 해당 섹션 자체가 삭제되므로 자동 제거됨. 별도 조치 불필요.

**3) JS 내 이모지 포함 문자열** (ROAS 모드 라벨, 필터 요약 텍스트):
- [ ] JS 내 `icon = '💰'`, `icon = '🚫'`, `icon = '🎯'`, `icon = '📊'` 를 텍스트로 교체:
  - `'💰'` → `'[ROAS]'`
  - `'🚫'` → `'[제외]'`
  - `'🎯'` → `'[공정]'`
  - `'📊'` → `'[엄격]'`
  - `countLine` 내 `✅` → 제거, `🚫` → `✕`

**4) 버튼/라벨 이모지** — Tasks 2~4에서 새 HTML로 교체되면서 자동 제거됨.

- [ ] 작업 후 검증: `grep -c "[\U0001F000-\U0001FFFF]" step1_integrated.html` 결과가 0이면 완료 (또는 VSCode에서 정규식 `[\u{1F300}-\u{1FFFF}]` 검색)

### Step 7.5: Lucide 아이콘 초기화

`</body>` 직전에 추가:

- [ ] 다음 스크립트 추가:

```html
  <script>
    if (typeof lucide !== 'undefined') lucide.createIcons();
  </script>
```

### Step 7.6: 기존 하단 안내 텍스트 제거

현재 섹션들에 있는 여러 줄 설명 텍스트 블록들 정리:

- [ ] `<small>` 태그나 `style="color: #6b7280; font-size: 11px;"` 형태의 설명 텍스트 중 사이드바 항목 옆 설명(예: "시작 날짜와 종료 날짜를 선택하세요", "매출 데이터가 늦게 들어오는 환경에서..." 등) 삭제
- [ ] ROAS 모드 설명 텍스트 블록(`매출 데이터가 늦게 들어오는 환경에서...`) 삭제 (이미 사이드바 칩으로 대체됨)

### Step 7.7: 최종 브라우저 검증

- [ ] 브라우저에서 파일 열기 (오류 없이 로드)
- [ ] CSV 업로드 → 점수 계산 실행 → 탭 바 노출 확인
- [ ] "소재 목록" 탭 → 테이블 정상 출력
- [ ] "전체 성과 요약" 탭 → 유형별 요약 + AI 태그 칩 출력
- [ ] "피로도" 탭 → 기간 설정 바 + 빈 테이블 출력
- [ ] 사이드바 접기/펼치기 동작 확인
- [ ] 사이드바 아코디언 동작 확인
- [ ] 이모지 미노출 확인

### Step 7.8: Commit

- [ ] `git add step1_integrated.html && git commit -m "feat: 피로도 탭 + 이모지 제거 Polish — 리디자인 완료"`

---

## 자체 검토 메모 (구현 전 확인 사항)

### A. 기존 JS 가중치 읽기 방식 확인

`calculateScores()` 내에서 가중치를 읽는 방식이 현재:
```javascript
const wConv = Number(document.getElementById('wConv')?.value ?? 25);
```
형태라면 새 사이드바 슬라이더 ID가 일치. 만약 현재 코드가 다른 ID를 쓴다면:
- 현재 sliders를 grep: `grep -n "weightConv\|w_conv\|convWeight" step1_integrated.html`
- 기존 ID와 일치하도록 새 슬라이더 id/name 조정

### B. 피로도 캠페인 필터 컨트롤

기존 피로도 섹션에 있던 캠페인 필터(`#fatigueCampaignCheckboxGroup`)는 이번 리디자인에서 탭 내부에 단순화. 필요 시 Task 7.2 후 추가로 포함 가능.

### C. `section#chart` 처리

차트 섹션은 범위 외로 Task 7.3에서 삭제. 이후 필요 시 "전체 성과 요약" 탭의 추가 블록으로 재도입 가능.

### D. CSS 충돌

기존 CSS 클래스(`.btn`, `.setting-group` 등)가 사이드바 내부에서도 일부 동작할 수 있음. 새 `.ds-btn-primary`, `.sb-*` 클래스로 전환 후 기존 `.btn` 클래스 CSS는 보존하되 점진적으로 대체.
