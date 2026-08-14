# pause_tool — 저효율 소재 제외 도구 (localhost)

피로도 분석에서 **제외 추천**된 저효율 소재를, 담당자 승인 후 **Google Ads에서 실제 중단(영상 제거)** 하는 로컬 웹앱. 스펙: `docs/superpowers/specs/2026-08-11-google-ads-pause-design.md` (Phase 2). 코어: `pipeline/pause.py`.

## 실행

```bash
.\.venv\Scripts\python.exe -m pause_tool.server
```

→ 브라우저에서 http://127.0.0.1:8765 (localhost 전용, 서버측 자격증명 `.secrets/google_ads.yaml` 재사용)

## 사용 흐름

1. **대시보드**(step1_integrated.html) → 타이틀 로드 → **피로도·제외 추천** 탭 → 분석 실행 → **CSV 내보내기**(`제외추천_YYYY-MM-DD.csv`).
2. pause_tool에서 **타이틀 선택** + CSV 내용 **붙여넣기** → **후보 불러오기**.
3. 후보 목록에서 끌 소재 **체크** → **① dry-run**으로 붙은 광고·before→after 확인.
4. 이상 없으면 **② 실제 제거**(확인 팝업 → 승인). 서빙·비용에 영향.
5. 되돌리려면 같은 선택으로 **복원**(영상 재추가).

## 매핑 (중요)

대시보드 `소재명`(=정규화 creative_id)은 Google Ads asset에 직접 안 붙음. `public/data/{title}.json`의 소재별 `kpi_daily[]`에서 실제 asset을 펼침:
- `asset_id`(파이프라인 Phase 1b, nightly 반영) 우선 — 이름 모호성 없음.
- 없으면 `creative_name`으로 라이브 resolve(폴백).
- **1 소재 = N asset**(L/S/V 영상 + 병합 BNR) → 전부 대상. **제거는 영상(VIDEO)만**, IMAGE(배너)는 영상 리스트에 없어 이 도구로 못 끔(후보에 별도 표시).

## 안전장치

- **dry-run 기본**, 실제 제거는 명시 승인(팝업) 후.
- 되돌리기(복원=재추가) 제공.
- 최소 개수 가드(영상 0개 되면 API 거부 → 그 광고 skip).
- localhost 전용. 라이브 광고 자동/무승인 변경 금지.

## 구성

| 파일 | 역할 |
|------|------|
| `server.py` | stdlib http.server — 후보/실행 API, `pipeline.pause` in-process 호출 |
| `mapping.py` | 순수 로직 — CSV 파싱 · 소재→asset 펼침 (테스트: `tests/test_pause_tool_mapping.py`) |
| `index.html` | UI — 후보 렌더 · 체크 · dry-run/제거/복원 |
