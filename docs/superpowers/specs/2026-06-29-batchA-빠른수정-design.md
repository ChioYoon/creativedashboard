# Batch A — Step1 빠른 수정 3건 설계

**작성일:** 2026-06-29
**대상:** `step1_integrated.html` (전부 인라인)
**범위:** backlog 묶음 A — ① MMP 기준 리네임 · ④ 지표 툴팁 버그 · ⑦ HTML 추출 필터 접기

## ① 'MMP 품질 기준' → 'MMP 기준' 리네임

레이어 토글 라벨만 변경. 점수 지표명(`MMP 품질점수` 등)은 유지.

- 1665행 버튼: `MMP 품질 기준` → `MMP 기준`
- 5947행 힌트: `<strong>MMP 품질 기준</strong>` → `<strong>MMP 기준</strong>`
- 2308행 주석: `Google Ads 기준 / MMP 품질 기준` → `… / MMP 기준`

**유지(무변경)**: `MMP 품질점수`, `종합점수 (MMP 품질)`(2276), `MMP 품질 상·하위`(5923/5927) — 점수 지표 고유명.

## ④ 지표 툴팁 버그 — `.has-tooltip` 중복 정의 충돌 제거

**원인**: `.has-tooltip:hover::after` 가 두 곳에 정의되어 충돌.
- 블록1(1254-1291): `::after` 위쪽(`bottom:calc(100%+6px)`)·중앙(`left:50%; translateX(-50%)`)·`max-width:280px`·`white-space:pre-line` + `::before` 화살표 + hover opacity.
- 블록2(1345-1354): `:hover::after` 아래쪽(`top:calc(100%+4px)`)·`left:0`·`max-width:220px`·`white-space:pre-wrap` (specificity 높아 hover 시 우선).

겹쳐서 `top`+`bottom` 동시 지정·`left:0`+잔존 `translateX(-50%)`·max-width/white-space 불일치 → 박스 오정렬, 한글 줄바꿈 깨짐.

**해결**: 단일 정의로 통합. 헤더가 표 상단이라 **아래쪽(top) 배치** + 한글 깔끔 줄바꿈.

블록1(1254-1291)을 아래로 교체:
```css
.has-tooltip { position: relative; cursor: help; }
.has-tooltip::after {
  content: attr(data-tip);
  position: absolute;
  top: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  background: #1f2937;
  color: #fff;
  padding: 7px 11px;
  border-radius: 6px;
  font-size: 11.5px;
  font-weight: 400;
  line-height: 1.55;
  white-space: normal;
  word-break: keep-all;
  width: max-content;
  max-width: 260px;
  text-align: left;
  pointer-events: none;
  opacity: 0;
  transition: opacity .18s;
  z-index: 9999;
}
.has-tooltip::before {
  content: '';
  position: absolute;
  top: calc(100% + 3px);
  left: 50%;
  transform: translateX(-50%);
  border: 5px solid transparent;
  border-bottom-color: #1f2937;
  pointer-events: none;
  opacity: 0;
  transition: opacity .18s;
  z-index: 9999;
}
.has-tooltip:hover::after,
.has-tooltip:hover::before { opacity: 1; }
```

그리고 블록2의 **충돌하는 `.has-tooltip:hover::after`(1346-1354)는 제거**한다. `.th-info`(1338-1344)와 `.has-tooltip { position: relative; }`(1345)는 유지(아이콘 스타일·중복이지만 무해).

- 핵심: `width: max-content; max-width: 260px; white-space: normal; word-break: keep-all;` → 박스가 텍스트에 맞게 줄어들고, 한글은 어절 단위로 박스 안에서 줄바꿈.
- 단일 정의라 `top`/`bottom`·`left` 충돌 없음.

## ⑦ HTML 추출 — 필터 조건 접기

`exportResultHTML`(5354) 의 필터 조건 임베드(5416)를 `<details>` 로 감싼다(기본 접힘, 추출본 독립 HTML이라 인라인 스타일):

```js
const fsEl = document.querySelector('#filterSummarySlot .filter-summary');
const filterHtml = fsEl
  ? `<details style="margin:0 0 16px;border:1px solid #e5e7eb;border-radius:8px;padding:0;">` +
    `<summary style="cursor:pointer;padding:10px 14px;font-size:13px;font-weight:700;color:#374151;list-style:revert;">적용 필터 조건</summary>` +
    `<div style="padding:0 14px 12px;">${fsEl.outerHTML}</div></details>`
  : '';
```

(기존엔 `fsEl.outerHTML` 그대로 임베드 → 항상 펼쳐짐. 변경 후 접힘 기본.)

## 검증 (preview)

`step1_integrated.html?_=<ts>` 캐시 우회 로드.
1. **①**: 레이어 토글 버튼 텍스트 `MMP 기준` 확인. `MMP 품질점수`(정렬 옵션 등)는 그대로.
2. **④**: 컬럼 헤더 `?`(`.has-tooltip`) hover → 검은 박스가 텍스트를 감싸고(width max-content), 260px 넘으면 한글 어절 줄바꿈, 헤더 아래 배치. `getComputedStyle(::after)` 로 `white-space:normal`·`max-width:260px` 단언, 박스 너비 ≤ 260.
3. **⑦**: 분석 실행 후 HTML 추출 → 파일 열어 "적용 필터 조건"이 접힘(details) 상태로 시작, 클릭 시 펼쳐짐. (또는 export 생성 HTML 문자열에 `<details`·`<summary>적용 필터 조건` 포함 단언.)
4. 콘솔 error 0.

## 비목표
- 점수 지표명('MMP 품질점수' 등) 변경 없음.
- 툴팁 동작/대상(`data-tip`) 변경 없음 — CSS만.
- export 의 다른 섹션·데이터 변경 없음.
