# 스펙: Google Ads 저효율 소재 자동 제외 — 추천형 + 별도 내부 도구

> 2026-08-11 · **Phase 0 실현가능성 검증 완료(통과)**. Phase 1 미착수.
> 관련 메모리: `cloop-lowperf-pause`. PoC: `scripts/gads-pause-poc.py`, `scripts/gads-remove-asset-poc.py`.

## Context

피로도 분석에서 **저효율(tired)** 판정된 Google Ads 소재를, 담당자 **승인 후 실제 Google Ads에서 중단**(추천형). 현재는 대시보드가 추천만 하고 off는 수동 → 반복작업 축소가 목표.

**확정 전제:**
- 실제 플랫폼 중단(대시보드 표시만 아님) · **추천형**(사람 승인) · **Google Ads 먼저**(Meta 후속)
- 실행 = **별도 내부 도구(localhost 웹앱, 서버측 자격증명)** — 정적·공개 대시보드는 OAuth 키를 못 담음. 도구가 서버측에서 인증 갖고 승인→실행. 호스팅=nightly PC localhost(자격증명 이미 존재).

---

## ✅ Phase 0 — 실현가능성 (검증 완료, 2026-08-11)

**핵심 발견:** 캠페인이 **UAC(App)·Demand Gen** 타입 → 소재를 **개별 pause할 링크가 없음**(campaign_asset/ad_group_asset/ad_group_ad_asset 전무). 소재가 **광고 안에 임베드** → 중단 = 광고의 **영상 asset 리스트에서 제거**(되돌리기=재추가).

- **P0-2 토큰** ✅ Standard(mutate 가능)
- **P0-1 식별** ✅ asset id + 붙은 광고(ad_group_ad)·타입 조회 가능
- **P0-3 실제 제거·복원** ✅ `AdService.mutate_ads`로 Demand Gen 광고서 제거+재추가 양방향 성공

**확정 메커니즘(Phase 1 반영):**
1. 중단 = 광고의 영상 리스트에서 대상 asset 빼서 `AdService.mutate_ads` update + `update_mask`. 복원 = 재추가.
2. **광고 타입별 필드 상이**: `DEMAND_GEN_VIDEO_RESPONSIVE_AD`→`demand_gen_video_responsive_ad.videos`(검증됨), `APP_PRE_REGISTRATION_AD`→`app_pre_registration_ad.youtube_videos`(미검증·추정), `APP_AD`→`app_ad.youtube_videos`.
3. **한 소재가 여러 광고·여러 타입**(실측: 1소재→7광고, App pre-reg 3 + Demand Gen 4) → 완전 중단하려면 **각 광고에서 제거**.
4. **최소 개수 제약**: 영상 0개 되면 API 거부 → 제거 후 ≥1 유지 가드 필수.
5. **주의**: 현재 목록을 `ad_group_ad_asset_view`(날짜 필터)로 읽으면 제거 후 잔존 표시 가능 → **광고의 라이브 영상 리스트를 직접 조회**해 재구성.

---

## 설계 (Phase 1~2)

### 아키텍처 — 별도 내부 도구 `pause_tool/`
소형 웹앱(Flask/FastAPI, localhost). 기존 `pipeline/`의 Google Ads 인증(`.secrets/google_ads.yaml`) 재사용.

```
파이프라인 → public/data/{title}.json (저효율 후보 + 소재별 붙은 광고 ref·타입)
                          │ 읽기
pause_tool (localhost, 서버측 자격증명)
   화면: 저효율 추천 소재 + 붙은 광고 목록 + [dry-run]/[실제 제거]
   승인 → 서버가 각 광고에서 asset 제거(타입별 필드·최소개수 가드) → 로그
```

### 컴포넌트
- `pipeline/sources/google_ads.py` — 소재별 붙은 광고(ad_group_ad resource·**ad type**·asset id) 수집.
- `pipeline/schemas.py` — creative에 `google_ads_ads`(광고 ref+타입 목록) 필드 → `public/data`.
- `pipeline/pause.py` (신규) — 광고 영상 리스트에서 asset 제거/재추가 순수 함수. 타입별 필드 맵·최소개수 가드·dry-run/apply. (PoC `gads-remove-asset-poc.py` 로직 정식화.)
- `pause_tool/` (신규) — localhost 웹앱: 후보 렌더 + 승인 → `pause.py` 호출.
- (선택) `pipeline/notify.py` — 결과 알림.

### 안전장치
- 사람 승인 필수 · **dry-run 기본** · 되돌리기(재추가) · 최소개수 가드 · localhost 전용 · 로그. 자동/무승인 실행 금지.

### 단계
| Phase | 내용 |
|-------|------|
| **0** | 실현가능성 — ✅ **통과** |
| **1** | `pause.py` 정식화(타입별·최소개수·라이브목록·다광고) + 커넥터 광고 ref 저장 |
| **2** | `pause_tool/` 웹앱(후보 렌더 + 승인 UI + 다광고 제거) |
| 3(후속) | 대시보드 "중단됨" 연동 · 피로도 판정 이식 · Meta 확장 |

## 검증
- Phase 1: `public/data`에 광고 ref·타입 저장 확인, `pause.py` dry-run/apply로 1소재의 전 광고 제거·복원 성공(App pre-reg 타입 포함 검증).
- Phase 2: pause_tool localhost → 저효율 후보 → 승인 → dry-run 정확 → 실제 제거(다광고) → 복원.
- 회귀: 피로도 분석·nightly·별칭 정상.

## 참고 (재사용)
- 피로도/제외 추천: `step1_integrated.html` `runFatigueAnalysis`·`fatigueExcludeReco`·`fatigueStatus`
- 상태 배지: `resolveStatus`/`statusBadgeHtml`
- Google Ads 커넥터: `pipeline/sources/google_ads.py`(`ad_group_ad_asset_view`) · auth `.secrets/google_ads.yaml` · `scripts/setup-google-ads.ps1`
- PoC(검증 완료): `scripts/gads-pause-poc.py`(링크 발견), `scripts/gads-remove-asset-poc.py`(제거·복원, 타입별)
