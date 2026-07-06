# step2 DS 토큰 정렬 — --radius/--shadow 충돌 해소 설계

**작성일:** 2026-07-06

## Goal

step2_clustering·step2_column_selector 두 페이지의 로컬 `:root`이 DS 토큰(`colors_and_type.css`)과 **같은 이름의 `--radius-*`·`--shadow-*`를 다른 값으로 재정의**해 DS 토큰을 덮어쓰는(shadowing) 문제를 해소한다. 로컬 오버라이드를 삭제해 DS 값을 채택하고, 두 페이지의 모서리·그림자를 step1·공식 컴포넌트와 통일한다.

## 배경 / 문제

두 step2 페이지의 로컬 `:root`은 대부분 의도적 리맵 shim이다 — `--red`→`var(--brand-primary)`, `--gray-bg`→`var(--surface-soft)` 등 브랜드·그레이·텍스트 토큰은 이미 DS 토큰을 가리킨다. 그러나 다음 6개는 DS와 **다른 값으로 재정의**되어 있다:

| 토큰 | 로컬 값 | DS 값(colors_and_type.css) |
|---|---|---|
| `--radius-sm` | 8px | 4px |
| `--radius-md` | 12px | 8px |
| `--radius-lg` | 16px | 16px (동일) |
| `--shadow-sm` | 0 2px 8px rgba(0,0,0,.06) | 0 1px 2px…, 0 1px 3px… |
| `--shadow-md` | 0 8px 24px rgba(0,0,0,.10) | 0 2px 8px…, 0 4px 16px… |
| `--shadow-lg` | 0 20px 60px rgba(0,0,0,.15) | 0 8px 28px…, 0 2px 8px… |

**두 페이지의 캐스케이드가 다르다** (DS `<link>` 위치 차이 — preview computed 값으로 확인):

| 페이지 | DS `<link>` 위치 | 현재 `--radius-md` 실효값 | 상태 |
|---|---|---|---|
| step2_clustering | 625행 (로컬 `:root` 15행 **뒤**) | 8px (DS 승) | 로컬 defs가 **이미 DS에 덮여 죽은 코드** |
| step2_column_selector | 11행 (로컬 `:root` 19행 **앞**) | 12px (로컬 승) | 로컬이 이겨 **실제 shadowing** |

즉 step2_clustering은 DS 링크가 로컬 `:root`보다 뒤라 이미 DS 값이 적용 중이고 로컬 radius/shadow 선언은 죽은 코드다. step2_column_selector만 로컬이 이겨 실제 shadowing이 발생한다. 어느 쪽이든 로컬 선언 삭제가 올바른 종착점(양쪽 DS 값)이다.

## 접근

로컬 `:root`에서 `--radius-sm/md/lg` + `--shadow-sm/md/lg` **6개 선언만 삭제**한다. 두 페이지 모두 `colors_and_type.css`를 로드하므로, 삭제 후 페이지 내 `var(--radius-md)`·`var(--shadow-sm)` 등의 참조는 DS 값으로 해석된다.

- **유지**: 나머지 리맵(`--red`·`--gray-bg`·`--dark` 등, 이미 DS 토큰 가리킴), 클러스터 시맨틱 색(`--green`·`--orange`·`--blue`·`--purple`·`--gold` + pale/mid — DS 대응 없음), `--transition`.
- **삭제**: radius 3개 + shadow 3개(라인은 구현 계획에서 정확 지정).

접근법 후보 중 이 방식(DS 값 채택)을 채택 — 사용자가 예시(현재 vs DS 비교)를 확인 후 결정. 대안(로컬 토큰을 `--cl-*`로 개명해 시각 유지)은 shadowing만 없애고 DS와 여전히 불일치라 기각.

## 변경 대상 파일

- `step2_clustering.html` — 로컬 `:root`(~15-30행)의 `--shadow-sm/md/lg`(25-27행)·`--radius-sm/md/lg`(28행) 삭제.
- `step2_column_selector.html` — 로컬 `:root`의 `--shadow-sm/md/lg`(34-36행)·`--radius-sm/md/lg`(37-39행) 삭제.

(정확한 삭제 라인·잔여 블록 형태는 구현 계획에서 확정.)

## 효과 (페이지별로 다름)

- **step2_clustering**: 이미 DS 값이 적용 중 → **시각 무변화**. 삭제는 죽은(덮인) 선언 제거 = 코드 위생.
- **step2_column_selector**: 로컬이 이기던 상태 → 삭제로 DS 값 채택 = **실제 시각 변화**. 카드·패널 모서리 `--radius-md` 12px→8px, 컨트롤·칩 `--radius-sm` 8px→4px(더 각지게), 그림자는 한 겹 진한 것 → DS 두 겹 얕은 것(더 은은). `--radius-lg`는 16px 동일.
- 두 페이지 모두 클러스터 색·브랜드 색·레이아웃은 무변화.

## Error Handling / Edge Cases

- 두 페이지가 `colors_and_type.css`를 로드하지 않으면 `var(--radius-md)`가 미정의가 되지만, 5개 페이지 모두 로드함이 확인됨(캐시버스팅 `?v=` 포함). 삭제 안전.
- 페이지 내 `var(--radius-*)`/`var(--shadow-*)` 참조는 인라인 폴백이 없어 DS 정의에 의존 — DS가 6개 모두 정의하므로 문제 없음.

## Testing / Verification

정적 사이트 → preview(브라우저) 기반:
1. step2_clustering·step2_column_selector 각각 로드 → 대표 카드/컨트롤의 `border-radius` computed 값이 DS 값(카드 8px, 소형 4px)인지 `preview_inspect`로 확인.
2. 삭제된 로컬 토큰이 더 이상 grep에 없고, 다른 `:root` 항목(리맵·클러스터 색)은 보존됐는지 정적 확인.
3. 레이아웃 깨짐·콘솔 에러 없음 확인.

## Out of Scope

- **live_dashboard 컴포넌트 교체** — DS `.ds-pill`은 40px·14px 대형 액션 버튼이라 live_dashboard의 12px 소형 토글과 치수·용도가 안 맞고, `.live-metric-btn`은 이미 DS 토큰 pill이라 실이득 없음. 제외.
- 브랜드/그레이 리맵·클러스터 시맨틱 색 — 변경 없음.
- 토큰 개명(`--cl-*`) 방식 — 채택 안 함(DS 값 채택으로 대체).
