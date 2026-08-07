# CLOOP 대시보드 — 측정 기준·항목 레퍼런스

> 코드 기준 정리 · 2026-08-07 · 소스: `pipeline/scoring.py`, `pipeline/mmp_metrics.py`, `pipeline/main.py`, `step1_integrated.html`

대시보드는 **스코어 3종 + 백분위 + 피로도** 5개 측정 체계를 사용한다.

---

## 1. 측정 항목 (지표)

### 원천 지표 (수집)
| 레이어 | 지표 | 비고 |
|--------|------|------|
| **Google Ads** | 전환, 비용, 노출수, 클릭수, 매출(Revenue) | 소재×캠페인×일별 |
| **MMP**(Airbridge/AppsFlyer) | impressions, clicks, cost, installs, **retained_d1**(D1잔존), revenue_d7, conversions | 非Google 매체, 코호트 기준 |

### 파생 지표 (계산)
| 구분 | 지표 | 공식 |
|------|------|------|
| **Google Ads** | CPA | 비용 / 전환 (전환 0 → 0) |
| | IPM | 전환 / 노출 × 1000 |
| | CTR | 클릭 / 노출 × 100 |
| | ROAS | 매출 / 비용 |
| **MMP 품질** ⚠️ | D1 IPM | D1잔존 / 노출 × 1000 (↑ 좋음) |
| | D1 CPI | 비용 / D1잔존 (↓ 좋음, 잔존0→N/A) |
| | D1 Retention | D1잔존 / 설치 × 100 (↑ 좋음, 0~100) |
| | D7 ROAS | D0~D7 누적매출 / 비용 (↑ 좋음, 비용0→N/A) |

> ⚠️ **MMP 지표는 업계표준과 다름** — 분모가 설치수가 아닌 **D1 잔존수**. 잔존 기반 품질을 강조하려는 의도(`mmp_metrics.py` 상단 주석 명시).

---

## 2. 측정 기준 (스코어링)

### ① Google Ads 성과 스코어 (메인)
`pipeline/scoring.py` = 프론트 `calculateCreativeScores` 와 동일 산출.

**공식 — Rank 기반 정규화:**
```
지표점수   = (n − Rank + 1) / n × 100
TotalScore = Σ(지표점수 × 가중치)
```
- **4지표**: 전환수 · CPA · IPM · ROAS
- **기본 가중치**: 균등 **25 / 25 / 25 / 25** (슬라이더 조정 가능)
- **동점 처리**: 값 차 0.0001 이내 → 동일 Rank 부여(다음 Rank 건너뜀)
- **특수 처리**:
  - CPA: 전환=0 소재 → **0점 강제 + 최하위**
  - IPM: 노출=0 → **0점**
  - **ROAS 3모드(auto 자동판정)**:
    - `off` — 매출 전무 → ROAS 가중치를 나머지 3지표에 재분배
    - `exclude` — 매출 보유율 < 30% → 매출 있는 소재만 ROAS 순위, 없는 소재는 제외 후 3지표 스케일
    - `strict` — 매출 보유율 ≥ 30% → 전체 ROAS 순위

**등급 (TotalScore 기준):**
| 등급 | 최우수 | 우수 | 양호 | 보통 | 개선필요 |
|------|:--:|:--:|:--:|:--:|:--:|
| 기준 | ≥80 | ≥60 | ≥40 | ≥20 | <20 |

### ② MMP 품질 스코어
`pipeline/mmp_metrics.py`. 4지표 Rank 정규화(공식·등급 ①과 동일).
- **install 기준(기본)**: 4축 균등 25% — 설치↑ · D1 CPI↓ · D1 IPM↑ · D7 ROAS↑
- **registration 기준(웹 사전예약, 예: zeus)**: 3축 균등 1/3 — 등록↑ · CPA↓ · 등록IPM↑ (**ROAS 제외**)
- None(N/A) 지표 → 해당 축 0점(최하위)

### ③ KPI 백분위
`pipeline/main.py`(약 895~929행). 소재별 풀 내 상대 위치(0~100, 높을수록 우수). 노출 **100 미만은 풀에서 제외**(노이즈).
- 항목: **CTR · CVR · CPA** 백분위 (CPA는 낮을수록 좋으므로 역방향 계산)

### ④ 피로도 (CPA 변화율 기반)
프론트(`step1_integrated.html` `buildFatiguePeriodScores`). **비교기간(최근 N일) vs 기준기간(이전 N일)** CPA 변화율로 판정.
| 상태 | fresh | stable | warning | tired | new / disappeared |
|------|:--:|:--:|:--:|:--:|:--|
| CPA 변화율 | ≤ −20% | −20~0% | 0~+20% | **> +20%** | 신규 / 소멸 |
- 기본 기간: 최근 7일 vs 이전 7일 (실적일 범위 기준)
- **경보 배지** = CPA +20% 초과 상승(tired) 소재 수
- **제외 추천** = `tired` + 비교기간 하위 20%

---

## 3. 소스 파일 맵
| 측정 | 파일 |
|------|------|
| 성과 스코어 | `pipeline/scoring.py`, `step1_integrated.html`(`calculateCreativeScores`) |
| MMP 품질 스코어 | `pipeline/mmp_metrics.py` |
| KPI 백분위 | `pipeline/main.py:895~929` |
| 피로도 | `step1_integrated.html:7382~`(`buildFatiguePeriodScores`) |
| 등급/가중치 UI | `step1_integrated.html` 계산기준 섹션 |

---

## 부록 — 소재 레코드(`public/data/{title}.json` creatives[]) 측정 관련 필드
- 성과: `전환, 비용, 노출수, 클릭수, Revenue`, 파생 `CPA/IPM/CTR/ROAS`
- 스코어: `scores{total, grade, rank, conv/cpa/ipm/roas}`
- 백분위: `kpi_percentiles{ctr, cvr, cpa}`
- MMP: `mmp_d1_ipm, mmp_d1_cpi, mmp_d1_retention, mmp_d7_roas, mmp_quality_score{...}, mmp_channels[]`
- 매체(2026-08-06 추가): `media_canonical` (표준 매체명, 노출 최다 대표)
