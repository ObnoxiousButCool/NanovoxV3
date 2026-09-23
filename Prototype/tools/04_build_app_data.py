"""Stage 4 -- the analytical layer the prototypes render, written to data.js.

Every figure carries its epistemic class, because the UI shows it:
  observed    counted directly from the written calls
  reference   a fact from the workbook's master sheets (the design population)
  derived     computed from observed values
  pattern     a relationship across several observed values
  inference   a possible explanation, never asserted as cause

Two deliberate refusals, both load-bearing:

  The Employer Master's churn profile is NOT an input to the risk band. It is the
  label the corpus was generated from, so scoring an account on it would be
  circular. It travels through as design_churn_profile and the UI shows it as a
  segment, outside the indicator count.

  Escalation integrity is handled divided by TRIGGERED, never escalations divided
  by all calls. Against all calls a rate of zero reads as good news; against
  warranted calls it reads as the control failure it is.

Action items are seeded from what the corpus raised -- process-gap proposals,
knowledge failures, escalation misses, control exceptions, exit language. The
workflow state (owner, assigned date, due date, action taken, outcome) is
prototype data: the corpus carries no action records.
"""
import collections
import datetime as dt
import json

from paths import APP_DATA_JS, DATASET_JSON, require

PERIOD_END = dt.date(2026, 9, 25)
SEV_RANK = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "": 0}
WEEKS = list(range(1, 13))
BUCKETS = [("Wk 1-4", [1, 2, 3, 4]), ("Wk 5-8", [5, 6, 7, 8]), ("Wk 9-12", [9, 10, 11, 12])]

# The ten indicator families. A band counts DISTINCT families, not incidents --
# the "two or more conditions" shape the v9 Metrics sheet uses for its account
# risk flag. None of these is evidence an employer will leave; the corpus has no
# termination outcomes to validate any of it against.
IND = [
    ("unresolved", "Unresolved outcome", lambda c: c["outcome"] == "UNRESOLVED"),
    ("escalation_missed", "Escalation requested, not handled",
     lambda c: c["esc_triggered"] and not c["esc_handled"]),
    ("complaint_choice", "Complaint attributed to Choice",
     lambda c: c["complaint"] and c["complaint_to"] == "CHOICE"),
    ("repeat_contact", "Repeat contact on the same issue", lambda c: bool(c["repeat_of"])),
    ("exit_language", "Exit or market-test language, verbatim",
     lambda c: any(i["code"] in ("market_test", "cancellation") for i in c["intent"])),
    ("critical_signal", "Critical-severity signal raised",
     lambda c: any(s["severity"] == "CRITICAL" for s in c["signals"])),
    ("control_exception", "Compliance control exception",
     lambda c: bool(c["control_exceptions"])),
    ("knowledge_failure", "Agent stated a published rule incorrectly", lambda c: c["kf_present"]),
    ("high_effort", "High member effort", lambda c: c["effort_band"] == "High"),
    ("broker_adverse", "Broker named adversely by the caller",
     lambda c: any(s["code"] == "broker_conduct_adverse" for s in c["signals"])),
]

# Prototype workflow states, cycled over the seeded items.
WF = [
    ("needs_action", None, None, None, None),
    ("assigned", "Rebekah Vance", "2026-09-14", None, None),
    ("in_progress", "Adam Thorne", "2026-09-10", None, None),
    ("assigned", "Marcus Bell", "2026-08-11", None, None),
    ("in_progress", "Priya Raman", "2026-08-18", None, None),
    ("action_taken", "Adam Thorne", "2026-09-02",
     "Claims communication reviewed with the account team on 15 Sep.", None),
    ("monitoring", "Priya Raman", "2026-08-24",
     "Invoice change-code glossary drafted and sent to Finance.",
     "Repeat contacts on invoice_statement: 2 in Wk 5-8, 1 in Wk 9-12."),
    ("completed", "Rebekah Vance", "2026-08-10",
     "Broker re-briefed on waiting-period disclosure at enrolment.",
     "No further adverse mentions for this agency in Wk 9-12."),
]


def structural(e):
    """Account facts that raise the stakes. Reference data, not observations."""
    out = []
    if e["sponsorship"] == "ER" and e["participation"] is not None and e["participation"] < 0.70:
        out.append({"code": "participation_below_threshold",
                    "label": "Participation below 70% on employer-sponsored dental",
                    "detail": "%d of %d enrolled (%.0f%%) - rule P-18 requires 70%%"
                              % (e["enrolled"], e["eligible"], e["participation"] * 100),
                    "cls": "reference"})
    months_out = (e["renewal_m"] - 9) % 12
    if 0 < months_out <= 3:
        out.append({"code": "renewal_near", "label": "Renewal within 90 days",
                    "detail": "renews %s" % e["renewal_month"], "cls": "reference"})
    if e["calls_per_100"] is not None and e["calls_per_100"] >= 12:
        out.append({"code": "high_contact_rate",
                    "label": "Planned contact rate above book median",
                    "detail": "%.1f calls per 100 lives per 12 weeks" % e["calls_per_100"],
                    "cls": "reference"})
    return out


def main():
    require(DATASET_JSON, "stage 4 -- run stage 3 first")
    D = json.loads(DATASET_JSON.read_text(encoding="utf-8"))
    calls, employers, brokers, agents = D["calls"], D["employers"], D["brokers"], D["agents"]
    rules, tps, snippets = D["rules"], D["touchpoints"], D["snippets"]

    by_emp = collections.defaultdict(list)
    for c in calls:
        by_emp[c["employer"]].append(c)

    # ---- employers ----
    emp_rows = []
    for eid, e in employers.items():
        cs = by_emp.get(eid, [])
        obs = []
        for code, label, fn in IND:
            hits = [c for c in cs if fn(c)]
            if hits:
                obs.append({"code": code, "label": label, "calls": [c["id"] for c in hits],
                            "n": len(hits), "cls": "observed"})
        families = len(obs)
        emp_rows.append({
            **e,
            "broker_name": brokers.get(e["broker"], {}).get("agency", ""),
            "calls_written": len(cs),
            "call_ids": [c["id"] for c in cs],
            "indicators": obs, "structural": structural(e),
            "indicator_families": families,
            "band": ("None" if families == 0 else "Watch" if families == 1
                     else "Elevated" if families == 2 else "High"),
            "unresolved": sum(1 for c in cs if c["outcome"] == "UNRESOLVED"),
            "repeat": sum(1 for c in cs if c["repeat_of"]),
            "signals": sum(len(c["signals"]) for c in cs),
            "worst_severity": max([SEV_RANK[s["severity"]] for c in cs for s in c["signals"]] or [0]),
            "avg_score": round(sum(c["score"] for c in cs) / len(cs)) if cs else None,
            "avg_effort": round(sum(c["effort"] for c in cs) / len(cs)) if cs else None,
            "aht_total": sum(c["aht"] for c in cs),
            # Metric 9, cost to serve: talk time annualised from the written
            # window, per covered life, against a fee set only by headcount.
            # Minutes, never money -- the workbook carries no cost per minute.
            "annual_minutes": round(sum(c["aht"] for c in cs) / 60 * (52 / D["meta"]["weeks"]), 1),
            "minutes_per_life": (
                round(sum(c["aht"] for c in cs) / 60 * (52 / D["meta"]["weeks"]) / e["enrolled"], 2)
                if e["enrolled"] and cs else None),
            # Not computable per account at batch-1 volume; the UI says so.
            "trend": "insufficient" if len(cs) < 4 else "computed",
        })
    emp_rows.sort(key=lambda r: (-r["indicator_families"], -r["worst_severity"], -r["signals"]))

    # ---- brokers ----
    brk_rows = []
    for bid, b in brokers.items():
        emps = [r for r in emp_rows if r["broker"] == bid]
        cs = [c for c in calls if c["broker"] == bid]
        adverse = [c for c in cs
                   if any(s["code"] == "broker_conduct_adverse" for s in c["signals"])]
        emps_adverse = {c["employer"] for c in adverse}
        brk_rows.append({
            **b,
            "employers_in_corpus": len(emps),
            "calls": len(cs), "call_ids": [c["id"] for c in cs],
            "adverse_calls": len(adverse), "adverse_employers": len(emps_adverse),
            "unresolved": sum(1 for c in cs if c["outcome"] == "UNRESOLVED"),
            "complaints": sum(1 for c in cs if c["complaint"]),
            "employers_elevated": sum(1 for r in emps if r["band"] in ("Elevated", "High")),
            "regions": sorted({c["region"] for c in cs if c["region"]}),
            # Questions Worth Asking trigger 2: >=3 adverse from >=2 employers.
            "trigger_broker_pattern": len(adverse) >= 3 and len(emps_adverse) >= 2,
        })
    brk_rows.sort(key=lambda r: (-r["adverse_calls"], -r["employers_elevated"], -r["calls"]))

    # ---- regions ----
    reg_rows = []
    for region in sorted({e["region"] for e in employers.values() if e["region"]}):
        emps = [r for r in emp_rows if r["region"] == region]
        cs = [c for c in calls if c["region"] == region]
        reg_rows.append({
            "region": region, "employers": len(emps),
            "enrolled": sum(r["enrolled"] for r in emps), "calls": len(cs),
            "brokers": len({r["broker"] for r in emps}),
            "unresolved": sum(1 for c in cs if c["outcome"] == "UNRESOLVED"),
            "elevated": sum(1 for r in emps if r["band"] in ("Elevated", "High")),
            "signals": sum(len(c["signals"]) for c in cs),
            "avg_score": round(sum(c["score"] for c in cs) / len(cs)) if cs else None,
        })

    # ---- weekly series ----
    def week_series(subset):
        byw = collections.Counter(c["w"] for c in subset)
        return [byw.get(w, 0) for w in WEEKS]

    series = {
        "calls": week_series(calls),
        "unresolved": week_series([c for c in calls if c["outcome"] == "UNRESOLVED"]),
        "escalated": week_series([c for c in calls if c["outcome"] == "ESCALATED"]),
        "repeat": week_series([c for c in calls if c["repeat_of"]]),
        "signals": week_series([c for c in calls if c["signals"]]),
        "complaints": week_series([c for c in calls if c["complaint"]]),
        "high_effort": week_series([c for c in calls if c["effort_band"] == "High"]),
    }
    series["resolution_pct"] = [
        round(100 * sum(1 for c in calls if c["w"] == w and c["outcome"] == "RESOLVED")
              / max(series["calls"][i], 1)) if series["calls"][i] else None
        for i, w in enumerate(WEEKS)]
    series["avg_aht"] = [
        round(sum(c["aht"] for c in calls if c["w"] == w) / max(series["calls"][i], 1))
        if series["calls"][i] else None for i, w in enumerate(WEEKS)]
    series["avg_score"] = [
        round(sum(c["score"] for c in calls if c["w"] == w) / max(series["calls"][i], 1))
        if series["calls"][i] else None for i, w in enumerate(WEEKS)]

    # ---- emerging, in four-week buckets (counts, never a rate at this volume) ----
    def bucket_counts(keyfn):
        out = collections.defaultdict(lambda: [0, 0, 0])
        for c in calls:
            for bi, (_, ws) in enumerate(BUCKETS):
                if c["w"] in ws:
                    for k in keyfn(c):
                        out[k][bi] += 1
        return out

    emerging = []
    for kind, keyfn in (("category", lambda c: [c["category"]]),
                        ("touchpoint", lambda c: [c["touchpoint"]] if c["touchpoint"] else []),
                        ("signal", lambda c: [s["code"] for s in c["signals"]]),
                        ("product_line", lambda c: [c["product_line"]] if c["product_line"] else [])):
        for k, v in bucket_counts(keyfn).items():
            if sum(v) < 3:
                continue
            emerging.append({"kind": kind, "key": k, "buckets": v, "total": sum(v),
                             "delta": v[2] - v[0], "latest": v[2]})
    emerging.sort(key=lambda r: (-r["delta"], -r["total"]))

    # ---- drivers ----
    drivers = []
    for code, label, fn in IND:
        hits = [c for c in calls if fn(c)]
        if not hits:
            continue
        b = [0, 0, 0]
        for c in hits:
            for bi, (_, ws) in enumerate(BUCKETS):
                if c["w"] in ws:
                    b[bi] += 1
        top_cat = collections.Counter(c["category"] for c in hits).most_common(1)[0]
        top_tp = collections.Counter(c["touchpoint"] for c in hits if c["touchpoint"]).most_common(1)
        drivers.append({"code": code, "label": label, "n": len(hits), "buckets": b,
                        "employers": len({c["employer"] for c in hits}),
                        "top_category": top_cat[0], "top_category_n": top_cat[1],
                        "top_touchpoint": top_tp[0][0] if top_tp else None,
                        "calls": [c["id"] for c in hits]})
    drivers.sort(key=lambda r: -r["n"])

    # ---- actions ----
    actions = []
    counter = {"n": 0}

    def add_action(source_cls, source, title, evidence, owner_team, recommendation,
                   call_ids, employer=None, broker=None, priority="Medium"):
        counter["n"] += 1
        n = counter["n"]
        st, owner, assigned, taken, outcome = WF[n % len(WF)]
        due = ((dt.date.fromisoformat(assigned) + dt.timedelta(days=21)).isoformat()
               if assigned else None)
        overdue = bool(due and dt.date.fromisoformat(due) < PERIOD_END
                       and st in ("assigned", "in_progress"))
        actions.append({
            "id": "ACT-%03d" % n, "title": title, "source": source, "source_cls": source_cls,
            "evidence": evidence, "owner_team": owner_team, "owner": owner,
            "recommendation": recommendation, "calls": call_ids, "employer": employer,
            "broker": broker, "status": "overdue" if overdue else st, "lifecycle": st,
            "assigned_on": assigned, "due": due, "action_taken": taken, "outcome": outcome,
            "priority": priority,
        })

    pg_groups = collections.defaultdict(list)
    for c in calls:
        if c["pg_present"]:
            pg_groups[c["pg_touchpoint"] or "unspecified"].append(c)
    for tp, cs in sorted(pg_groups.items(), key=lambda kv: -len(kv[1])):
        add_action("observed", "process_gap - %s" % (cs[0]["pg_status"] or "UNVALIDATED"),
                   "Rewrite %s: %s" % (tp.replace("_", " "), cs[0]["pg_change"][:90]),
                   "%d call%s proposed a change at this touchpoint"
                   % (len(cs), "s" if len(cs) > 1 else ""),
                   tps.get(tp, {}).get("owner", "Process owner"),
                   "Validate the proposal, attach the minutes consumed, route to the "
                   "touchpoint owner.",
                   [c["id"] for c in cs], priority="High" if len(cs) >= 3 else "Medium")

    kf_groups = collections.defaultdict(list)
    for c in calls:
        if c["kf_present"] and c["kf_rule"]:
            kf_groups[c["kf_rule"]].append(c)
    for rid, cs in sorted(kf_groups.items(), key=lambda kv: -len(kv[1])):
        r = rules.get(rid, {})
        add_action("observed", "knowledge_failure - rule %s" % rid,
                   "Clarify rule %s (%s)" % (rid, r.get("area", "")),
                   "%d call%s stated this rule incorrectly. Commonly confused with: %s"
                   % (len(cs), "s" if len(cs) > 1 else "", (r.get("confused") or "-")[:80]),
                   "Knowledge Management",
                   "Check whether the failures cluster on one agent (training), one "
                   "touchpoint (information design) or both (process).",
                   [c["id"] for c in cs], priority="High" if len(cs) >= 2 else "Low")

    esc = [c for c in calls if c["esc_triggered"] and not c["esc_handled"]]
    if esc:
        trig = sum(c["esc_triggered"] for c in calls)
        add_action("observed", "escalation_missed",
                   "Escalation route refused on %d calls" % len(esc),
                   "Triggered %d, handled %d - refusal rate %d%%"
                   % (trig, sum(c["esc_handled"] for c in calls),
                      round(100 * len(esc) / max(trig, 1))),
                   "Operations",
                   "Check refusals by trigger type - a refusal on retention risk means "
                   "something different from one on a billing limit.",
                   [c["id"] for c in esc], priority="High")

    for c in [c for c in calls if any(s["code"] == "retention_risk" for s in c["signals"])]:
        e = employers.get(c["employer"], {})
        add_action("observed", "retention_risk signal",
                   "Exit language from %s" % e.get("name", c["employer"]),
                   "Verbatim exit or market-test language on %s. Renews %s."
                   % (c["id"], e.get("renewal_month", "?")),
                   "Account Management",
                   "Treat exit language as an escalation trigger, not a sentiment tag.",
                   [c["id"]], employer=c["employer"], broker=c["broker"], priority="High")

    ce_groups = collections.defaultdict(list)
    for c in calls:
        for x in c["control_exceptions"]:
            ce_groups[x].append(c)
    for x, cs in ce_groups.items():
        add_action("observed", "control_exception - %s" % x,
                   "%s on %d calls" % (x.replace("_", " "), len(cs)),
                   "Deterministic check on the opening turns. Agents: %s"
                   % ", ".join(sorted({c["agent"] for c in cs})),
                   "Compliance",
                   "Scripted greeting check and a verification gate, both monitored.",
                   [c["id"] for c in cs], priority="High")

    for b in brk_rows:
        if b["trigger_broker_pattern"]:
            add_action("pattern", "Questions Worth Asking trigger 2",
                       "Broker pattern: %s" % b["agency"],
                       "%d adverse mentions across %d employers in 12 weeks"
                       % (b["adverse_calls"], b["adverse_employers"]),
                       "Broker Relations",
                       "Pull the broker's groups from the Broker Master and check how many "
                       "of their book appear at all.",
                       b["call_ids"], broker=b["id"], priority="High")

    status_counts = collections.Counter(a["status"] for a in actions)

    # ---- questions worth asking, each on its own rolling window ----
    def rolling_max(weeks_span, keyfn, distinct_fn):
        best = {}
        for anchor in WEEKS:
            lo = anchor - weeks_span
            win = [c for c in calls if c["w"] is not None and lo < c["w"] <= anchor]
            groups = collections.defaultdict(set)
            for c in win:
                for k in keyfn(c):
                    groups[k].add(distinct_fn(c))
            for k, v in groups.items():
                best[k] = max(best.get(k, 0), len(v))
        return best

    qwa = []
    t1 = rolling_max(4, lambda c: [(s["code"], c["touchpoint"])
                                   for s in c["signals"] if c["touchpoint"]],
                     lambda c: c["employer"])
    t1_top = sorted(t1.items(), key=lambda kv: -kv[1])[:1]
    qwa.append({"n": 1, "threshold": "4 employers, same signal + touchpoint, rolling 4wk",
                "window": "4wk", "lens": "OPERATIONS",
                "fires": sum(1 for v in t1.values() if v >= 4),
                "best": t1_top[0][1] if t1_top else 0,
                "best_label": ("%s @ %s" % t1_top[0][0]) if t1_top else "-",
                "question": "Is this a common process defect rather than four unrelated incidents?"})
    t5 = rolling_max(4, lambda c: [c["kf_rule"]] if c["kf_present"] and c["kf_rule"] else [],
                     lambda c: c["id"])
    qwa.append({"n": 5, "threshold": "5 calls citing the same rule, rolling 4wk",
                "window": "4wk", "lens": "ORGANIZATION",
                "fires": sum(1 for v in t5.values() if v >= 5),
                "best": max(t5.values()) if t5 else 0,
                "best_label": max(t5, key=t5.get) if t5 else "-",
                "question": "Is this a training problem, a process problem, or an "
                            "information-design problem?"})
    t6 = rolling_max(12, lambda c: [c["pg_touchpoint"]] if c["pg_present"] else [],
                     lambda c: c["id"])
    qwa.append({"n": 6, "threshold": "3 calls proposing the same process gap, 12wk",
                "window": "12wk", "lens": "ORGANIZATION",
                "fires": sum(1 for v in t6.values() if v >= 3),
                "best": max(t6.values()) if t6 else 0,
                "best_label": max(t6, key=t6.get) if t6 else "-",
                "question": "Should this document or screen be rewritten, and what would it save?"})
    t9 = rolling_max(4, lambda c: [c["agent"]] if c["control_exceptions"] else [],
                     lambda c: c["id"])
    qwa.append({"n": 9, "threshold": "3 control exceptions by one agent, rolling 4wk",
                "window": "4wk", "lens": "RISK",
                "fires": sum(1 for v in t9.values() if v >= 3),
                "best": max(t9.values()) if t9 else 0,
                "best_label": max(t9, key=t9.get) if t9 else "-",
                "question": "Is this an individual habit or a gap in what we told everybody?"})
    # Grouped BY EMPLOYER, counting that employer's own calls -- the threshold is
    # "an employer generates >=2 such calls", not ">=2 employers did it once".
    t8 = rolling_max(12, lambda c: ([c["employer"]]
                                    if any(i["code"] == "expansion" for i in c["intent"]) else []),
                     lambda c: c["id"])
    qwa.append({"n": 8, "threshold": "2 unrouted expansion-intent calls, one employer, 12wk",
                "window": "12wk", "lens": "COMMERCIAL",
                "fires": sum(1 for v in t8.values() if v >= 2),
                "best": max(t8.values()) if t8 else 0,
                "best_label": "%d employer%s at %d call each"
                              % (len(t8), "" if len(t8) == 1 else "s",
                                 max(t8.values()) if t8 else 0),
                "question": "Why has an account asking to buy more not reached anyone who "
                            "can sell to them?"})

    # ---- resolution friction by topic ----
    friction = []
    for cat in sorted({c["category"] for c in calls}):
        cs = [c for c in calls if c["category"] == cat]
        if len(cs) < 4:
            continue
        friction.append({
            "topic": cat, "calls": len(cs),
            "avg_aht": round(sum(c["aht"] for c in cs) / len(cs)),
            "repeat": sum(1 for c in cs if c["repeat_of"]),
            "unresolved": sum(1 for c in cs if c["outcome"] == "UNRESOLVED"),
            "escalated": sum(1 for c in cs if c["esc_triggered"]),
            "high_effort": sum(1 for c in cs if c["effort_band"] == "High"),
            "avg_effort": round(sum(c["effort"] for c in cs) / len(cs)),
            "avg_score": round(sum(c["score"] for c in cs) / len(cs)),
            "signals": sum(len(c["signals"]) for c in cs),
        })
    friction.sort(key=lambda r: -(r["repeat"] + r["unresolved"] + r["escalated"]))

    # ---- kpis ----
    elevated = [r for r in emp_rows if r["band"] in ("Elevated", "High")]
    newly = [r for r in elevated
             if r["call_ids"] and all(c["w"] >= 9 for c in calls if c["id"] in r["call_ids"])]
    trig = sum(c["esc_triggered"] for c in calls)
    kpis = {
        "employers_monitored": len(employers),
        "employers_with_calls": len([r for r in emp_rows if r["calls_written"]]),
        "employers_elevated": len(elevated),
        "employers_high": len([r for r in emp_rows if r["band"] == "High"]),
        "employers_watch": len([r for r in emp_rows if r["band"] == "Watch"]),
        "employers_newly_flagged": len(newly),
        # Needs a prior indicator per account to compare against; not available at
        # batch-1 volume. Null so the UI states the reason instead of printing 0.
        "employers_improving": None,
        "risk_signals": sum(len(c["signals"]) for c in calls),
        "calls_written": len(calls), "calls_planned": 600,
        "open_actions": (status_counts["needs_action"] + status_counts["assigned"]
                         + status_counts["in_progress"]),
        "overdue_actions": status_counts["overdue"],
        "monitoring_actions": status_counts["monitoring"],
        "completed_actions": status_counts["completed"],
        "actions_total": len(actions),
        "emerging_issues": len([e for e in emerging if e["delta"] >= 2]),
        "escalation_triggered": trig,
        "escalation_handled": sum(c["esc_handled"] for c in calls),
        "escalation_integrity": round(100 * sum(c["esc_handled"] for c in calls) / max(trig, 1)),
        "resolution_pct": round(100 * sum(1 for c in calls if c["outcome"] == "RESOLVED")
                                / max(len(calls), 1)),
        "unresolved": sum(1 for c in calls if c["outcome"] == "UNRESOLVED"),
        "repeat_pairs": sum(1 for c in calls if c["repeat_of"]),
        "avg_score": round(sum(c["score"] for c in calls) / max(len(calls), 1)),
        "avg_aht": round(sum(c["aht"] for c in calls) / max(len(calls), 1)),
        "enrolled_total": sum(e["enrolled"] for e in employers.values()),
        "premium_total": sum(e["annual_premium"] or 0 for e in employers.values()) or None,
        "premium_elevated": sum(r["annual_premium"] or 0 for r in elevated) or None,
        "fee_total": sum(e["annual_fee"] for e in employers.values()),
        "fee_elevated": sum(r["annual_fee"] for r in elevated),
        # The median is the comparison that matters for cost to serve: a mean is
        # dragged by the two-life groups that sit at the top of the list.
        "minutes_per_life_median": (
            sorted(r["minutes_per_life"] for r in emp_rows if r["minutes_per_life"])
            [len([r for r in emp_rows if r["minutes_per_life"]]) // 2]
            if any(r["minutes_per_life"] for r in emp_rows) else None),
        "recent_calls": len([c for c in calls if c["w"] and c["w"] >= 9]),
        "prior_calls": len([c for c in calls if c["w"] and c["w"] <= 4]),
    }

    out = {
        "meta": {**D["meta"], "generated": dt.date.today().isoformat(),
                 "source_workbook": "nanovox_corpus_v9_build_bible_2.xlsx",
                 "source_pdf": "nanovox_v9_transcripts_batch1_001-100_1.pdf"},
        "kpis": kpis, "weeks": WEEKS, "buckets": [b[0] for b in BUCKETS], "series": series,
        "employers": emp_rows, "brokers": brk_rows, "regions": reg_rows,
        "calls": calls, "agents": agents, "rules": rules, "touchpoints": tps,
        "snippets": snippets, "drivers": drivers, "emerging": emerging[:14],
        "actions": actions, "qwa": qwa, "friction": friction,
    }
    js = "window.NVX = " + json.dumps(out, separators=(",", ":")) + ";\n"
    APP_DATA_JS.write_text(js, encoding="utf-8")

    print("stage 4: %d employers, %d actions, %d drivers -> %s (%d KB)"
          % (len(emp_rows), len(actions), len(drivers), APP_DATA_JS.name, len(js) // 1024))
    print("   bands: %s" % dict(collections.Counter(r["band"] for r in emp_rows)))
    print("   actions: %s" % dict(status_counts))
    print("   escalation integrity: %d%% (%d handled of %d triggered)"
          % (kpis["escalation_integrity"], kpis["escalation_handled"], trig))
    print("   triggers firing: %s of %d"
          % (sum(1 for q in qwa if q["fires"]), len(qwa)))


if __name__ == "__main__":
    main()
