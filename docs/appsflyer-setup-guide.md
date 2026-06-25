# AppsFlyer MMP 연동 가이드

AppsFlyer를 메인 MMP로 쓰는 타이틀의 소재 성과를 대시보드에 연동합니다.

## 1. API 토큰 (담당자 1회)
1. AppsFlyer 대시보드 → 우상단 계정 → **Security Center → Manage your AppsFlyer API tokens**.
2. **API Token V2.0**(Bearer) 복사.
3. 프로젝트 `.env` 에 추가:
   ```
   APPSFLYER_API_TOKEN=복사한_토큰
   ```
   토큰은 조직 단위 1개로 계정 내 모든 앱에 사용됩니다.

## 2. 타이틀 등록 (등록부)
등록부 xlsx 에서:
- **MMP 종류** = `appsflyer`
- **MMP 앱 식별자** = AppsFlyer App ID (예 `com.com2us.rheroes.android.google.global.normal`, iOS 는 `id...`)
- **광고 성과 연동** = `Y`

> 한 타이틀에 Airbridge·AppsFlyer 둘 다 연동된 경우, **MMP 종류**가 메인을 정합니다.
> 메인만 매일 수집됩니다. 메인 전환은 MMP 종류 값을 바꾸면 됩니다(보조 식별자는 titles_overrides.json).

## 3. 동작 / 한계
- 수집: 소재(af_ad)×매체×캠페인×일자 — 노출·클릭·비용·설치·매출. **Google 매체는 항상 제외**(Google Ads는 별도 레이어).
- 비용/노출이 없는 기간·소재는 CPI·IPM·ROAS 가 '—'(설치·매출은 표시).
- v1 은 D1 잔존·코호트 D7 정밀화 미포함(후속).
