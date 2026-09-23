"""Stage 3 -- join the workbook and the transcripts into one dataset.

Produces the per-call records the prototypes drill into, with each call joined to
its employer, broker, region and agent. Two things are computed here rather than
read, because the workbook does not carry them:

  participation / fee band / COBRA regime  -- derived from eligible headcount and
      rule P-33 ($25 for 2-8, $30 for 9-20, $35 for 21-199, $50 for 200+), and
      the 20-employee Cal-COBRA boundary. The workbook's own columns for these
      are formulas with no cached value.

  member effort / complexity  -- our composites, from talk time, turn count,
      repeat contact, escalation and outcome. They are not corpus values and the
      UI labels them "derived" wherever they appear. Sentiment and a
      sensitive-content flag are NOT derived: the v9 tag schema has no field for
      them and nothing here stands in for one.

Caller identity comes from the tracker sheet joined through Member Master and
Employer Contacts -- never from the transcript header, which stopped carrying the
caller's name in the current revision.
"""
import collections
import datetime as dt
import json
import re

from paths import (DATASET_JSON, TRANSCRIPTS_TXT, WORKBOOK_JSON, ensure_build,
                   require)

PERIOD_START = dt.datetime(2026, 7, 6)
MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}
SPEAKER = re.compile(r"^\s*([A-Z][A-Za-z'\-]{1,14}):\s*(.+)$", re.M)


def cell(row, i):
    return (row[i] if i < len(row) else "") or ""


def fee_band(eligible):
    if eligible <= 8:
        return 25
    if eligible <= 20:
        return 30
    if eligible <= 199:
        return 35
    return 50


def premium_per_life(d):
    """The annual premium lever, read from Distribution Targets rather than
    hardcoded, so a corpus revision that changes it changes the figures.

    The workbook has no per-line rate table, but it does carry one reference
    figure -- 'Annual premium per enrolled life ($)' -- which is the lever the
    Employer Master population was built from. It is flat, so premium per
    account is headcount in different units: it converts lives into dollars for
    a board, and cannot rank two accounts of the same size. The admin fee band
    is the differentiated number.
    """
    for r in d.get("Distribution Targets", []):
        label = " ".join(str(x) for x in r)
        if "Annual premium per enrolled life" in label:
            for x in r:
                try:
                    v = float(str(x).replace(",", ""))
                except (TypeError, ValueError):
                    continue
                if v > 1:  # skip the share/index columns
                    return v
    return None


def parse_date(s):
    m = re.search(r"(\d{2}) (\w{3}) (\d{4})\s+(\d{2}):(\d{2})", s)
    if not m:
        return None
    return dt.datetime.strptime("%s %s %s %s:%s" % m.groups(), "%d %b %Y %H:%M")


def pct_rank(sorted_vals, v):
    lo = sum(1 for x in sorted_vals if x < v)
    return lo / max(len(sorted_vals) - 1, 1)


def main():
    require(WORKBOOK_JSON, "stage 3 -- run stage 1 first")
    require(TRANSCRIPTS_TXT, "stage 3 -- run stage 2 first")
    ensure_build()
    d = json.loads(WORKBOOK_JSON.read_text(encoding="utf-8"))

    def rows_of(sheet, prefix):
        return [r for r in d[sheet][4:] if cell(r, 0).strip().startswith(prefix)]

    # ---- brokers ----
    bh = d["Broker Master"][3]
    BI = {c: i for i, c in enumerate(bh) if c}
    brokers = {}
    for r in rows_of("Broker Master", "BRK"):
        bid = cell(r, 0).strip()
        brokers[bid] = {
            "id": bid,
            "name": cell(r, BI["Broker"]).strip(),
            "agency": cell(r, BI["Agency"]).strip(),
            "groups_in_book": cell(r, BI["Groups in book"]).strip(),
            "region": cell(r, BI["Region"]).strip(),
            "signal_profile": cell(r, BI["Signal profile"]).strip(),
        }

    # ---- employers ----
    prem = premium_per_life(d)
    if prem is None:
        print("   warning: no annual premium lever found in Distribution Targets;")
        print("            premium figures will be absent")
    eh = d["Employer Master"][3]
    EI = {c: i for i, c in enumerate(eh) if c}
    employers = {}
    for r in rows_of("Employer Master", "EMP"):
        eid = cell(r, 0).strip()
        elig = int(float(cell(r, EI["Eligible employees"]) or 0))
        enr = int(float(cell(r, EI["Enrolled lives"]) or 0))
        planned = int(float(cell(r, EI["Planned calls"]) or 0))
        employers[eid] = {
            "id": eid,
            "name": cell(r, EI["Employer name"]).strip(),
            "industry": cell(r, EI["Industry"]).strip(),
            "design_churn_profile": cell(r, EI["Churn profile"]).strip(),
            "eligible": elig,
            "enrolled": enr,
            "participation": round(enr / elig, 4) if elig else None,
            "fee_band": fee_band(elig),
            # Revenue, both sides of it. The fee is banded by headcount and is
            # what we actually charge; the premium is what flows through us.
            "annual_fee": fee_band(elig) * 12,
            "annual_premium": round(enr * prem) if prem and enr else None,
            "cobra": "Cal-COBRA" if elig < 20 else "Federal COBRA",
            "region": cell(r, EI["Region"]).strip(),
            "renewal_month": cell(r, EI["Renewal month"]).strip(),
            "renewal_m": MONTHS.get(cell(r, EI["Renewal month"]).strip(), 0),
            "broker": cell(r, EI["Broker of record"]).strip(),
            "sponsorship": cell(r, EI["Dental sponsorship"]).strip(),
            "lines": cell(r, EI["Lines held"]).strip(),
            "planned_calls": planned,
            "planned_member": int(float(cell(r, EI["Member calls"]) or 0)),
            "planned_employer": int(float(cell(r, EI["Employer calls"]) or 0)),
            "calls_per_100": round(planned / enr * 100, 2) if enr else None,
        }

    # ---- callers -> employer ----
    caller_emp, member_age = {}, {}
    for r in rows_of("Member Master", "CB"):
        caller_emp[cell(r, 0).strip()] = cell(r, 3).strip()
        member_age[cell(r, 0).strip()] = cell(r, 2).strip()
    for r in rows_of("Employer Contacts", "CON"):
        caller_emp[cell(r, 0).strip()] = cell(r, 4).strip()
    contact_auth = {cell(r, 0).strip(): cell(r, 3).strip()
                    for r in rows_of("Employer Contacts", "CON")}

    # ---- agents ----
    ah = d["Agent Roster"][3]
    AI = {c: i for i, c in enumerate(ah) if c}
    agents = {}
    for r in rows_of("Agent Roster", "AGT"):
        aid = cell(r, 0).strip()
        def num(prefix):
            """Matched on a prefix, not the full header: the variance column is
            titled 'Score variance (+/-)' with a typographic sign that a corpus
            revision is free to change."""
            for name, i in AI.items():
                if name.startswith(prefix):
                    try:
                        return float(cell(r, i))
                    except (TypeError, ValueError):
                        return None
            return None

        agents[aid] = {
            "id": aid,
            "name": cell(r, AI["Agent"]).strip(),
            "band": cell(r, AI["Band"]).strip(),
            "pattern": cell(r, AI["Dominant pattern"]).strip(),
            # The designed population, carried through so the UI can say how far
            # the written corpus is from the volume the roster itself requires:
            # "thirty calls each, which is exactly the minimum needed to quote an
            # agent-level rate".
            "planned_calls": int(num("Planned calls") or 0),
            "expected_score": num("Expected mean score"),
            "score_variance": num("Score variance"),
        }

    # ---- rules ----
    rules = {}
    for sheet, prefix in (("Rules — Program", "P"),
                          ("Rules — Administration", "A"),
                          ("Rules — Carrier", "C")):
        hdr = next(r for r in d[sheet] if cell(r, 0) == "Rule ID")
        HI = {c: i for i, c in enumerate(hdr) if c}
        area_key = "Area" if "Area" in HI else "Carrier / line"
        for r in d[sheet]:
            rid = cell(r, 0).strip()
            if re.fullmatch(prefix + r"-\d+", rid):
                rules[rid] = {
                    "id": rid, "layer": prefix,
                    "area": cell(r, HI[area_key]).strip(),
                    "rule": cell(r, HI["Rule"]).strip(),
                    "confused": cell(r, HI["Commonly confused with"]).strip(),
                    "confidence": cell(r, HI["Confidence"]).strip(),
                }

    # ---- touchpoint owners ----
    tp_owner = {}
    for r in d["Touchpoints"][3:]:
        k = cell(r, 0).strip()
        if k and k != "Touchpoint" and "_" in k:
            tp_owner[k] = {"owner": cell(r, 1).strip(), "controls": cell(r, 2).strip()}

    # ---- transcripts: turn counts and quoted lines ----
    text = TRANSCRIPTS_TXT.read_text(encoding="utf-8")
    turns, snippets = {}, {}
    for part in re.split(r"\n(?=C-\d{4} — )", text):
        m = re.match(r"(C-\d{4}) — ", part)
        if not m:
            continue
        cid = m.group(1)
        body = part.split("CALL TAGS")[0]
        lines = SPEAKER.findall(body)
        turns[cid] = len(lines)
        snippets[cid] = [{"who": w, "text": re.sub(r"\s+", " ", t).strip()[:260]}
                         for w, t in lines]

    # ---- calls ----
    th = d["Transcript Tracker"][3]
    TI = {c: i for i, c in enumerate(th) if c}
    calls = []
    for r in d["Transcript Tracker"][4:]:
        cid = cell(r, 0).strip()
        if not re.fullmatch(r"C-\d{4}", cid):
            continue
        ts = parse_date(cell(r, TI["Date / time"]))
        ref = cell(r, TI["caller_ref"]).strip()
        eid = caller_emp.get(ref, "")
        esc = cell(r, TI["Escalation"]).strip()
        sigs = []
        for s in cell(r, TI["Signals"]).split(";"):
            s = s.strip()
            if s:
                p = [x.strip() for x in s.split("|")]
                sigs.append({"code": p[0],
                             "severity": p[1] if len(p) > 1 else "",
                             "owner": p[2] if len(p) > 2 else ""})
        comp = [x.strip() for x in cell(r, TI["Complaint"]).strip().split("|")]
        kf = [x.strip() for x in cell(r, TI["Knowledge failure"]).strip().split("|")]
        pg = [x.strip() for x in cell(r, TI["Process gap"]).strip().split("|")]
        bn = [x.strip() for x in cell(r, TI["Broker named"]).strip().split("|")]
        tp = cell(r, TI["Touchpoint"]).strip()
        intents = []
        for raw in cell(r, TI["Intent"]).split(";"):
            raw = raw.strip()
            if not raw or raw == "none":
                continue
            p = [x.strip() for x in raw.split("|")]
            turn = None
            if len(p) > 1:
                mt = re.search(r"turn (\d+)", p[1])
                if mt:
                    turn = int(mt.group(1))
            intents.append({"code": p[0], "turn": turn})
        calls.append({
            "id": cid,
            "ts": ts.isoformat() if ts else None,
            "date": ts.strftime("%Y-%m-%d") if ts else None,
            "hour": ts.hour if ts else None,
            "w": ((ts - PERIOD_START).days // 7 + 1) if ts else None,
            "caller_type": cell(r, TI["Caller type"]).strip(),
            "caller_ref": ref,
            "caller_name": cell(r, TI["Caller name"]).strip(),
            "authority": contact_auth.get(ref, ""),
            "member_age": member_age.get(ref, ""),
            "employer": eid,
            "broker": employers.get(eid, {}).get("broker", ""),
            "region": employers.get(eid, {}).get("region", ""),
            "agent": cell(r, TI["Agent"]).split("|")[0].strip(),
            "agent_name": (cell(r, TI["Agent"]).split("|")[1].strip()
                           if "|" in cell(r, TI["Agent"]) else ""),
            "category": cell(r, TI["Category"]).strip(),
            "product_line": cell(r, TI["Product line"]).strip(),
            "rule_refs": [x.strip() for x in cell(r, TI["Rule refs"]).split(",")
                          if x.strip() and x.strip() != "—"],
            "touchpoint": (tp if tp not in ("—", "-", "") else None),
            "outcome": cell(r, TI["Outcome"]).strip(),
            "score": int(float(cell(r, TI["Score"]) or 0)),
            "aht": int(float(cell(r, TI["AHT (s)"]) or 0)),
            "archetype": cell(r, TI["Archetype"]).strip(),
            "complaint": comp[0] == "present",
            "complaint_to": comp[1] if len(comp) > 1 else "",
            "signals": sigs,
            "esc_triggered": "triggered true" in esc.lower(),
            "esc_requested": "requested_by_caller true" in esc.lower(),
            "esc_handled": "handled true" in esc.lower(),
            "esc_type": (esc.split("|")[1].strip()
                         if esc.lower().startswith("triggered true") and "|" in esc else ""),
            "control_exceptions": [x.strip() for x in cell(r, TI["Control exceptions"]).split(";")
                                   if x.strip()],
            "kf_present": kf[0] == "present",
            "kf_rule": kf[1] if len(kf) > 1 else "",
            "kf_statement": kf[2] if len(kf) > 2 else "",
            "intent": intents,
            "pg_present": pg[0] == "present",
            "pg_change": pg[1] if len(pg) > 1 else "",
            "pg_touchpoint": pg[2] if len(pg) > 2 else "",
            "pg_raised_by": pg[3] if len(pg) > 3 else "",
            "pg_status": pg[4] if len(pg) > 4 else "",
            "broker_named": bn[0] == "present",
            "broker_named_ref": bn[1] if len(bn) > 1 else "",
            "broker_named_sentiment": bn[2] if len(bn) > 2 else "",
            "repeat_of": cell(r, TI["Repeat of"]).strip(),
            "turns": turns.get(cid, 0),
        })

    # ---- derived composites (labelled "derived" in the UI) ----
    ahts = sorted(c["aht"] for c in calls)
    trns = sorted(c["turns"] for c in calls)
    for c in calls:
        a = pct_rank(ahts, c["aht"])
        t = pct_rank(trns, c["turns"])
        eff = 45 * a
        if c["repeat_of"]:
            eff += 20
        if c["esc_requested"]:
            eff += 12
        if c["outcome"] == "UNRESOLVED":
            eff += 18
        elif c["outcome"] == "PARTIALLY RESOLVED":
            eff += 8
        if c["esc_triggered"] and not c["esc_handled"]:
            eff += 10
        c["effort"] = round(min(eff, 100))
        c["effort_band"] = ("High" if c["effort"] >= 60
                            else "Medium" if c["effort"] >= 35 else "Low")
        cx = 55 * a + 45 * t
        if len(c["rule_refs"]) >= 2:
            cx += 8
        if len(c["signals"]) >= 2:
            cx += 6
        c["complexity"] = round(min(cx, 100))
        c["complexity_band"] = ("High" if c["complexity"] >= 60
                                else "Medium" if c["complexity"] >= 35 else "Low")

    unjoined = [c["id"] for c in calls if not c["employer"]]
    DATASET_JSON.write_text(json.dumps({
        "meta": {"period_start": "2026-07-06", "period_end": "2026-09-25", "weeks": 12,
                 "calls_written": len(calls), "calls_planned": 600,
                 "employers": len(employers), "brokers": len(brokers),
                 "agents": len(agents), "rules": len(rules)},
        "employers": employers, "brokers": brokers, "agents": agents,
        "calls": calls, "rules": rules, "touchpoints": tp_owner, "snippets": snippets,
    }, indent=1), encoding="utf-8")

    print("stage 3: %d calls, %d employers, %d brokers, %d agents, %d rules -> %s"
          % (len(calls), len(employers), len(brokers), len(agents), len(rules),
             DATASET_JSON.name))
    print("   outcomes: %s" % dict(collections.Counter(c["outcome"] for c in calls)))
    print("   turns: mean %.1f, range %d-%d"
          % (sum(c["turns"] for c in calls) / max(len(calls), 1),
             min(c["turns"] for c in calls), max(c["turns"] for c in calls)))
    if unjoined:
        print("   WARNING: %d calls did not join to an employer: %s"
              % (len(unjoined), ", ".join(unjoined[:8])))
    if any(c["turns"] == 0 for c in calls):
        missing = [c["id"] for c in calls if c["turns"] == 0]
        print("   WARNING: %d calls have no transcript turns -- the tracker and the PDF\n"
              "            may be from different revisions: %s"
              % (len(missing), ", ".join(missing[:8])))


if __name__ == "__main__":
    main()
