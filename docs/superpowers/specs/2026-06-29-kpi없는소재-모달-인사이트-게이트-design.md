# KPI 없는 소재 — 모달 성과 인사이트 게이트 설계

**작성일:** 2026-06-29
**대상:** `step1_integrated.html` — `buildSignalChipsHtml` / `buildInsightBlocksHtml` + 신규 `hasPerfData` 헬퍼

## 목표

미집행(Google Ads·MMP 성과 데이터 없음) 소재의 상세 모달에서 **성과 추측성 분석(인사이트·가설·차주 변주)을 숨긴다.** 이들은 KPI 없이 시각만으로 도출된 가설이라 집행 전엔 오해를 부를 수 있다. 대신 "집행 후 추가" 안내를 보인다. **강점·약점(시각 근거)·제작 의도는 유지**(집행 전에도 "이 소재가 시각적으로 무엇을 하는가"는 유의미).

## 배경 — 점수·등급은 이미 게이트됨

점수·등급은 현재 코드에서 이미 미집행 시 숨겨진다(이번 작업 대상 아님):
- 테이블 행(5145·5150-5151): `hasAds = c._ads && c._ads.imp > 0` → 없으면 점수·등급 `—`.
- 모달 종합점수(6723-6725): `_ads.imp>0` 아니면 "— / Google Ads 데이터 없음".

## 범위

**대상 (in scope)** — `step1_integrated.html`
- 신규 `hasPerfData(creative)` 헬퍼.
- `buildSignalChipsHtml`(2162) — 미집행 시 가설·차주변주 그룹 제외.
- `buildInsightBlocksHtml`(2190) — 미집행 시 one_line_insight 숨김 + 안내 문구.

**비대상 (무변경)**
- 점수·등급(이미 게이트됨), 강점·약점·제작 의도 렌더, 데이터·파이프라인·캐싱.
- 라이브 대시보드(별도, 추후).

## 설계

### 게이트 — 신규 `hasPerfData(creative)`

```js
function hasPerfData(creative) {
  const c = creative || {};
  const m = c.meta || {};
  const ads = !!(c._ads && c._ads.imp > 0);
  const mmp = !!(m.mmp_quality_score && m.mmp_quality_score.total != null);
  return ads || mmp;
}
```

기존 게이트(`_ads.imp>0`, `mmp_quality_score.total`)와 일치. 미집행(zeus형: ads·mmp 모두 없음) → `false`.

### `buildSignalChipsHtml` — 미집행 시 가설·변주 제외

`groups` 배열을 `hasPerfData` 기준으로 필터한다. 미집행이면 `hypothesis`·`test_ideas` 그룹을 제외하고 `strengths`·`weaknesses`만 렌더.

```js
function buildSignalChipsHtml(creative) {
  const meta = (creative && creative.meta) || {};
  const perf = hasPerfData(creative);
  const groups = [
    { label: '강점',      items: meta.strengths,  cls: 'signal-chip-strength',   evCls: 'evidence-strength', evidences: meta.strength_evidence },
    { label: '약점',      items: meta.weaknesses, cls: 'signal-chip-weakness',   evCls: 'evidence-weakness', evidences: meta.weakness_evidence },
    ...(perf ? [
      { label: '가설',      items: meta.hypothesis, cls: 'signal-chip-hypothesis', evCls: null,                evidences: null },
      { label: '차주 변주', items: meta.test_ideas, cls: 'signal-chip-testidea',   evCls: 'evidence-testidea', evidences: meta.improvement_actions, evPrefix: '→ ' },
    ] : []),
  ];
  // (이하 기존 렌더 로직 동일)
}
```

### `buildInsightBlocksHtml` — 미집행 시 인사이트 숨김 + 안내

미집행이면 one_line_insight 대신 안내 문구를 반환(kpi_reality_check은 미집행 시 이미 null).

```js
function buildInsightBlocksHtml(creative) {
  const meta = (creative && creative.meta) || {};
  if (!hasPerfData(creative)) {
    return `<div class="signal-insight signal-insight-pending"><span class="signal-insight-key">안내</span>` +
           `<div class="signal-insight-lead">캠페인 집행 후 성과 인사이트(가설·차주 변주)가 추가됩니다. 현재는 시각 분석(강점·약점·제작 의도)만 제공됩니다.</div></div>`;
  }
  const insight = ((meta.one_line_insight || meta.marketer_insight) || '').trim();
  const reality = (meta.kpi_reality_check || '').trim();
  if (!insight && !reality) return '';
  const lead = insight ? `<div class="signal-insight-lead">${escapeHtml(insight)}</div>` : '';
  const body = reality ? `<div class="signal-insight-body">${escapeHtml(reality)}</div>` : '';
  return `<div class="signal-insight"><span class="signal-insight-key">인사이트</span>${lead}${body}</div>`;
}
```

`.signal-insight-pending` 는 기존 `.signal-insight` 의 muted 변형(회색 톤) — 별도 색 없이 기존 클래스 재사용 + 인라인 회색이면 충분.

## 검증 (preview 기반)

`preview_eval` — KPI 없는 소재 / 있는 소재 합성 후 두 함수 출력 단언:

1. **미집행 소재** (`_ads` 없음·mmp null): `buildSignalChipsHtml` 출력에 "가설"·"차주 변주" 라벨 **없음**, "강점"·"약점" **있음**. `buildInsightBlocksHtml` 출력에 one_line_insight 텍스트 **없음**, 안내 문구 **있음**.
2. **집행 소재** (`_ads.imp>0`): 가설·차주변주·인사이트 모두 **표시**(무회귀).
3. 모달 실제 렌더(zeus형 소재) screenshot — 강·약점·의도 + 안내, 가설·변주·인사이트 없음.
4. 콘솔 error 0.

## 비목표 (non-goals)

- 점수·등급 변경 없음(이미 게이트됨).
- 강점·약점·제작 의도·기본 태그 변경 없음.
- 데이터/파이프라인/프롬프트/캐싱 변경 없음(가설·변주는 데이터에 그대로 — UI에서만 숨김 → 집행 후 자동 노출).
