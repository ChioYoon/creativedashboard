# MMP channel/media_source 통합 설계 — media 축 정합

> 상태: 설계(미구현) · 작성 2026-08-06 · 선행 커밋 `1013745`(campaign_canonical media 이름앵커 픽스)

## 1. 목표

캠페인명 파싱에만 의존하던 `media`를, MMP(Airbridge/AppsFlyer)가 제공하는 **channel/media_source 구조화 필드**와 결합해 정합성·신뢰도를 높인다. 非Google 매체는 네이밍 규율에 의존하지 않도록 한다.

## 2. 현황 — 매체 신호가 2개, 서로 단절

| 신호 | 위치 | 성격 | 커버리지 |
|------|------|------|----------|
| `campaign_canonical[name].media` | 타이틀 레벨 맵 (`main.py:1221` `build_campaign_canonical`) | 캠페인명 파싱(이름앵커, 방금 픽스) | 전 캠페인(Google+非Google) |
| `creative.mmp_channels[]`, `creative.mmp_daily[].channel` | 소재 레벨 (`schemas.py:496,526`) | MMP 실측 채널(구조화 필드) | 非Google만(MMP가 google.adwords 제외) |

→ 두 신호가 **이미 JSON에 다 있으나 연결 안 됨**. `mmp_channels`는 표시용으로만 쓰이고 `media` 축 산출엔 미반영.

## 3. 실측 데이터가 보여준 쟁점 (2026-08-06 런)

### (a) 채널 표기 불일치 — 정규화 맵이 핵심 작업
| 실제 매체 | Airbridge(zeus) | AppsFlyer(gd) | 이름파싱 토큰 |
|-----------|-----------------|---------------|---------------|
| Meta | `facebook.business` | `facebook ads` | `Meta`/`FB` |
| Moloco | `moloco` | `moloco_int` | `Moloco`/`ML` |
| TikTok | `tiktok` | `tiktokglobal_int` | `Tiktok`/`TT` |
| Appier | `appier` | `appier_int` | `Appier`/`AP` |
| Kakao | `kakao` | — | `Kakao` |
| Naver | — | `naver_int` | `NaverGFA` |
| MS | `microsoft.ads` | — | `MSN` |
| **`da`** | `da`(38건) | — | **불명 — 마케터 확인 필요** |

한 매체가 최대 3표기. 정규화 없이 합치면 대시보드 매체 축이 파편화.

### (b) 멀티채널 캠페인 (zeus 5건)
`Incross_HQ_ZEUS_KR_Tiktok_...` 등 캠페인명 media(Tiktok/Pangle)와 MMP 귀속 채널이 1:1 아님. **MMP channel이 항상 더 정확하다는 보장 없음** — 이름파싱이 더 구체적인 경우도 있음. 단순 "MMP 우선"은 정밀도 손실 위험.

## 4. 설계

### 4-1. 정규화 맵 (신규 산출물 — 도메인 결정)
`channel/media_source raw id → 표준 매체명` 단일 맵. Airbridge·AppsFlyer 변형과 대소문자 모두 흡수.
- 위치(안): `pipeline/media_normalize.py` 또는 `titles.json` 공용 상수. (이름파싱 토큰 `Meta`/`Kakao`…과 **동일 표준값**으로 수렴시켜야 두 신호가 한 축에 합쳐짐.)
- 예: `{"facebook.business":"Meta","facebook ads":"Meta","moloco":"Moloco","moloco_int":"Moloco","tiktokglobal_int":"TikTok","tiktok":"TikTok", ...}`
- **미매핑 채널은 원시값 그대로 통과 + 로그 경고**(silent drop 금지).
- `da` 등 모호값은 마케터가 정의.

### 4-2. 정합 로직 (두 신호 결합, 계층) — **이름파싱 우선 확정**
```
소재/캠페인 media =
  1) campaign_media(이름앵커)  ← 1순위 진실 (커밋 1013745, 현재 오파싱 0)
  2) normalize(MMP channel)    ← 이름파싱 공란/실패(BAD 셋) 시 폴백
충돌 시(이름파싱 ≠ MMP정규화): 이름파싱 채택 + `media_conflict` 플래그만 남겨 검수 리스트 산출(오버라이드 안 함)
```
- MMP 채널은 **폴백 + 검증(충돌 플래그)** 역할. 이름앵커가 이미 견고하므로 override 금지 → 회귀 위험 최소.
- 멀티채널 캠페인: 이름파싱 media가 대표. MMP 전체 채널은 `mmp_channels`(기존)에 리스트 유지.
- 비교·폴백 위해 MMP channel은 이름파싱 표준값(`Meta`/`Kakao`…)으로 정규화 필요.

### 4-3. 배선
- `build_campaign_canonical(campaign_names)` → `build_campaign_canonical(campaign_names, campaign_channel_map)` 로 확장. 맵은 `records`의 `mmp_daily[].(campaign_name,channel,impressions)`에서 상류 집계(호출부 `main.py:1221`에 records 이미 존재).
- 또는 소재 레벨에 `media_canonical` 필드 신설(소재별 대표 매체) — 대시보드 필터가 캠페인 맵 대신 소재 필드를 직접 쓰게. (스키마 `CreativeTag`에 1필드 추가.)
- 권장: **둘 다** — 캠페인 맵(필터용)은 정규화 채널 반영, 소재엔 `media_canonical` 추가(귀속·추천용).

## 5. 단계

1. **정규화 맵 정의** (마케터+개발) — §3(a) 표 기반, `da` 등 확정. 산출: `media_normalize` 맵 + 미매핑 경고.
2. **campaign→channel 집계 유틸** — records의 mmp_daily에서 `{campaign_name: [(channel,impressions)]}` 산출.
3. **build_campaign_canonical 확장** — 채널 맵 우선, 이름앵커 폴백, 충돌 플래그.
4. (선택) **소재 `media_canonical` 필드** 신설 — 추천/귀속 정확도용.
5. **검증** — 라이브 재파싱으로 매체 축 파편화 0(facebook 계열이 Meta 1개로), 충돌 리스트 수기 검수, 회귀 점검.

## 6. 확정 사항 (2026-08-06)
- ✅ **충돌 우선순위** — **이름파싱 우선**. MMP는 폴백+검증(충돌 플래그만). §4-2 반영.
- ✅ **산출 형태** — **둘 다**. `campaign_canonical.media`(필터용) + 소재 `media_canonical` 신설(귀속·추천용).
- ✅ **적용 범위** — **전 타이틀 동시**(zeus/gd/pepp-us/tougenanki).
- ⏳ **정규화 맵 값** — §3(a) 표준값으로 확정. `da`(zeus 38건)는 **마케터 확인 대기 → 그때까지 원시값 통과 + 경고 로그**.

## 7. 참고 파일 (현황)
- 호출부/데이터흐름: `pipeline/main.py:1221`, `_collect_campaign_names`(`main.py:61`)
- 파서: `pipeline/campaign_canonical.py`(`campaign_media` 이름앵커)
- MMP 소스·channel: `pipeline/sources/airbridge.py`(gb[1]=channel), `pipeline/sources/appsflyer.py`(media_source→channel), `pipeline/mmp.py`
- 스키마: `pipeline/schemas.py`(`mmp_channels`:496, `CreativeMmpDaily.channel`:526)
