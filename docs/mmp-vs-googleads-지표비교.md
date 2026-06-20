# 지표 기준 비교 — Google Ads(기존) vs Airbridge MMP(신규)

작성 2026-06-17 · pepp-us 실데이터 교차검증 기반. **Push 전 지표 의미 검증용.**

> ⚠️ **2026-06-20 갱신**: 이후 대시보드가 두 레이어를 **동일 4지표 구조**(전환·CPA/D1 CPI·IPM/D1 IPM·ROAS/D7 ROAS)로 평행화하고, MMP 품질점수 4번째 축을 **D1 잔존율 → 전환(설치)** 으로 변경했습니다(D1 잔존율은 표시 지표로만 유지). 날짜는 **실적일 기준** 윈도우링, 데이터 없는 레이어는 **"—"** 표기. 현재 동작·사용법 → **[분석 레이어 사용 가이드](분석-레이어-가이드.md)**. 아래 본문은 지표 정의·측정주체 비교로 유효하나, MMP 품질점수 산식 부분은 이 변경을 감안해 읽으세요.

> 핵심: 두 레이어는 **측정 주체·어트리뷰션·시간기준·통화가 다릅니다.** 같은 "성과"라도 의미가 달라서, 대시보드에서 **별도 레이어로 분리**해 둔 이유입니다. 절대 직접 비교(예: Google CPA vs MMP CPI)하면 안 됩니다.

---

## 1. Google Ads 레이어 (기존 — 변경 없음)

**출처**: Google Ads API `ad_group_ad_asset_view` (소재=asset.name). **측정 주체 = Google.** **어트리뷰션 = Google 자체**(클릭/조회 기반 + 전환 모델링).

| 대시보드 지표 | 산식 | 원천(Google Ads API) | 의미 |
|---|---|---|---|
| 노출수 | `metrics.impressions` | Google 노출 | Google 광고가 보여진 횟수 |
| 클릭수 | `metrics.clicks` | Google 클릭 | |
| 비용 | `cost_micros / 1,000,000` | Google 지출 | **계정 통화**(Com2uS 계정 기준) |
| 전환 | `metrics.conversions` | Google 전환 | ⚠️ **Google Ads 계정에 설정된 전환 액션** 수(설치/인앱이벤트 등 — 계정 설정에 의존, 모델링 포함) |
| 매출(Revenue) | `metrics.conversions_value` | Google 전환가치 | 위 전환에 부여된 가치(실매출 아닐 수 있음) |
| CPA | 비용 / 전환 | 파생 | 전환 1건당 비용 |
| IPM | (전환 / 노출) × 1000 | 파생 | 1000노출당 **전환**(설치 아님 — Google 전환 기준) |
| ROAS | 매출 / 비용 × (대시보드 %) | 파생 | Google 전환가치 / 비용 |
| CTR | 클릭 / 노출 × 100 | 파생 | |

**주의**: 여기서 "전환"은 Google이 측정한 전환 액션이며, 그 정의는 **R팀 Google Ads 계정의 전환 설정**에 달려 있습니다(설치 전환인지, 특정 인앱 이벤트인지 확인 필요). "매출"도 Google 전환가치라 실제 인앱매출과 다를 수 있습니다.

---

## 2. Airbridge MMP 레이어 (신규 — 非Google 매체)

**출처**: Airbridge Actuals API (소재=ad_creative). **측정 주체 = MMP(Airbridge).** **어트리뷰션 = Airbridge**(매체 통합 라스트터치). **대상 = Google 外 유료 매체**(pepp의 경우 Facebook). **설계 철학: 분모를 "D1 잔존수"로 두어 낚시성 소재를 페널티.**

### 원천 메트릭 (Airbridge dataspec actual-report/metrics 실명)

| 원천 메트릭 key | Airbridge 정의(공식 설명) | 본 분석 사용처 |
|---|---|---|
| `impressions_channel` | "Impression count from Channel (4시간마다 API 갱신)" — **광고 네트워크가 보고한 노출** | D1 IPM 분모 |
| `clicks_channel` | "Click count from Channel" | (보조) |
| `cost_channel` | "Cost (Channel)" — **매체 광고비**. ⚠️ **매체 계정 통화**(pepp Facebook = USD로 확인됨) | D1 CPI·D7 ROAS 분모 |
| `app_installs` | "Installs (App)" — Airbridge 귀속 설치 | D1 Retention 분모 |
| `retention_app_open_day_1_count` | D1 잔존수 — 설치 후 **다음날 앱을 다시 연 유저 수** | D1 IPM·CPI 분자, Retention 분자 |
| `custom_revenue_j75a3l` | "Revenue - Sum - D7" — 설치 코호트의 **D0~D7 누적 인앱매출** (⚠️ 앱별 custom 메트릭) | D7 ROAS 분자 |

### 산출 품질지표 (코드 계산 — pipeline/mmp_metrics.py)

| 품질지표 | 산식 | 의미 | 방향 |
|---|---|---|---|
| **D1 IPM** | D1잔존수 / 노출(채널) × 1000 | 1000노출당 "**살아남은**" 유저 수 — 후킹+초기 정착력 | 높을수록↑ |
| **D1 CPI** | 비용(채널) / D1잔존수 | **잔존 유저 1명** 획득 비용(낚시성 페널티) | 낮을수록↑ |
| **D1 Retention** | D1잔존수 / 설치수 × 100 | 설치 후 다음날 잔존율(%) | 높을수록↑ |
| **D7 ROAS** | D7누적매출 / 비용(채널) | 설치 후 **7일 내** 광고비 회수율 | 높을수록↑ |
| 품질점수 | 위 4지표 rank 종합(균등 25%) | 비-Google 소재 품질 종합 | 높을수록↑ |

---

## 3. 핵심 차이 (직접 비교 금지 이유)

| 축 | Google Ads 레이어 | Airbridge MMP 레이어 |
|---|---|---|
| 측정 주체 | Google | MMP(Airbridge) |
| 어트리뷰션 | Google 자체(모델링 포함) | Airbridge 라스트터치(매체 통합) |
| 대상 매체 | Google 캠페인만 | **Google 外**(Facebook 등) |
| "전환" 정의 | 계정 설정 전환 액션 | 설치 / D1잔존 / D7매출 (명시적) |
| 효율 분모 | 전환·설치 | **D1 잔존수**(품질 가중) |
| 시간 기준 | 기간 누적(전환 시점) | **코호트 기반**(D1·D7) |
| 통화 | Google 계정 통화 | **매체 계정 통화(Facebook=USD)** |

---

## 4. 실데이터 교차검증 결과 (pepp Facebook, 2026-01-08~06-16)

내 계산을 Airbridge **네이티브 표준 지표**와 대조:

| 검증 | 결과 |
|---|---|
| **D1 Retention** = AB native `retention_app_open_day_1_percent` | ✅ **완전 일치**(6.43=6.43, 21.62=21.62, 12.70=12.70…) → 계산·설치분모 검증 |
| D1 IPM 분모 | AB native `ipm`은 **0**(네이티브 impressions 비활성) → `impressions_channel` 사용이 정답임 검증 ✅ |
| D1 CPI vs AB `cpi_channel` | 내 D1CPI(잔존기준) $40~80 ≫ AB cpi_channel(설치기준) $5~11 — **분모 차이(의도)**, 둘 다 정상 |
| D7 ROAS vs AB `roas_channel` | 내 D7ROAS(0.005~0.069) ≪ AB roas_channel(0.66~7.09) — **시간윈도우 차이**(D7 누적 vs 전체기간 누적) |

---

## 5. ⚠️ Push 전 확정/조정 필요 항목

1. ~~통화 라벨~~ → **✅ 처리됨 (2026-06-17, 커밋 80b84d5)**: MMP `cost_channel`(USD) → **원화 환산**. 환율 `titles.json _pipeline_airbridge_usd_to_krw`(pepp=1500) / `.env AIRBRIDGE_USD_TO_KRW`로 설정, 변경 시 재실행 반영. 비용·매출·CPI 변환, ROAS/IPM/잔존율은 비율이라 불변. 대시보드 ₩ 표기 + "USD×1,500 환산" 주석. `mmp_currency`/`mmp_fx_rate` 메타 저장.
2. **D7 ROAS 해석** → **✅ 라벨 처리됨**: 모달에 "(D0~D7 누적)" 명시. "전체 ROAS"가 아니라 **설치 후 7일 내 조기 회수율**(LTV는 이후 누적, 값이 낮은 게 정상). 장기 ROAS 필요 시 D30/D180 메트릭(custom_revenue_*)으로 확장 가능.
3. **D7 매출 메트릭이 앱별 custom**(`custom_revenue_j75a3l`): pepp 전용. 타 앱 연동 시 dataspec에서 해당 앱의 'Revenue - Sum - D7' key를 찾아 `.env AIRBRIDGE_REVENUE_D7_METRIC`로 교체.
4. **Google "전환" 정의 확인**: 대시보드 전환/매출이 Google Ads 계정에서 어떤 전환 액션·가치인지 R팀 확인 권장(설치 전환인지 등).

---

## 결론

- **계산 정확성**: D1 Retention이 Airbridge 네이티브와 정확히 일치 → 산식·원천 검증됨. 나머지 3지표도 원천 메트릭이 의도대로 매핑됨.
- **의미**: 각 지표는 명시한 정의(D1잔존 분모, D7 코호트)대로 정확히 동작. Google 레이어와는 측정체계가 달라 별도 표시.
- **조정 필요**: 통화 라벨(₩→$/매체통화), D7 ROAS 라벨(조기 회수율 명시). 이 둘 처리 후 push 권장.
