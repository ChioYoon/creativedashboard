r"""산출 JSON의 KPI/URL/concept 채워짐 확인 — PowerShell 인용 escape 회피용.

사용법:
    .\.venv\Scripts\python.exe scripts\check-pipeline-output.py
    .\.venv\Scripts\python.exe scripts\check-pipeline-output.py --title pepp-us
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# schema 옆에 있는 signal 분포 헬퍼 재사용 (analyze-signals.py 와 동일 SoT)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.schemas import signal_distribution  # noqa: E402
from pipeline.validators import check_signal_diversity  # noqa: E402


def main():
    # PowerShell cp949 console에서 em-dash(—) 등 unicode 출력 깨짐 방지
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    p = argparse.ArgumentParser()
    p.add_argument("--title", default="pepp-us")
    p.add_argument("--path", default=None, help="JSON 직접 경로 지정 (선택)")
    args = p.parse_args()

    json_path = Path(args.path) if args.path else Path(f"public/data/{args.title}.json")
    if not json_path.exists():
        sys.exit(f"[X] {json_path} 가 없습니다. main.py 를 먼저 실행하세요.")

    d = json.loads(json_path.read_text(encoding="utf-8"))
    creatives = d.get("creatives", [])
    print(f"파일: {json_path}")
    print(f"schema_version: {d.get('schema_version')}")
    print(f"generated_at:   {d.get('generated_at')}")
    print(f"소재 record 수: {len(creatives)}")

    with_kpi = [r for r in creatives if r.get("노출수", 0) > 0]
    with_url = [r for r in creatives if r.get("링크")]
    with_concept = [r for r in creatives if r.get("creative_concept")]
    with_daily = [r for r in creatives if r.get("kpi_daily")]

    print(f"\n채워짐 현황:")
    print(f"  KPI (노출수>0):      {len(with_kpi):>4} / {len(creatives)}")
    print(f"  링크 (asset_url):    {len(with_url):>4} / {len(creatives)}")
    print(f"  creative_concept:    {len(with_concept):>4} / {len(creatives)}")
    print(f"  kpi_daily 행 보유:   {len(with_daily):>4} / {len(creatives)}")

    if with_url:
        r = with_url[0]
        print(f"\n샘플 record (KPI+URL 채워진 첫 항목):")
        print(f"  파일명:   {r.get('파일명')}")
        print(f"  소재명:   {r.get('소재명')}")
        print(f"  concept:  {r.get('creative_concept')}")
        print(f"  유형:     {r.get('유형')} / 사이즈: {r.get('사이즈')} / 언어: {r.get('언어')}")
        print(f"  링크:     {r.get('링크')}")
        print(
            f"  노출수: {r.get('노출수', 0):,} / "
            f"비용: {r.get('비용', 0):,} / "
            f"클릭수: {r.get('클릭수', 0):,} / "
            f"전환: {r.get('전환', 0)}"
        )
        daily = r.get("kpi_daily", []) or []
        print(f"  kpi_daily 행: {len(daily)}개")
        if daily:
            campaigns = sorted({d.get("campaign_name", "") for d in daily})
            print(f"  등장 캠페인 수: {len(campaigns)}")
            print(f"  첫 row: date={daily[0].get('date')} | "
                  f"campaign={(daily[0].get('campaign_name') or '')[:50]} | "
                  f"imp={daily[0].get('impressions', 0):,} | "
                  f"url? {'Y' if daily[0].get('asset_url') else 'N'}")

        # Stage 5-E v2: 구조화 신호 표시
        strengths = r.get("strengths", []) or []
        weaknesses = r.get("weaknesses", []) or []
        hypothesis = r.get("hypothesis", []) or []
        test_ideas = r.get("test_ideas", []) or []
        one_line = r.get("one_line_insight", "")
        if strengths or weaknesses or hypothesis or test_ideas or one_line:
            print(f"\n  [Stage 5-E v2 구조화 신호]")
            print(f"    강점: {strengths}")
            print(f"    약점: {weaknesses}")
            print(f"    가설: {hypothesis}")
            print(f"    변주: {test_ideas}")
            print(f"    1줄: {one_line!r}")

    # Stage 5-E v2: 전체 분포 자동 집계 (schema 헬퍼 사용 — analyze-signals.py 와 동일 SoT)
    distribution = signal_distribution(creatives)
    if any(distribution.values()):
        print(f"\n[전체 {len(creatives)}개 record 분포 — v2 신호 집계]")
        # (필드명, 헤더라벨, 라벨 컬럼폭) — 한 곳에서 출력 형식 통제
        sections = [
            ("strengths",  "강점 Top",        25),
            ("weaknesses", "약점 Top",        25),
            ("hypothesis", "가설 Top",        35),
            ("test_ideas", "변주 추천 Top",   25),
        ]
        for field, header, width in sections:
            counter = distribution[field]
            if not counter:
                continue
            print(f"  {header}:")
            for label, n in counter.most_common(5):
                pct = f" ({n*100//len(creatives)}%)" if field in ("strengths", "weaknesses") else ""
                print(f"    {label:<{width}} {n:>3}건{pct}")

    # Stage 5-G.4: 분포 sanity check (top-1 enum 80% 이상 부여 시 경고)
    diversity_warnings = check_signal_diversity(creatives, top_share_threshold=0.8)
    if diversity_warnings:
        print(f"\n[!] 분포 sanity check 경고 ({len(diversity_warnings)}건):")
        for w in diversity_warnings:
            print(f"    - {w}")
    elif any(distribution.values()):
        print(f"\n[OK] 분포 sanity check 통과 — top-1 enum 부여율 80% 미만 (variance 확보)")

    if not with_kpi:
        print("\n[!] 경고: KPI 채워진 record 0개.")
        print("    원인 후보:")
        print("    1) titles.json 의 _pipeline_kpi_enabled=true, _pipeline_google_ads_customer_id 확인")
        print("    2) main.py 실행 로그에서 'KPI fetch' 줄 확인 (skipped/failed 여부)")
        print("    3) cache/{title}_kpi.json 존재 시 한 번 삭제 후 재실행 권장")


if __name__ == "__main__":
    main()
