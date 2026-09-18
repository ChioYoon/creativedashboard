# BigQuery Exporter (B안 decoupled) — 설계

> 일자: 2026-09-18 | 목적: CLOOP 파이프라인 산출 JSON을 BigQuery에 병행 적재해 장기 이력·BI 확보.
> 현재 라이브 JSON은 28일 롤링·덮어쓰기(git 히스토리가 유일 아카이브). BQ로 전체 이력 영구 축적.

## 1. 배경·목표

- 현 적재: `public/data/{title}.json`(+`{title}_axis.json`) → git → GitHub Pages. DB 없음.
- 한계: kpi_daily는 최근 28일 창만, 매 nightly 전체 덮어쓰기 → 창 밖 일별 성과 라이브 JSON서 소멸(git 스냅샷만 남음).
- 목표: 파이프라인 **무변경**으로 JSON을 BQ에 병행 적재. 시계열 영구 누적 + 소재 태그·축 판정 일 스냅샷.
- 비목표(YAGNI): 스트리밍 insert, 실시간, BQ 뷰/스케줄드쿼리, Looker, git 히스토리 대량 백필.

## 2. 접근 — B안 decoupled exporter

별도 모듈 `pipeline/bq_export.py`가 `public/data/*.json`을 읽어 BQ 적재. 파이프라인·대시보드 경로 무손상. nightly git push **뒤** 실행 → BQ 장애가 대시보드·git에 무영향(격리).

## 3. 테이블 (데이터셋 `cloop`, env 지정)

| 테이블 | 소스 | 파티션 | 클러스터 | 행 키 |
|---|---|---|---|---|
| `kpi_daily` | creatives[].kpi_daily[] | `date` | title_id, creative_name, campaign_name | (creative_name, campaign_name, ad_group_name, date) |
| `mmp_daily` | creatives[].mmp_daily[] | `date`(코호트 설치일) | title_id, channel, creative_name | (creative_name, channel, date) |
| `creatives` | creatives[] 태그 메타 | `snapshot_date` | title_id, creative_name | (title_id, creative_name, snapshot_date) |
| `axis` | {title}_axis.json | `snapshot_date` | title_id, axis | (title_id, axis, snapshot_date) |

- 공통 컬럼: `title_id`, `loaded_at`(TIMESTAMP 적재시각). 스냅샷 2종은 `snapshot_date`(DATE = dataset.generated_at 날짜).
- `creatives` 컬럼: creative_id·소재명·유형·theme_primary·theme_secondary·core_usp(USP)·intent_axis·theme_flags·hooking_strategy·player_motivation 등 태그 메타(성과 kpi_daily/mmp_daily는 제외 — 별 테이블).
- BQ 스키마는 Pydantic 모델(`CreativeKpiDaily`·`CreativeMmpDaily`)에서 파생. 중첩·리스트 필드는 평탄화(kpi_daily/mmp_daily는 소재 밖 독립 행으로 전개).

## 4. 적재 — 파티션 교체 (idempotent)

매 실행, 테이블별로:
```
1. JSON서 행 추출 → BQ 타입 매핑(cost_micros→cost 등 파생은 파이프라인이 이미 계산, 그대로)
2. 삭제 범위 산정:
   - 시계열(kpi/mmp): 이번 로드 행의 date min..max 파티션
   - 스냅샷(creatives/axis): 오늘 snapshot_date 파티션
3. DELETE WHERE partition IN [범위]   (창/오늘 파티션만)
4. load_table_from_json(rows, WRITE_APPEND)  재삽입
   → 창 밖 과거 파티션 무손상·영구 누적
```
- 늦은 전환 백필: date 파티션 통째 대체라 자동 반영(같은 날짜 = 최신 확정값 1벌, 중복 0).
- 테이블당 독립 처리 — DELETE는 load job 성공 확인 후에만(부분 로드 방지). 실패 시 그 테이블만 영향.

## 5. 설정·인증 (`.env`, gitignore)

```
BQ_PROJECT=<gcp-project>
BQ_DATASET=cloop
GOOGLE_APPLICATION_CREDENTIALS=.secrets/bq_sa.json   # 서비스계정 키(BQ Data Editor)
BQ_EXPORT_ENABLED=1                                   # 미설정/0 → 스킵
```
- 서비스계정 키는 `.secrets/`(google_ads.yaml 패턴) 로컬 보관, gitignore. 저장소 유입 금지.
- 의존 추가: `google-cloud-bigquery`(requirements.txt). 기존 google-auth 재사용.
- 데이터셋·테이블 없으면 **자동 생성**(첫 실행 부트스트랩, DDL 멱등).

## 6. nightly 통합 ([scripts/nightly.ps1](scripts/nightly.ps1))

- 순서: `pipeline.main --all-titles` → git commit/push(기존) → **`python -m pipeline.bq_export --all-titles`(신규 마지막)**.
- `-DryRun`이면 스킵. push 뒤 배치라 BQ 실패해도 대시보드·git 무영향.
- CLI: `--all-titles`(public/data 스캔) / `--title <id>` / `--dry-run`(행수·삭제범위·SQL만 출력, 무적재).

## 7. 에러 처리 (격리·graceful)

- `BQ_EXPORT_ENABLED`≠1 또는 키 파일 없음 → 조용히 스킵(로그만). nightly 성공 유지.
- 테이블별 독립 try/except — 한 테이블 실패가 나머지 안 막음.
- 실패는 notify.py 경보(기존 패턴 재사용).
- JSON 파싱 실패·빈 파일 → 해당 타이틀 스킵, 로그.

## 8. 테스트 (오프라인 — 라이브 BQ 실행은 사용자 몫)

순수 로직만 pytest, BQ 클라이언트는 주입·fake로 검증(네트워크 0):
- JSON→BQ 행 변환: 중첩 kpi_daily/mmp_daily 평탄화, title_id·loaded_at·snapshot_date 주입, 타입.
- 파티션 삭제 범위 계산: 시계열 date min..max, 스냅샷 오늘.
- 스키마 생성: Pydantic → BQ SchemaField 매핑.
- 게이팅: env 없음/0 → 스킵 반환.
- fake client: 호출된 DELETE 범위·load 행수 검증(실제 BQ 미호출).

## 9. 보안 제약 (불변)

- 어시스턴트는 라이브 BQ 적재·서비스계정 키 조작 안 함(사용자 GCP 환경·자격증명). 코드·DDL·dry-run까지만.
- 원천 폴더(.env·.secrets) 저장소 공유 금지.

## 10. 유닛 경계

- `bq_export.py`: CLI·오케스트레이션(파일 스캔·테이블 루프·게이팅).
- 행 변환 함수(순수): `dataset_json → rows[]` 테이블별. 테스트 대상 핵심.
- 스키마 정의(순수): Pydantic→BQ SchemaField.
- 적재 함수: (client, table, rows, partition_range) → DELETE+load. client 주입.
- 설정 로더: env→config, 게이팅 판정.
