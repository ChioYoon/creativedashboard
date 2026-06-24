# Drive 폴더 링크 폴백 설계 스펙

작성 2026-06-24 · 브레인스토밍 합의 기반.

---

## 0. 한 줄 요약

Google Ads 미연동 등으로 미리보기가 없는 소재에 대해, 타이틀별 **Google Drive 공유 폴더 링크**를 폴백으로 노출한다. **파이프라인·재태깅 변경 없는 순수 프론트엔드 변경.**

---

## 1. 배경 · 문제

- 대시보드 미리보기(`링크` 필드)는 **오직 Google Ads API의 `asset_url`**(image_asset.full_size.url / youtube URL)에서만 채워짐 — `pipeline/main.py:820` `preview_url = d.asset_url`.
- 도원암귀(`tougenanki`)는 `_pipeline_kpi_enabled: false` → Google Ads 미연동 → 모든 소재가 미리보기 없음(`📷`/`—` placeholder).
- 스캐너는 소재의 **로컬 마운트 경로**(`G:\공유 드라이브\...`)만 알며, 이는 클릭 가능한 웹 링크가 아님. Drive 웹 링크는 파일 ID 기반이고 파이프라인에 Drive API 연동이 없음.
- 목표: 미리보기 없는 소재에 **최소 노력으로** "소재를 찾아볼 수 있는 경로" 제공.

---

## 2. 설계 원칙 · 선택한 트레이드오프

브레인스토밍에서 3개 방식(① Drive API 자동 연동 ② 타이틀별 폴더 링크 수동 ③ 로컬 경로 표시) 중 **②를 선택**.

- **장점**: 인증·개발 최소, 파이프라인/재태깅 불변, 즉시 적용.
- **수용한 한계**: 소재별 정확한 파일 딥링크가 아니라 **폴더 링크 1개** — 폴더가 열리면 사용자가 소재명으로 직접 탐색. (정확한 파일 딥링크·인라인 썸네일은 Drive API가 필요하므로 이번 회차 범위 밖.)

---

## 3. 아키텍처

```
js/titles.json
  └── (타이틀별) "drive_folder_url": "https://drive.google.com/drive/folders/{공유폴더ID}"
        ↑ 프론트엔드가 직접 소비 → "_pipeline_" 접두사 없음

step1_integrated.html
  ├── loadTitleManifest() 가 titles.json 전체를 읽음 (기존 동작)
  ├── 타이틀 로드 시 현재 타이틀의 drive_folder_url 을 전역에 보관
  └── 미리보기 렌더 3곳에서:
        미리보기 URL 없음 AND 현재 타이틀 drive_folder_url 있음
          → 기존 placeholder 대신 "📁 Drive 폴더 열기" 버튼 (새 탭)
```

데이터 흐름: **파이프라인 미경유.** titles.json(정적) → 대시보드 런타임 로드 → 렌더 분기.

---

## 4. 컴포넌트 상세

### 4-A. titles.json 신규 필드

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `drive_folder_url` | string | (없음) | 타이틀 공유 폴더의 Drive 웹 URL. 없으면 폴백 버튼 미표시 (기존 placeholder 유지) |

**적용 예시:**
```json
{
  "id": "tougenanki",
  "name": "도원암귀: Crimson Inferno",
  "json_url": "public/data/tougenanki.json",
  ...
  "drive_folder_url": "https://drive.google.com/drive/folders/{공유폴더ID}"
}
```

**초기값 확보:** 도원암귀 공유 폴더(`G:\공유 드라이브\[도원암귀_MKT] 외부 드라이브\1. 소재\...\0. UA Asset`)의 웹 URL은 **연결된 Google Drive 도구(`get_file_metadata`의 `webViewLink`)로 조회**해 채운다 (사용자 수동 복사 불필요). 향후 신규 타이틀은 동일 방식 또는 한 줄 수동 추가.

> 펩(`pepp-us`)은 Google Ads 미리보기가 이미 있으므로 `drive_folder_url`은 선택 사항. 이번 회차에는 **도원암귀에만 추가**(펩은 미설정 시 기존 동작 그대로).

### 4-B. 현재 타이틀 메타 보관 (프론트엔드)

`loadTitleManifest()`가 반환하는 매니페스트 항목에 `drive_folder_url`이 포함됨. 타이틀 로드 시점(`loadTitleFromJson`)에 현재 타이틀의 값을 전역 변수(예: `window.currentDriveFolderUrl`)에 저장한다.

- 자동 로드 경로(`initializeTitleSelector` → `loadTitleFromJson(matched)`)는 full 매니페스트 항목을 넘기므로 그대로 사용 가능.
- 셀렉터 변경 경로(`onTitleSelectorChange` → `loadTitleFromJson({id, json_url})`)는 현재 `drive_folder_url`을 누락하므로, **매니페스트를 전역 보관**하거나 id→url 맵을 만들어 조회한다.
- "직접 업로드" 모드 등 타이틀 미선택 시 `window.currentDriveFolderUrl = ''`.

### 4-C. 미리보기 폴백 분기 (3개 렌더 지점)

세 곳 모두 동일 패턴(`imageUrl` 추출 → `isVideo`/`hasImage` 분기 → placeholder):

| # | 위치(대략) | 함수/맥락 | placeholder 클릭 동작(현행) |
|---|-----------|----------|------------------------------|
| 1 | `step1_integrated.html:~4894` | 메인 소재 랭킹 테이블 | `openPreviewModal(index)` |
| 2 | `step1_integrated.html:~5257` | 소재별 점수 상세표(export 포함) | 원본 이미지 새 탭 / VID 박스 |
| 3 | `step1_integrated.html:~6248` | 피로도 분석 테이블 | `showFatigueModal(...)` |

**폴백 규칙 (세 곳 공통):**
```
미리보기 URL 없음(!hasImage, 영상 포함하여 실제 asset URL 부재)
  AND window.currentDriveFolderUrl 비어있지 않음
    → "📁 Drive 폴더 열기" 버튼 렌더
        onclick: window.open(currentDriveFolderUrl, '_blank', 'noopener')
  그 외 → 기존 동작 유지 (이미지 썸네일 / 영상 play div / 📷·— placeholder)
```

- **영상 처리 주의**: 현행 코드는 `isVideo`를 먼저 검사해 URL 없어도 play div를 렌더함. 폴백 규칙에서는 "실제 URL 부재"를 우선 판정 — URL 없는 영상도 Drive 폴더 버튼으로 대체(현재 빈 모달을 여는 것보다 유용).
- 버튼 라벨/툴팁: `📁 Drive 폴더 열기` / `title="공유 드라이브 폴더에서 이 소재를 찾아보세요"`.
- 미리보기가 **있는** 소재는 전혀 영향 없음.

### 4-D. 보안·범위 주의

- `drive_folder_url`은 공유 폴더의 **접근 권한 내** 사용자에게만 유효 — 권한 없는 외부 사용자가 열면 Drive가 자체적으로 접근 거부(앱 측 처리 불필요).
- `window.open(..., 'noopener')`로 새 탭 격리.
- URL은 titles.json(정적, 비밀 아님)에만 존재. `.env`·시크릿 무관.

---

## 5. 범위 밖 (이번 회차 제외)

- 소재별 정확한 파일 딥링크 (Drive API 필요)
- Drive 인라인 썸네일 (`drive.google.com/thumbnail?id=` — 파일 ID 필요)
- 파이프라인·스코어·태깅·캐시 변경
- 펩(`pepp-us`) 등 Google Ads 미리보기 보유 타이틀에 대한 강제 적용

---

## 6. 테스트 전략

| 단계 | 검증 내용 | 방법 |
|------|-----------|------|
| T1 | `drive_folder_url` 있는 타이틀 + 미리보기 없는 소재 → 폴더 버튼 노출 | 도원암귀 로드 후 미리보기 칸 육안 확인 |
| T2 | 버튼 클릭 → 새 탭으로 폴더 URL 열림 | preview 도구로 클릭 시뮬레이션 / 육안 |
| T3 | `drive_folder_url` 없는 타이틀(펩) → 폴백 미표시, 기존 동작 유지 | 펩 로드 후 회귀 확인 |
| T4 | 미리보기 **있는** 소재 → 폴더 버튼 미표시(기존 썸네일 유지) | 펩 이미지 소재 확인 |
| T5 | 3개 렌더 지점 모두 동일 폴백 적용 | 메인표·점수상세·피로도표 각각 확인 |

---

## 7. 구현 범위 (이번 회차)

- [ ] `js/titles.json`: 도원암귀에 `drive_folder_url` 추가 (값은 Drive 도구로 조회)
- [ ] `step1_integrated.html`: 현재 타이틀 `drive_folder_url` 전역 보관 (4-B)
- [ ] `step1_integrated.html`: 3개 렌더 지점에 폴백 버튼 분기 (4-C)
- [ ] T1~T5 검증 (preview 도구)
