"""content_theme 축 판정 — 소구축별 4상태(검증/후보/소진/미검증) 산출.

R팀 협의안 §6-1 / 정의서 v2.0 기준. CLOOP↔브랜드브리프 연동의 축 레이어.

판정 3단계(협의안 §1-2):
  ① 자격  n≥MIN_N & 비용≥MIN_COST      → 미달 시 '미검증'
  ② 효율  IPM(전환/노출×1000) ≥ baseline.ipm
  ③ 품질  ROAS7 ≥ baseline.roas7        (MMP 등록기준 타이틀은 ROAS7 부재 → '품질 미확인')
상태(효율·품질 조합, 협의안): 동시상회=검증 / 하나상회=후보 / 동시하회=소진.
  ※ ROAS7 미확인이면 품질=미충족 취급 → 효율 상회 시 '후보' cap (검증 불가). 정직 처리.

단계(L/P) = 성과 발생 일자 기준(회신 v1.4 §1): 성과일 < 런칭일 → P, ≥ → L. **일별 성과를 기간 분할**(§3).
판정 대상 = 캠페인 목적세그(6번째) NU*  · RT·SA·숫자ID 제외(v1.4 §2).
N/A·미검수 소재는 집계 제외하되 '판정 대상 외 비중' 산출(정의서 §4-3).
"""
from __future__ import annotations
import datetime
from .content_theme import assign_theme, load_map

# 타이틀별 기본 파라미터 (권장 기본값).
# baseline.ipm=None → 코호트 median 상대판정(권장). 협의안 AppsFlyer baseline(ipm 1.6635·roas7 3.86)은
# CLOOP Google Ads IPM과 지표 공간이 달라 fixed 로 쓰면 오판(거의 전부 소진). 참고용으로만 보존.
DEFAULT_PARAMS = {
    "zeus": {"launch_date": "2026-08-26", "baseline": {"ipm": None, "roas7": None},
             "min_n": 3, "min_cost": 100000,
             "_ref_appsflyer_baseline": {"ipm": 1.6635, "roas7": 3.86}},
}
_FALLBACK = {"baseline": {"ipm": None, "roas7": None}, "min_n": 3, "min_cost": 100000}


def _purpose(cn: str) -> str:
    p = (cn or "").split("_")
    return p[5] if len(p) > 5 else ""


def _judgable_purpose(pr: str) -> bool:
    if not pr or pr in ("RT", "SA"):
        return False
    if pr.isdigit():  # Apple Search Ads 숫자 ID
        return False
    return pr.startswith("NU")


def _round(v, n=4):
    return None if v is None else round(v, n)


def compute_axis_verdict(creatives, *, title, launch_date, win_from, win_to,
                         baseline, min_n=3, min_cost=100000,
                         require_reviewed=False, theme_map=None):
    """소구축(theme_primary)별 P/L 단계 4상태 판정 → dict(협의안 §6-1 형태)."""
    m = theme_map if theme_map is not None else load_map()
    L = datetime.date.fromisoformat(launch_date)
    wf = datetime.date.fromisoformat(win_from); wt = datetime.date.fromisoformat(win_to)
    # {stage: {axis: {impr,conv,cost,val, keys:set}}}
    agg = {"P": {}, "L": {}}
    total = 0; excluded = 0
    for c in creatives:
        concept = c.get("creative_concept") or c.get("소재명") or ""
        # 창 내 판정대상 일자 존재?
        rows = []
        for x in (c.get("kpi_daily") or []):
            try:
                dd = datetime.date.fromisoformat(str(x.get("date"))[:10])
            except Exception:
                continue
            if not (wf <= dd <= wt):
                continue
            if not _judgable_purpose(_purpose(x.get("campaign_name") or "")):
                continue
            rows.append((dd, x))
        if not rows:
            continue
        total += 1
        t = assign_theme(concept, m)
        axis = t["theme_primary"]
        if axis.startswith("N/A") or (require_reviewed and not t["theme_reviewed"]):
            excluded += 1
            continue
        for dd, x in rows:
            stage = "P" if dd < L else "L"
            a = agg[stage].setdefault(axis, {"impr": 0, "conv": 0.0, "cost": 0.0, "val": 0.0, "keys": set()})
            a["impr"] += x.get("impressions") or 0
            a["conv"] += x.get("conversions") or 0.0
            a["cost"] += x.get("cost") or 0.0
            a["val"] += x.get("conversions_value") or 0.0
            a["keys"].add(concept)

    def _metrics(a):
        return ((a["conv"] / a["impr"] * 1000) if a["impr"] > 0 else None,
                (a["val"] / a["cost"]) if a["cost"] > 0 else None)

    def _median(xs):
        xs = sorted(v for v in xs if v is not None)
        if not xs:
            return None
        k = len(xs)
        return xs[k // 2] if k % 2 else (xs[k // 2 - 1] + xs[k // 2]) / 2

    # baseline.ipm 이 None 이면 코호트 median(상대판정) — 협의안 AppsFlyer baseline은 CLOOP Google Ads IPM과
    # 지표 공간이 달라 직접 사용 불가. 자체 코호트 median 이 CLOOP 랭크기반 철학과 정합.
    def stage_baseline(a_map):
        if baseline.get("ipm") is not None:
            return baseline["ipm"], "fixed"
        qual = [_metrics(a)[0] for a in a_map.values() if len(a["keys"]) >= min_n and a["cost"] >= min_cost]
        return _median(qual), "cohort_median"

    def verdict(a, base_ipm):
        n = len(a["keys"]); cost = a["cost"]
        ipm, ga_roas = _metrics(a)
        roas7 = None  # MMP D7 revenue ROAS — 등록기준 타이틀 부재(별도 소스 연동 시 주입)
        if n < min_n or cost < min_cost:
            return {"n": n, "status": "미검증", "reason": "자격 미달(n<%d 또는 비용<%s)" % (min_n, f"{min_cost:,}"),
                    "ipm": _round(ipm), "roas7": roas7, "ga_roas": _round(ga_roas), "cost": round(cost)}
        eff = base_ipm is not None and ipm is not None and ipm >= base_ipm
        qual_high = roas7 is not None and roas7 >= baseline.get("roas7", 0)
        score = int(eff) + int(qual_high)
        status = "검증" if score == 2 else ("후보" if score == 1 else "소진")
        reason = ("효율%s·품질%s" % ("상회" if eff else "하회",
                  "상회" if qual_high else ("미확인" if roas7 is None else "하회")))
        if roas7 is None:
            reason += " (ROAS7 미확인 — 등록기준, 검증 불가·후보 cap)"
        return {"n": n, "status": status, "reason": reason,
                "ipm": _round(ipm), "roas7": roas7, "ga_roas": _round(ga_roas), "cost": round(cost)}

    out_stages = {}; base_used = {}
    for stage in ("P", "L"):
        base_ipm, base_mode = stage_baseline(agg[stage])
        base_used[stage] = {"ipm": _round(base_ipm), "mode": base_mode}
        axes = [dict(axis=ax, **verdict(a, base_ipm)) for ax, a in agg[stage].items()]
        axes.sort(key=lambda r: (r["status"] != "검증", r["status"] != "후보", -(r["ipm"] or 0)))
        out_stages[stage] = axes
    return {
        "schema_version": "axis-1.0",
        "title": title,
        "launch_date": launch_date,
        "period": {"from": win_from, "to": win_to},
        "baseline": baseline,
        "baseline_used": base_used,
        "gates": {"min_n": min_n, "min_cost": min_cost},
        "excluded_ratio": round(excluded / total, 3) if total else 0.0,
        "excluded_note": "N/A·미검수 소재 제외 비중(판정 대상 외)",
        "stages": out_stages,
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "note": "ROAS7=MMP D7 매출 ROAS(등록기준 타이틀 부재→null). ga_roas=Google Ads conversions_value/cost(참고).",
    }


def build_for_title(creatives, title, *, win_from, win_to, params=None):
    """타이틀 기본 파라미터로 축 판정(파라미터 미지정 시 DEFAULT_PARAMS/폴백)."""
    p = params or DEFAULT_PARAMS.get(title, _FALLBACK)
    return compute_axis_verdict(
        creatives, title=title, launch_date=p.get("launch_date", "2026-08-26"),
        win_from=win_from, win_to=win_to, baseline=p["baseline"],
        min_n=p.get("min_n", 3), min_cost=p.get("min_cost", 100000))
