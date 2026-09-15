"""content_theme 축 판정 — 소구축별 4상태(검증/후보/소진/미검증). R팀 협의안~회신 v1.5.

판정 3단계(협의안 §1-2):
  ① 자격  n≥MIN_N & 비용≥MIN_COST → 미달 시 '미검증'
  ② 효율  IPM(전환/노출×1000) ≥ baseline_ipm
  ③ 품질  단계별 지표(회신 v1.5 §2):
      · P(사전예약): 사전예약 전환율(전환/클릭) ≥ baseline_cvr   ← 매출 없어도 정상 판정
      · L(런칭)    : D7 ROAS ≥ baseline_roas (ROAS 부재 시에만 '후보 cap')
상태: 효율·품질 동시상회=검증 / 하나상회=후보 / 동시하회=소진.

baseline = **코호트 가중평균**(회신 v1.5 §1): Σ전환/Σ노출, Σ전환/Σ클릭, Σ매출/Σ비용.
  "예산 주류보다 잘하는가" — 비용 큰 축이 기준선을 끌어당겨 소액 축이 흔들지 않음. (median 폐기)
단계 L/P = 성과 발생일 vs 런칭일(회신 v1.4 §1), 일별 성과 기간분할(§3). 판정대상=목적세그 NU*(RT/SA/숫자 제외).
delta = 직전 기간(창 -30일) 대비 IPM 변화율(v1.5 §1-4). N/A·미검수 제외 + 판정대상외 비중 산출.
"""
from __future__ import annotations
import datetime
from .content_theme import assign_theme, load_map

# 타이틀별 파라미터. baseline_mode='cohort_weighted'(v1.5 확정). 런칭일=타이틀별.
#   launch_date=None → 미런칭. 소재 단계는 전량 P(런칭 전)로 집계한다.
#   ⚠️ 폴백에 특정 타이틀의 런칭일을 두면 다른 타이틀이 그 날짜를 상속해 L/P 분류가 통째로 틀어진다.
#      (브리프 정본 stage.launch_date 연동 전까지 여기서 관리 — 도원암귀는 일본 2026-12/2027-02 검토 중 미확정)
DEFAULT_PARAMS = {
    "zeus": {"launch_date": "2026-08-26", "min_n": 3, "min_cost": 100000},
    "tougenanki": {"launch_date": None, "min_n": 3, "min_cost": 100000},
}
_FALLBACK = {"launch_date": None, "min_n": 3, "min_cost": 100000}


def _purpose(cn: str) -> str:
    p = (cn or "").split("_")
    return p[5] if len(p) > 5 else ""


def _judgable_purpose(pr: str) -> bool:
    if not pr or pr in ("RT", "SA") or pr.isdigit():
        return False
    return pr.startswith("NU")


def _r(v, n=4):
    return None if v is None else round(v, n)


def _agg_window(creatives, m, L, wf, wt, require_reviewed):
    """창 [wf,wt] 판정대상 일별 성과 → {stage:{axis:{impr,conv,clicks,cost,val,keys}}}, total, excluded."""
    agg = {"P": {}, "L": {}}
    total = 0
    excluded = 0
    for c in creatives:
        concept = c.get("creative_concept") or c.get("소재명") or ""
        rows = []
        for x in (c.get("kpi_daily") or []):
            try:
                dd = datetime.date.fromisoformat(str(x.get("date"))[:10])
            except Exception:
                continue
            if wf <= dd <= wt and _judgable_purpose(_purpose(x.get("campaign_name") or "")):
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
            stage = "L" if (L is not None and dd >= L) else "P"
            a = agg[stage].setdefault(axis, {"impr": 0, "conv": 0.0, "clicks": 0, "cost": 0.0, "val": 0.0, "keys": set()})
            a["impr"] += x.get("impressions") or 0
            a["conv"] += x.get("conversions") or 0.0
            a["clicks"] += x.get("clicks") or 0
            a["cost"] += x.get("cost") or 0.0
            a["val"] += x.get("conversions_value") or 0.0
            a["keys"].add(concept)
    return agg, total, excluded


def _cohort_baseline(stage_map):
    """코호트 가중평균 baseline: Σ전환/Σ노출×1000, Σ전환/Σ클릭, (Σ매출/Σ비용은 참고)."""
    si = sc = sk = sco = sv = 0.0
    for a in stage_map.values():
        si += a["impr"]; sc += a["conv"]; sk += a["clicks"]; sco += a["cost"]; sv += a["val"]
    return {
        "ipm": (sc / si * 1000) if si > 0 else None,
        "cvr": (sc / sk) if sk > 0 else None,
        "ga_roas": (sv / sco) if sco > 0 else None,
        "roas7": None,  # MMP D7 매출 ROAS — 등록기준 부재(별도 소스 연동 시 주입)
    }


def compute_axis_verdict(creatives, *, title, launch_date, win_from, win_to,
                         min_n=3, min_cost=100000, prior_from=None, prior_to=None,
                         require_reviewed=False, theme_map=None):
    m = theme_map if theme_map is not None else load_map()
    L = datetime.date.fromisoformat(launch_date) if launch_date else None   # None=미런칭 → 전량 P
    wf = datetime.date.fromisoformat(win_from); wt = datetime.date.fromisoformat(win_to)
    agg, total, excluded = _agg_window(creatives, m, L, wf, wt, require_reviewed)

    # delta 용 직전 기간(기본: 창 바로 앞 동일 길이)
    if prior_from is None or prior_to is None:
        span = (wt - wf).days
        prior_to = (wf - datetime.timedelta(days=1)).isoformat()
        prior_from = (wf - datetime.timedelta(days=1 + span)).isoformat()
    pagg, _, _ = _agg_window(creatives, m, L,
                             datetime.date.fromisoformat(prior_from),
                             datetime.date.fromisoformat(prior_to), require_reviewed)

    def _ipm(a):
        return (a["conv"] / a["impr"] * 1000) if a["impr"] > 0 else None

    out_stages = {}; base_used = {}
    for stage in ("P", "L"):
        base = _cohort_baseline(agg[stage])
        base_used[stage] = {"ipm": _r(base["ipm"]), "cvr": _r(base["cvr"]),
                            "roas7": base["roas7"], "mode": "cohort_weighted"}
        axes = []
        for ax, a in agg[stage].items():
            n = len(a["keys"]); cost = a["cost"]
            ipm = _ipm(a)
            cvr = (a["conv"] / a["clicks"]) if a["clicks"] > 0 else None
            ga_roas = (a["val"] / a["cost"]) if a["cost"] > 0 else None
            roas7 = None  # 등록기준 부재
            # delta (직전기간 IPM 대비)
            pa = pagg[stage].get(ax)
            pipm = _ipm(pa) if pa else None
            ipm_pct = _r((ipm - pipm) / pipm * 100, 1) if (ipm is not None and pipm) else None
            if n < min_n or cost < min_cost:
                axes.append({"axis": ax, "n": n, "status": "미검증",
                             "reason": "자격 미달(n<%d 또는 비용<%s)" % (min_n, f"{min_cost:,}"),
                             "ipm": _r(ipm), "cvr": _r(cvr), "roas7": roas7, "ga_roas": _r(ga_roas),
                             "cost": round(cost), "delta": {"ipm_pct": ipm_pct, "vs_period": f"{prior_from}~{prior_to}"}})
                continue
            eff = base["ipm"] is not None and ipm is not None and ipm >= base["ipm"]
            if stage == "P":  # 품질 = 사전예약 전환율(전환/클릭)
                q_known = base["cvr"] is not None and cvr is not None
                q_high = q_known and cvr >= base["cvr"]
                q_label = "전환율"
            else:            # L: 품질 = D7 ROAS (부재 시 후보 cap)
                q_known = roas7 is not None
                q_high = q_known and base["roas7"] is not None and roas7 >= base["roas7"]
                q_label = "ROAS"
            if q_known:
                score = int(eff) + int(q_high)
                status = "검증" if score == 2 else ("후보" if score == 1 else "소진")
                reason = "효율%s·%s%s" % ("상회" if eff else "하회", q_label, "상회" if q_high else "하회")
            else:  # 품질 미확인(L ROAS 부재) → 효율만으로 후보 cap
                status = "후보" if eff else "소진"
                reason = "효율%s·%s미확인(후보 cap)" % ("상회" if eff else "하회", q_label)
            axes.append({"axis": ax, "n": n, "status": status, "reason": reason,
                         "ipm": _r(ipm), "cvr": _r(cvr), "roas7": roas7, "ga_roas": _r(ga_roas),
                         "cost": round(cost), "delta": {"ipm_pct": ipm_pct, "vs_period": f"{prior_from}~{prior_to}"}})
        axes.sort(key=lambda r: (r["status"] != "검증", r["status"] != "후보", -(r["ipm"] or 0)))
        out_stages[stage] = axes

    return {
        "schema_version": "axis-1.1",
        "title": title,
        "launch_date": launch_date,
        "period": {"from": win_from, "to": win_to},
        "prior_period": {"from": prior_from, "to": prior_to},
        "baseline_used": base_used,
        "baseline_mode": "cohort_weighted",
        "gates": {"min_n": min_n, "min_cost": min_cost},
        "excluded_ratio": round(excluded / total, 3) if total else 0.0,
        "excluded_note": "N/A·미검수 소재 제외 비중(판정 대상 외)",
        "stages": out_stages,
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "note": "baseline=코호트 가중평균. P품질=사전예약 전환율(전환/클릭), L품질=D7 ROAS(등록기준 부재→후보cap). ga_roas=Google conversions_value/cost(참고).",
    }


def build_for_title(creatives, title, *, win_from, win_to, params=None):
    p = params or DEFAULT_PARAMS.get(title, _FALLBACK)
    return compute_axis_verdict(
        creatives, title=title, launch_date=p.get("launch_date"),
        win_from=win_from, win_to=win_to,
        min_n=p.get("min_n", 3), min_cost=p.get("min_cost", 100000))
