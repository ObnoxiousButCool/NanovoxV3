/* NanoVox Account Signals - shared behaviour: filters, charts, drill-down.
   All figures come from window.NVX (built from the v9 workbook + batch 1 transcripts). */
(function () {
  const D = window.NVX;
  const NV = window.NV = { D };

  /* ---------------- formatting ---------------- */
  const pad = (n) => (n < 10 ? "0" + n : "" + n);
  NV.pct = (n) => (n === null || n === undefined ? "–" : n + "%");
  NV.mmss = (s) => Math.floor(s / 60) + "m " + pad(s % 60) + "s";
  NV.esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  NV.titleCase = (s) => String(s || "").replace(/_/g, " ").replace(/^./, (m) => m.toUpperCase());
  NV.weekLabel = (w) => "Wk " + w;
  NV.weekDates = (w) => {
    const start = new Date(Date.UTC(2026, 6, 6) + (w - 1) * 7 * 864e5);
    const end = new Date(start.getTime() + 4 * 864e5);
    const f = (d) => d.getUTCDate() + " " + ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul",
      "Aug", "Sep", "Oct", "Nov", "Dec"][d.getUTCMonth()];
    return f(start) + " – " + f(end);
  };
  NV.clsChip = (kind, extra) => '<span class="cls cls-' + kind + '"' +
    (extra ? ' title="' + NV.esc(extra) + '"' : "") + ">" + kind + "</span>";
  NV.bandPill = (band) => '<span class="pill pill-' + band.toLowerCase() + '">' + band + "</span>";

  /* Call quality, banded the way the v9 Call Quality Framework bands it rather
     than averaged. An average of 73 hides that a fifth of calls are POOR by the
     framework's own definition, which is the number worth knowing. */
  NV.QUALITY_BANDS = [
    ["GOOD", 86, "Good", "86 and above"],
    ["AVERAGE", 60, "Average", "60 to 85"],
    ["POOR", 0, "Poor", "below 60"],
  ];
  NV.qualityBand = (score) =>
    (typeof score !== "number" ? null
      : score >= 86 ? "GOOD" : score >= 60 ? "AVERAGE" : "POOR");
  NV.qualityTone = (b) => (b === "GOOD" ? "good" : b === "POOR" ? "serious" : "warning");
  NV.qualitySplit = (calls) => {
    const out = { GOOD: 0, AVERAGE: 0, POOR: 0 };
    calls.forEach((c) => { const b = NV.qualityBand(c.score); if (b) out[b] += 1; });
    return out;
  };

  /* How the call was handled. The corpus tags every call with an archetype, and
     in batch 1 it maps one-to-one onto outcome - so it is NOT an independent
     signal, and nothing here should present it as one. What it adds is a split
     of the unresolved calls into two different failure modes: a brush-off is a
     behaviour, a circular call is a process. The order is worst-first. */
  NV.ARCHETYPES = [
    ["Brush-off", "Ended without solving it", true],
    ["Circular", "The caller went round in loops", true],
    ["Competent but constrained", "Handled well, blocked by a rule or a system", false],
    ["Escalated or handed off correctly", "Passed on, correctly", false],
    ["Competent and resolved", "Solved on the call", false],
  ];
  NV.archetypeSplit = (calls) => NV.ARCHETYPES.map(([name, gloss, adverse]) => {
    const cs = calls.filter((c) => c.archetype === name);
    return {
      name: name, gloss: gloss, adverse: adverse, calls: cs, n: cs.length,
      avgScore: cs.length ? Math.round(cs.reduce((a, c) => a + c.score, 0) / cs.length) : null,
      unresolved: cs.filter((c) => c.outcome === "UNRESOLVED").length,
      repeat: cs.filter((c) => c.repeat_of).length,
      employers: new Set(cs.map((c) => c.employer)).size,
    };
  }).filter((r) => r.n);
  NV.delta = (n, invert) => {
    if (n === 0) return '<span class="delta flat">→ 0</span>';
    const bad = invert ? n < 0 : n > 0;
    return '<span class="delta ' + (bad ? "up" : "down") + '">' +
      (n > 0 ? "↑ +" : "↓ ") + n + "</span>";
  };

  const EMP = {}; D.employers.forEach((e) => (EMP[e.id] = e));
  const BRK = {}; D.brokers.forEach((b) => (BRK[b.id] = b));
  NV.emp = (id) => EMP[id] || { name: id, id: id };
  NV.brk = (id) => BRK[id] || { agency: id, id: id };
  NV.call = (id) => D.calls.find((c) => c.id === id);

  /* ---------------- filter state ---------------- */
  const DEFAULTS = {
    mode: "week", week: "all", month: "all", from: "", to: "", compare: "prev",
    region: "", broker: "", employer: "", band: "",
    category: "", line: "", touchpoint: "", outcome: "", signal: "", agent: "",
    callerType: "", effort: "", complexity: "", esc: "", repeat: "", compliance: "",
    intent: "", complaint: "", actionStatus: "", quality: "", archetype: "",
  };
  const KEY = "nvx-filters-v1";
  let S = Object.assign({}, DEFAULTS);
  /* Precedence: URL wins over stored state, so a link someone sends reproduces
     the view they were looking at rather than the recipient's own last filters.
     Storage is per-browser and can be empty or throw, so every access is
     guarded and the page renders correctly without it. */
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) S = Object.assign(S, JSON.parse(raw));
  } catch (e) { /* private window or blocked storage - defaults are fine */ }
  try {
    const q = new URLSearchParams(window.location.search);
    let fromUrl = false;
    Object.keys(DEFAULTS).forEach((k) => {
      if (q.has(k)) { S[k] = q.get(k); fromUrl = true; }
    });
    if (fromUrl) {
      try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) { /* ignore */ }
    }
  } catch (e) { /* no URLSearchParams - defaults are fine */ }
  NV.S = S;

  function writeUrl() {
    try {
      const q = new URLSearchParams();
      Object.keys(DEFAULTS).forEach((k) => {
        if (S[k] && S[k] !== DEFAULTS[k]) q.set(k, S[k]);
      });
      const qs = q.toString();
      window.history.replaceState(null, "",
        window.location.pathname + (qs ? "?" + qs : ""));
    } catch (e) { /* history blocked - the filters still work */ }
  }

  const subs = [];
  NV.onChange = (fn) => { subs.push(fn); };
  NV.set = (k, v) => {
    S[k] = v;
    try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) { /* ignore */ }
    writeUrl();
    subs.forEach((f) => f());
  };
  NV.reset = () => {
    S = Object.assign(NV.S, DEFAULTS);
    try { localStorage.removeItem(KEY); } catch (e) { /* ignore */ }
    writeUrl();
    subs.forEach((f) => f());
  };
  /* Carry the filters across a page change, so a shared link keeps working when
     the recipient navigates. */
  NV.href = (page) => {
    try {
      const q = new URLSearchParams();
      Object.keys(DEFAULTS).forEach((k) => {
        if (S[k] && S[k] !== DEFAULTS[k]) q.set(k, S[k]);
      });
      const qs = q.toString();
      return page + (qs ? "?" + qs : "");
    } catch (e) { return page; }
  };

  /* ---------------- theme ----------------
     Three states, and light is the default: this gets read in meetings and
     printed, where a dark ground is the wrong starting point regardless of how
     the laptop is set. "Auto" stays available as a deliberate choice rather
     than the fallback. Either fixed choice stamps data-theme on <html>, which
     both dark blocks in the stylesheet are written to respect, so it beats the
     OS. The same key is read by the inline snippet in each page's head, which
     runs before first paint so the wrong ground colour never flashes. */
  const TKEY = "nvx-theme";
  NV.themeRead = () => {
    try {
      const v = localStorage.getItem(TKEY);
      return v === "dark" || v === "system" ? v : "light";
    } catch (e) { return "light"; }
  };
  NV.themeApply = (mode) => {
    const el = document.documentElement;
    if (mode === "light" || mode === "dark") el.setAttribute("data-theme", mode);
    else el.removeAttribute("data-theme");
  };
  NV.themeSet = (mode) => {
    /* All three are stored explicitly, including light. Removing the key would
       make "light" and "never chose" the same state, which is harmless now but
       stops being harmless the moment the default changes again. */
    try {
      localStorage.setItem(TKEY, mode);
    } catch (e) { /* storage blocked - the choice still applies for this page */ }
    NV.themeApply(mode);
    paintThemer();
    repaintForTheme();
  };
  /* Charts bake some colours into SVG attributes rather than leaving them to
     CSS, and NV.inkOn caches by token *name* while the token's value changes
     with the theme. Both have to be invalidated, or a live switch reuses the
     other theme's ink - which fails contrast outright on the heatmap. */
  function repaintForTheme() {
    if (NV.clearInkCache) NV.clearInkCache();
    subs.forEach((f) => f());
  }
  /* Someone on Auto whose OS flips needs the same invalidation. */
  try {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onOs = () => { if (NV.themeRead() === "system") repaintForTheme(); };
    if (mq.addEventListener) mq.addEventListener("change", onOs);
    else if (mq.addListener) mq.addListener(onOs);
  } catch (e) { /* no matchMedia - a reload picks up the change */ }
  const THEMES = [["light", "Light"], ["dark", "Dark"], ["system", "Auto"]];
  NV.themer = () => {
    const cur = NV.themeRead();
    return '<div class="themer" role="group" aria-label="Colour theme">' +
      THEMES.map(([v, l]) =>
        '<button type="button" data-theme-set="' + v + '" aria-pressed="' +
        (v === cur) + '">' + l + "</button>").join("") + "</div>";
  };
  function paintThemer() {
    const cur = NV.themeRead();
    document.querySelectorAll("[data-theme-set]").forEach((b) => {
      b.setAttribute("aria-pressed", String(b.getAttribute("data-theme-set") === cur));
    });
  }
  /* Delegated, because the rail is injected after this script runs. */
  document.addEventListener("click", (e) => {
    const b = e.target.closest && e.target.closest("[data-theme-set]");
    if (b) NV.themeSet(b.getAttribute("data-theme-set"));
  });
  NV.themeApply(NV.themeRead());

  /* ---------------- keyboard ----------------
     Rows and cards are activated by click, which leaves keyboard users with no
     way to drill in at all. Anything clickable gets a tab stop and responds to
     Enter and Space. */
  NV.wireKeyboard = (root) => {
    (root || document).querySelectorAll(
      ".clickable:not([tabindex]), .card:not([tabindex])").forEach((el) => {
      el.setAttribute("tabindex", "0");
      el.setAttribute("role", "button");
    });
  };
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const el = e.target.closest && e.target.closest(".clickable, .card");
    if (!el) return;
    e.preventDefault();
    el.click();
  });

  const MONTH_WEEKS = { Jul: [1, 2, 3, 4], Aug: [5, 6, 7, 8], Sep: [9, 10, 11, 12] };
  NV.activeWeeks = () => {
    if (S.mode === "week" && S.week !== "all") return [+S.week];
    if (S.mode === "month" && S.month !== "all") return MONTH_WEEKS[S.month] || D.weeks;
    if (S.mode === "custom" && S.from && S.to) {
      return D.weeks.filter((w) => {
        const s = new Date(Date.UTC(2026, 6, 6) + (w - 1) * 7 * 864e5);
        return s >= new Date(S.from) && s <= new Date(S.to);
      });
    }
    return D.weeks;
  };
  NV.priorWeeks = () => {
    const a = NV.activeWeeks();
    if (a.length === D.weeks.length) return [];
    const span = a.length, lo = Math.min.apply(null, a);
    return D.weeks.filter((w) => w < lo && w >= lo - span);
  };

  /* A comparison that is always meaningful.
     Selecting the full window leaves no prior period to compare against, which
     would make "what changed?" permanently blank on the default view. So when no
     sub-period is chosen, fall back to an explicit four-week split and say which
     weeks are being compared -- never an unlabelled delta. */
  NV.comparison = () => {
    const now = NV.activeWeeks(), prior = NV.priorWeeks();
    if (prior.length) {
      return { now: now, prior: prior, fromFilter: true,
               label: "the selected period against the " + prior.length +
                      " week" + (prior.length === 1 ? "" : "s") + " before it" };
    }
    return { now: [9, 10, 11, 12], prior: [5, 6, 7, 8], fromFilter: false,
             label: "Wk 9–12 against Wk 5–8" };
  };

  /* Calls in an arbitrary week set, with every non-period filter still applied. */
  NV.callsIn = (weeks) => D.calls.filter((c) => weeks.indexOf(c.w) !== -1 && matchDims(c));

  /* A delta with its direction read correctly: more unresolved calls is bad,
     more resolved calls is good, so the caller says which way is which. */
  NV.deltaChip = (now, prior, badWhenUp) => {
    const d = now - prior;
    if (d === 0) return '<span class="delta flat">no change</span>';
    const bad = badWhenUp ? d > 0 : d < 0;
    return '<span class="delta ' + (bad ? "up" : "down") + '">' +
      (d > 0 ? "↑ +" : "↓ ") + Math.abs(d) + "</span>";
  };

  function matchDims(c) {
    if (S.region && c.region !== S.region) return false;
    if (S.broker && c.broker !== S.broker) return false;
    if (S.employer && c.employer !== S.employer) return false;
    /* Risk band is deliberately NOT tested here. A band is a property of an
       employer's calls in the period, so it has to be computed after the rest of
       the filtering, in NV.calls() below -- testing it here would need the band
       before the call set that defines it. */
    if (S.category && c.category !== S.category) return false;
    if (S.line && c.product_line !== S.line) return false;
    if (S.touchpoint && c.touchpoint !== S.touchpoint) return false;
    if (S.outcome && c.outcome !== S.outcome) return false;
    if (S.signal && !c.signals.some((s) => s.code === S.signal)) return false;
    if (S.agent && c.agent !== S.agent) return false;
    if (S.callerType && c.caller_type !== S.callerType) return false;
    if (S.effort && c.effort_band !== S.effort) return false;
    if (S.complexity && c.complexity_band !== S.complexity) return false;
    if (S.quality && NV.qualityBand(c.score) !== S.quality) return false;
    if (S.archetype && c.archetype !== S.archetype) return false;
    if (S.esc === "triggered" && !c.esc_triggered) return false;
    if (S.esc === "handled" && !c.esc_handled) return false;
    if (S.esc === "missed" && !(c.esc_triggered && !c.esc_handled)) return false;
    if (S.esc === "requested" && !c.esc_requested) return false;
    if (S.repeat === "yes" && !c.repeat_of) return false;
    if (S.repeat === "no" && c.repeat_of) return false;
    if (S.compliance === "yes" && !c.control_exceptions.length) return false;
    if (S.intent && !c.intent.some((i) => i.code === S.intent)) return false;
    if (S.complaint && c.complaint_to !== S.complaint) return false;
    return true;
  }
  NV.calls = () => {
    const w = NV.activeWeeks();
    const list = D.calls.filter((c) => w.indexOf(c.w) !== -1 && matchDims(c));
    if (!S.band) return list;
    const byEmp = {};
    list.forEach((c) => { (byEmp[c.employer] = byEmp[c.employer] || []).push(c); });
    const band = {};
    Object.keys(byEmp).forEach((k) => {
      band[k] = NV.bandFor(NV.indicatorsFor(byEmp[k]).length);
    });
    return list.filter((c) => band[c.employer] === S.band);
  };
  NV.callsPrior = () => {
    const w = NV.priorWeeks();
    if (!w.length) return [];
    return D.calls.filter((c) => w.indexOf(c.w) !== -1 && matchDims(c));
  };
  /* ---- indicator families, recomputed for the calls in scope ----
     The same ten predicates stage 4 uses. They live here as well so the risk
     band answers the period filter: a band computed over the full 12 weeks while
     the figures beside it cover one week would be two scopes in one panel. The
     precomputed values in data.js remain the full-window baseline. */
  NV.INDICATORS = [
    ["unresolved", "Unresolved outcome", (c) => c.outcome === "UNRESOLVED"],
    ["escalation_missed", "Escalation requested, not handled",
      (c) => c.esc_triggered && !c.esc_handled],
    ["complaint_choice", "Complaint attributed to Choice",
      (c) => c.complaint && c.complaint_to === "CHOICE"],
    ["repeat_contact", "Repeat contact on the same issue", (c) => !!c.repeat_of],
    ["exit_language", "Exit or market-test language, verbatim",
      (c) => c.intent.some((i) => i.code === "market_test" || i.code === "cancellation")],
    ["critical_signal", "Critical-severity signal raised",
      (c) => c.signals.some((s) => s.severity === "CRITICAL")],
    ["control_exception", "Compliance control exception", (c) => c.control_exceptions.length > 0],
    ["knowledge_failure", "Agent stated a published rule incorrectly", (c) => c.kf_present],
    ["high_effort", "High member effort", (c) => c.effort_band === "High"],
    ["broker_adverse", "Broker named adversely by the caller",
      (c) => c.signals.some((s) => s.code === "broker_conduct_adverse")],
  ];
  NV.indicatorsFor = (calls) => NV.INDICATORS.map(([code, label, fn]) => {
    const hits = calls.filter(fn);
    return hits.length ? { code: code, label: label, n: hits.length,
      calls: hits.map((c) => c.id) } : null;
  }).filter(Boolean);
  NV.bandFor = (n) => (n === 0 ? "None" : n === 1 ? "Watch" : n === 2 ? "Elevated" : "High");

  /* Employers in scope, each carrying its band for the calls in the current
     period. `scopedCalls` is the period-filtered set; `allCalls` is every
     written call for that account, so a page can show both without conflating. */
  NV.employersInScope = () => {
    let list = D.employers;
    if (S.region) list = list.filter((e) => e.region === S.region);
    if (S.broker) list = list.filter((e) => e.broker === S.broker);
    if (S.employer) list = list.filter((e) => e.id === S.employer);
    const scoped = NV.calls();
    const byEmp = {};
    scoped.forEach((c) => { (byEmp[c.employer] = byEmp[c.employer] || []).push(c); });
    list = list.map((e) => {
      const cs = byEmp[e.id] || [];
      const inds = NV.indicatorsFor(cs);
      return Object.assign({}, e, {
        scopedCalls: cs,
        scoped_written: cs.length,
        scoped_indicators: inds,
        scoped_families: inds.length,
        scoped_band: NV.bandFor(inds.length),
        scoped_signals: cs.reduce((a, c) => a + c.signals.length, 0),
        scoped_avg_score: cs.length
          ? Math.round(cs.reduce((a, c) => a + c.score, 0) / cs.length) : null,
        scoped_avg_effort: cs.length
          ? Math.round(cs.reduce((a, c) => a + c.effort, 0) / cs.length) : null,
      });
    });
    if (S.band) list = list.filter((e) => e.scoped_band === S.band);
    return list;
  };

  /* ---------------- rail + filter bar ---------------- */
  const PAGES = [
    ["exec.html", "Board scorecard", "Five questions"],
    ["index.html", "Risk overview", "Where is the risk?"],
    ["employer.html", "Employer intelligence", "Why this account?"],
    ["actions.html", "Action centre", "What are we doing?"],
    ["hierarchy.html", "Broker &amp; region", "Isolated or systemic?"],
    ["agents.html", "Agent conduct", "Events, not scores"],
    /* Hidden from the rail, not deleted: rules.html still works if you open it
       directly, and the rulebook it reads is still quoted in the call-evidence
       drawer on every page. Put this line back to show it again. */
    /* ["rules.html", "Rule intelligence", "What do we misexplain?"], */
  ];
  NV.rail = (active) => {
    const nav = PAGES.map(([href, label, sub]) =>
      '<a class="nav" href="' + NV.href(href) + '"' +
      (href === active ? ' aria-current="page"' : "") +
      ">" + label + "<small>" + sub + "</small></a>").join("");
    return '<aside class="rail"><div class="brandmark"><span class="dot">NV</span>' +
      "<div><b>NanoVox</b><span>Account signals</span></div></div>" +
      "<nav>" + nav + "</nav>" +
      '<div class="foot">' + NV.themer() +
      '<span class="footnote">Corpus v9 · batch 1<br>' + D.kpis.calls_written +
      " of " + D.kpis.calls_planned + " calls written<br>" +
      D.meta.weeks + " weeks to 25 Sep 2026</span></div></aside>";
  };

  const uniq = (arr) => Array.from(new Set(arr.filter(Boolean))).sort();
  const opts = (list, cur, anyLabel) =>
    '<option value="">' + anyLabel + "</option>" +
    list.map((o) => {
      const v = typeof o === "string" ? o : o.v, l = typeof o === "string" ? NV.titleCase(o) : o.l;
      return '<option value="' + NV.esc(v) + '"' + (cur === v ? " selected" : "") + ">" +
        NV.esc(l) + "</option>";
    }).join("");

  function fg(label, id, html) {
    return '<div class="fg"><label for="' + id + '">' + label + "</label>" + html + "</div>";
  }
  function sel(id, key, list, anyLabel) {
    return '<select id="' + id + '" data-k="' + key + '">' + opts(list, S[key], anyLabel) + "</select>";
  }

  NV.filterBar = (opts) => {
    const compact = !!(opts && opts.compact);
    const periodCtl = S.mode === "week"
      ? sel("f-week", "week", D.weeks.map((w) => ({ v: "" + w, l: "Wk " + w + " · " + NV.weekDates(w) })), "All 12 weeks")
      : S.mode === "month"
        ? sel("f-month", "month", ["Jul", "Aug", "Sep"].map((m) => ({ v: m, l: m + " 2026" })), "All 3 months")
        : '<input type="date" id="f-from" data-k="from" value="' + S.from + '" min="2026-07-06" max="2026-09-25" aria-label="From">' +
          '<input type="date" id="f-to" data-k="to" value="' + S.to + '" min="2026-07-06" max="2026-09-25" aria-label="To">';

    const primary =
      '<div class="fg"><label>Period</label><div class="seg" role="group" aria-label="Period granularity">' +
        ["week", "month", "custom"].map((m) =>
          '<button type="button" data-mode="' + m + '" aria-pressed="' + (S.mode === m) + '">' +
          NV.titleCase(m) + "</button>").join("") + "</div></div>" +
      '<div class="fg"><label for="f-week">' + (S.mode === "custom" ? "Date range" : S.mode === "month" ? "Month" : "Week") + "</label>" +
        '<div class="row" style="gap:6px">' + periodCtl + "</div></div>" +
      fg("Compare", "f-cmp", sel("f-cmp", "compare", [{ v: "prev", l: "Previous period" }, { v: "none", l: "No comparison" }], "Previous period")) +
      fg("Region", "f-region", sel("f-region", "region", uniq(D.employers.map((e) => e.region)), "All 6 regions")) +
      fg("Broker", "f-broker", sel("f-broker", "broker", D.brokers.map((b) => ({ v: b.id, l: b.agency })), "All 30 brokers")) +
      fg("Employer", "f-employer", sel("f-employer", "employer", NV.employersInScope().map((e) => ({ v: e.id, l: e.name })), "All 95 employers")) +
      fg("Risk band", "f-band", sel("f-band", "band", ["High", "Elevated", "Watch", "None"], "Any band")) +
      '<button type="button" class="btn ghost" id="f-reset">Reset all</button>';

    const advanced =
      fg("Category", "f-cat", sel("f-cat", "category", uniq(D.calls.map((c) => c.category)), "Any category")) +
      fg("Product line", "f-line", sel("f-line", "line", uniq(D.calls.map((c) => c.product_line)), "Any line")) +
      fg("Touchpoint", "f-tp", sel("f-tp", "touchpoint", uniq(D.calls.map((c) => c.touchpoint)), "Any touchpoint")) +
      fg("Outcome", "f-out", sel("f-out", "outcome", ["RESOLVED", "PARTIALLY RESOLVED", "ESCALATED", "UNRESOLVED"], "Any outcome")) +
      fg("Call quality", "f-qual", sel("f-qual", "quality",
        NV.QUALITY_BANDS.map(([k, , label, range]) => ({ v: k, l: label + " · " + range })),
        "Any quality band")) +
      fg("Handling", "f-arch", sel("f-arch", "archetype",
        NV.ARCHETYPES.map(([n]) => n), "Any handling")) +
      fg("Signal", "f-sig", sel("f-sig", "signal", uniq(D.calls.flatMap((c) => c.signals.map((s) => s.code))), "Any signal")) +
      fg("Escalation", "f-esc", sel("f-esc", "esc", [{ v: "triggered", l: "Triggered" }, { v: "handled", l: "Handled" }, { v: "missed", l: "Triggered, not handled" }, { v: "requested", l: "Caller asked" }], "Any escalation state")) +
      fg("Repeat contact", "f-rep", sel("f-rep", "repeat", [{ v: "yes", l: "Repeat only" }, { v: "no", l: "First contact only" }], "Any")) +
      fg("Compliance", "f-comp", sel("f-comp", "compliance", [{ v: "yes", l: "Control exception raised" }], "Any")) +
      fg("Member effort · derived", "f-eff", sel("f-eff", "effort", ["High", "Medium", "Low"], "Any effort")) +
      fg("Complexity · derived", "f-cx", sel("f-cx", "complexity", ["High", "Medium", "Low"], "Any complexity")) +
      fg("Caller type", "f-ct", sel("f-ct", "callerType", ["MEMBER", "EMPLOYER"], "Member and employer")) +
      fg("Intent", "f-int", sel("f-int", "intent", ["expansion", "market_test", "cancellation"], "Any intent")) +
      fg("Complaint against", "f-cmpl", sel("f-cmpl", "complaint", ["CHOICE", "BROKER", "CARRIER", "PROVIDER"], "Any target")) +
      fg("Agent", "f-agent", sel("f-agent", "agent", Object.values(D.agents).map((a) => ({ v: a.id, l: a.name + " · " + a.band })), "All 20 agents"));

    if (compact) {
      /* The board view takes period and region only. Everything else is detail
         that belongs on the pages built for it. */
      return '<div class="filters">' +
        '<div class="fg"><label>Period</label><div class="seg" role="group" aria-label="Period granularity">' +
        ["week", "month", "custom"].map((m) =>
          '<button type="button" data-mode="' + m + '" aria-pressed="' + (S.mode === m) + '">' +
          NV.titleCase(m) + "</button>").join("") + "</div></div>" +
        '<div class="fg"><label for="f-week">' +
        (S.mode === "custom" ? "Date range" : S.mode === "month" ? "Month" : "Week") + "</label>" +
        '<div class="row" style="gap:6px">' + periodCtl + "</div></div>" +
        fg("Region", "f-region", sel("f-region", "region",
          uniq(D.employers.map((e) => e.region)), "All 6 regions")) +
        '<button type="button" class="btn ghost" id="f-reset">Reset</button>' +
        "</div>" + NV.appliedBar();
    }

    return '<div class="filters">' + primary + "</div>" +
      '<details class="adv"' + (NV.advOpen ? " open" : "") + "><summary>Advanced filters · call intelligence</summary>" +
      '<div class="filters">' + advanced + "</div>" +
      '<p class="note" style="margin-top:10px">Sentiment, call complexity as scored, and a sensitive-content flag are <b>not fields in the v9 tag schema</b>. ' +
      "Member effort and complexity above are <b>derived</b> from talk time, turn count, repeat contact, escalation and outcome — they are our composites, not corpus values.</p>" +
      "</details>" + NV.appliedBar();
  };

  const LABELS = {
    region: "Region", broker: "Broker", employer: "Employer", band: "Risk band",
    category: "Category", line: "Line", touchpoint: "Touchpoint", outcome: "Outcome",
    signal: "Signal", agent: "Agent", callerType: "Caller", effort: "Effort",
    complexity: "Complexity", esc: "Escalation", repeat: "Repeat", compliance: "Compliance",
    intent: "Intent", complaint: "Complaint vs", actionStatus: "Action status",
  };
  NV.appliedBar = () => {
    const chips = Object.keys(LABELS).filter((k) => S[k]).map((k) => {
      let v = S[k];
      if (k === "broker") v = NV.brk(v).agency;
      if (k === "employer") v = NV.emp(v).name;
      if (k === "agent") v = (D.agents[v] || {}).name || v;
      return '<span class="chipf">' + LABELS[k] + ": " + NV.esc(NV.titleCase(v)) +
        '<button type="button" data-clear="' + k + '" aria-label="Remove filter">×</button></span>';
    });
    const w = NV.activeWeeks();
    const scope = '<span class="chipf" style="background:var(--surface-2);color:var(--ink-2)">' +
      (w.length === 12 ? "Full 12 weeks" : w.length === 1 ? NV.weekLabel(w[0]) + " · " + NV.weekDates(w[0]) : w.length + " weeks") +
      " · " + NV.calls().length + " calls</span>";
    return '<div class="appliedbar">' + scope + chips.join("") +
      (chips.length ? '<button type="button" class="btn ghost" id="f-reset2">Clear filters</button>' : "") +
      '<button type="button" class="btn ghost" id="f-copy">Copy link to this view</button></div>';
  };

  /* Clipboard access can be refused; show the URL so it can still be copied. */
  function showUrl(url) {
    NV.drawer("Link to this view",
      '<p class="sub" style="margin:0">Every filter on screen is in this address, so it opens ' +
      "on the same figures for whoever you send it to.</p>" +
      '<input id="nv-url" readonly value="' + NV.esc(url) +
      '" style="width:100%;font-family:var(--mono);font-size:11.5px;padding:8px;' +
      'border:1px solid var(--rule-strong);border-radius:6px;background:var(--surface-2);' +
      'color:var(--ink)">', null,
      (dlg) => {
        const i = dlg.querySelector("#nv-url");
        if (i) { i.focus(); i.select(); }
      });
  }

  NV.bindFilters = (root) => {
    root.querySelectorAll("select[data-k], input[data-k]").forEach((el) => {
      el.addEventListener("change", () => NV.set(el.dataset.k, el.value));
    });
    root.querySelectorAll("[data-mode]").forEach((b) => {
      b.addEventListener("click", () => NV.set("mode", b.dataset.mode));
    });
    root.querySelectorAll("[data-clear]").forEach((b) => {
      b.addEventListener("click", () => NV.set(b.dataset.clear, ""));
    });
    const r1 = root.querySelector("#f-reset"), r2 = root.querySelector("#f-reset2");
    if (r1) r1.addEventListener("click", NV.reset);
    if (r2) r2.addEventListener("click", NV.reset);
    const copy = root.querySelector("#f-copy");
    if (copy) {
      copy.addEventListener("click", () => {
        const url = window.location.href;
        const done = () => {
          copy.textContent = "Link copied";
          setTimeout(() => { copy.textContent = "Copy link to this view"; }, 1800);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(url).then(done, () => showUrl(url));
        } else {
          showUrl(url);
        }
      });
    }
    const adv = root.querySelector("details.adv");
    if (adv) adv.addEventListener("toggle", () => { NV.advOpen = adv.open; });
  };

  /* ---------------- tooltip ---------------- */
  const tip = document.createElement("div");
  tip.className = "tip"; tip.setAttribute("role", "status");
  document.addEventListener("DOMContentLoaded", () => document.body.appendChild(tip));
  NV.showTip = (evt, html) => {
    tip.innerHTML = html;
    tip.style.opacity = "1";
    const r = tip.getBoundingClientRect();
    let x = evt.clientX + 14, y = evt.clientY + 14;
    if (x + r.width > window.innerWidth - 8) x = evt.clientX - r.width - 14;
    if (y + r.height > window.innerHeight - 8) y = evt.clientY - r.height - 14;
    tip.style.left = Math.max(8, x) + "px";
    tip.style.top = Math.max(8, y) + "px";
  };
  NV.hideTip = () => { tip.style.opacity = "0"; };


  /* ---------------- ink on a coloured fill ----------------
     The sequential ramp is inverted between themes: on light it runs
     light->dark, and on a dark surface "near zero" has to recede toward the
     surface, so it runs dark->light. That means the strongest heat cell is the
     darkest swatch in light mode and the lightest one in dark mode, and a
     hardcoded white numeral is unreadable in one of the two. Resolve the token
     and pick the ink by luminance instead, so all three theme states are handled
     and a retuned token cannot silently break the label. */
  const inkCache = {};
  function luminance(r, g, b) {
    const f = (c) => {
      c /= 255;
      return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  }
  NV.inkOn = (cssVar) => {
    if (inkCache[cssVar]) return inkCache[cssVar];
    let ink = "var(--ink)";
    try {
      const raw = getComputedStyle(document.documentElement)
        .getPropertyValue(cssVar.replace(/^var\(|\)$/g, "")).trim();
      let rgb = null;
      let m = raw.match(/^#([0-9a-f]{6})$/i);
      if (m) {
        rgb = [parseInt(m[1].slice(0, 2), 16), parseInt(m[1].slice(2, 4), 16),
               parseInt(m[1].slice(4, 6), 16)];
      } else {
        m = raw.match(/rgba?\(([^)]+)\)/);
        if (m) rgb = m[1].split(",").slice(0, 3).map((n) => parseFloat(n));
      }
      /* 0.179 is where white and near-black contrast equally against a
         fill; above it near-black wins, below it white does. */
      if (rgb) ink = luminance(rgb[0], rgb[1], rgb[2]) > 0.179 ? "#0b0b0b" : "#ffffff";
    } catch (e) { /* fall back to theme ink */ }
    inkCache[cssVar] = ink;
    return ink;
  };
  NV.clearInkCache = () => { Object.keys(inkCache).forEach((k) => delete inkCache[k]); };

  /* ---------------- charts (hand-rolled SVG, one scale per chart) ---------------- */
  const SVGNS = "http://www.w3.org/2000/svg";
  function svg(tag, attrs) {
    const el = document.createElementNS(SVGNS, tag);
    for (const k in attrs) if (attrs[k] !== null && attrs[k] !== undefined) el.setAttribute(k, attrs[k]);
    return el;
  }
  function niceMax(v) {
    if (v <= 4) return Math.max(v, 1);
    const p = Math.pow(10, Math.floor(Math.log10(v)));
    return Math.ceil(v / (p / 2)) * (p / 2);
  }

  /* line chart with crosshair; series = [{name,color,values}] */
  NV.chart = {
    line(host, cfg) {
      const W = 720, H = cfg.height || 200, P = { t: 14, r: 46, b: 26, l: 34 };
      const labels = cfg.labels, n = labels.length;
      const all = cfg.series.flatMap((s) => s.values.filter((v) => v !== null));
      const max = niceMax(Math.max.apply(null, all.concat([1])));
      const x = (i) => P.l + (n === 1 ? 0 : i * (W - P.l - P.r) / (n - 1));
      const y = (v) => H - P.b - (v / max) * (H - P.t - P.b);
      const s = svg("svg", { class: "chart", viewBox: "0 0 " + W + " " + H, role: "img",
        "aria-label": cfg.aria || cfg.title || "trend chart" });

      [0, 0.5, 1].forEach((f) => {
        const v = max * f;
        s.appendChild(svg("line", { class: f === 0 ? "baseline" : "gridline",
          x1: P.l, x2: W - P.r, y1: y(v), y2: y(v) }));
        const t = svg("text", { class: "tick", x: P.l - 7, y: y(v) + 3.5, "text-anchor": "end" });
        t.textContent = Math.round(v); s.appendChild(t);
      });
      labels.forEach((l, i) => {
        if (n > 8 && i % 2) return;
        const t = svg("text", { class: "tick", x: x(i), y: H - P.b + 14, "text-anchor": "middle" });
        t.textContent = l; s.appendChild(t);
      });

      cfg.series.forEach((ser) => {
        const pts = ser.values.map((v, i) => (v === null ? null : [x(i), y(v)])).filter(Boolean);
        if (cfg.area && pts.length) {
          const dd = "M" + pts.map((p) => p[0] + "," + p[1]).join("L") +
            "L" + pts[pts.length - 1][0] + "," + y(0) + "L" + pts[0][0] + "," + y(0) + "Z";
          s.appendChild(svg("path", { d: dd, fill: ser.color, opacity: ".10", stroke: "none" }));
        }
        s.appendChild(svg("path", { d: "M" + pts.map((p) => p[0] + "," + p[1]).join("L"),
          fill: "none", stroke: ser.color, "stroke-width": 2, "stroke-linejoin": "round" }));
        const last = pts[pts.length - 1];
        if (last) {
          s.appendChild(svg("circle", { cx: last[0], cy: last[1], r: 4.5, fill: ser.color,
            stroke: "var(--surface)", "stroke-width": 2 }));
          const t = svg("text", { class: "dlabel", x: last[0] + 9, y: last[1] + 4 });
          t.textContent = ser.values[ser.values.length - 1]; s.appendChild(t);
        }
      });

      const hit = svg("rect", { x: P.l, y: P.t, width: W - P.l - P.r, height: H - P.t - P.b,
        fill: "transparent", style: "cursor:crosshair" });
      const cross = svg("line", { class: "baseline", y1: P.t, y2: H - P.b, opacity: 0 });
      s.appendChild(cross); s.appendChild(hit);
      hit.addEventListener("mousemove", (e) => {
        const box = s.getBoundingClientRect();
        const rel = (e.clientX - box.left) / box.width * W;
        let i = Math.round((rel - P.l) / ((W - P.l - P.r) / Math.max(n - 1, 1)));
        i = Math.max(0, Math.min(n - 1, i));
        cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i)); cross.setAttribute("opacity", ".6");
        NV.showTip(e, "<b>" + NV.esc(cfg.tipTitle ? cfg.tipTitle(i) : labels[i]) + "</b><dl>" +
          cfg.series.map((ser) => "<dt>" + NV.esc(ser.name) + "</dt><dd>" +
            (ser.values[i] === null ? "–" : ser.values[i]) + (ser.suffix || "") + "</dd>").join("") +
          "</dl>");
      });
      hit.addEventListener("mouseleave", () => { cross.setAttribute("opacity", 0); NV.hideTip(); });
      host.innerHTML = ""; host.appendChild(s);
      if (cfg.series.length > 1) {
        const lg = document.createElement("div");
        lg.className = "legend";
        lg.innerHTML = cfg.series.map((ser) => '<span><i style="background:' + ser.color + '"></i>' +
          NV.esc(ser.name) + "</span>").join("");
        host.appendChild(lg);
      }
    },

    /* horizontal bars with direct value labels */
    bars(host, cfg) {
      const rows = cfg.rows, rh = cfg.rowHeight || 26;
      const W = 720, H = rows.length * rh + 8, L = cfg.labelWidth || 210;
      const max = niceMax(Math.max.apply(null, rows.map((r) => r.value).concat([1])));
      const s = svg("svg", { class: "chart", viewBox: "0 0 " + W + " " + H, role: "img",
        "aria-label": cfg.aria || "bar chart" });
      rows.forEach((r, i) => {
        const yy = i * rh + 4, bw = Math.max((r.value / max) * (W - L - 54), r.value > 0 ? 2 : 0);
        const lab = svg("text", { class: "tick", x: 0, y: yy + rh / 2 + 3, fill: "var(--ink-2)" });
        lab.setAttribute("style", "font-size:11.5px");
        lab.textContent = r.label.length > 34 ? r.label.slice(0, 33) + "…" : r.label;
        s.appendChild(lab);
        const g = svg("g", { style: "cursor:pointer" });
        g.appendChild(svg("rect", { x: L, y: yy + 4, width: Math.max(bw, 2), height: rh - 12,
          rx: 4, fill: r.color || "var(--seq-2)" }));
        const v = svg("text", { class: "dlabel", x: L + Math.max(bw, 2) + 7, y: yy + rh / 2 + 3.5 });
        v.textContent = r.display !== undefined ? r.display : r.value;
        g.appendChild(v);
        g.appendChild(svg("rect", { x: 0, y: yy, width: W, height: rh, fill: "transparent" }));
        g.addEventListener("mousemove", (e) => NV.showTip(e, r.tip || ("<b>" + NV.esc(r.label) + "</b>")));
        g.addEventListener("mouseleave", NV.hideTip);
        if (r.onClick) g.addEventListener("click", r.onClick);
        s.appendChild(g);
      });
      host.innerHTML = ""; host.appendChild(s);
    },

    /* grouped bars across ordered time buckets (sequential ramp = order) */
    grouped(host, cfg) {
      const rows = cfg.rows, buckets = cfg.buckets, rh = 30;
      const W = 720, H = rows.length * rh + 26, L = cfg.labelWidth || 200;
      const max = niceMax(Math.max.apply(null, rows.flatMap((r) => r.values).concat([1])));
      const colors = ["var(--seq-1)", "var(--seq-2)", "var(--seq-3)"];
      const s = svg("svg", { class: "chart", viewBox: "0 0 " + W + " " + H, role: "img",
        "aria-label": cfg.aria || "grouped bars by period" });
      const barW = (rh - 12) / buckets.length;
      rows.forEach((r, i) => {
        const yy = i * rh + 4;
        const lab = svg("text", { class: "tick", x: 0, y: yy + rh / 2 + 3, fill: "var(--ink-2)" });
        lab.setAttribute("style", "font-size:11.5px");
        lab.textContent = r.label.length > 32 ? r.label.slice(0, 31) + "…" : r.label;
        s.appendChild(lab);
        r.values.forEach((v, bi) => {
          const bw = (v / max) * (W - L - 66);
          s.appendChild(svg("rect", { x: L, y: yy + 3 + bi * (barW + 2), width: Math.max(bw, v > 0 ? 2 : 0),
            height: barW, rx: 2, fill: colors[bi] }));
        });
        const tot = svg("text", { class: "dlabel", x: W - 54, y: yy + rh / 2 + 3.5 });
        tot.textContent = r.values.join(" → ");
        s.appendChild(tot);
        const hit = svg("rect", { x: 0, y: yy, width: W, height: rh, fill: "transparent" });
        hit.addEventListener("mousemove", (e) => NV.showTip(e, "<b>" + NV.esc(r.label) + "</b><dl>" +
          buckets.map((b, bi) => "<dt>" + b + "</dt><dd>" + r.values[bi] + "</dd>").join("") + "</dl>" +
          (r.note ? '<div style="margin-top:6px;color:var(--ink-2)">' + NV.esc(r.note) + "</div>" : "")));
        hit.addEventListener("mouseleave", NV.hideTip);
        s.appendChild(hit);
      });
      const lg = buckets.map((b, i) => '<span><i style="background:' + colors[i] + '"></i>' + b + "</span>").join("");
      host.innerHTML = "";
      host.appendChild(s);
      const l = document.createElement("div"); l.className = "legend"; l.innerHTML = lg;
      host.appendChild(l);
    },

    /* stacked composition bar, one row, direct labels + legend */
    stacked(host, cfg) {
      const total = cfg.parts.reduce((a, p) => a + p.value, 0) || 1;
      const W = 720, H = 46;
      const s = svg("svg", { class: "chart", viewBox: "0 0 " + W + " " + H, role: "img",
        "aria-label": cfg.aria || "composition" });
      let xx = 0;
      cfg.parts.forEach((p) => {
        const w = (p.value / total) * W;
        if (w <= 0) return;
        const g = svg("g", { style: "cursor:pointer" });
        g.appendChild(svg("rect", { x: xx, y: 0, width: Math.max(w - 2, 1), height: 22, rx: 3, fill: p.color }));
        if (w > 44) {
          const t = svg("text", { class: "dlabel", x: xx + 4, y: 37 });
          t.textContent = p.value + " · " + Math.round(p.value / total * 100) + "%";
          s.appendChild(t);
        }
        g.addEventListener("mousemove", (e) => NV.showTip(e, "<b>" + NV.esc(p.name) + "</b><dl><dt>Calls</dt><dd>" +
          p.value + "</dd><dt>Share</dt><dd>" + Math.round(p.value / total * 100) + "%</dd></dl>"));
        g.addEventListener("mouseleave", NV.hideTip);
        if (p.onClick) g.addEventListener("click", p.onClick);
        s.appendChild(g);
        xx += w;
      });
      host.innerHTML = ""; host.appendChild(s);
      /* The legend carries the value as well as the name. Two of the four series
         colours sit below 3:1 on the light surface, so the palette requires
         visible labels as relief -- and the in-bar label is dropped when a
         segment is too narrow to hold it, which is exactly when a reader would
         be left with colour alone. */
      const l = document.createElement("div"); l.className = "legend";
      l.innerHTML = cfg.parts.map((p) => '<span><i style="background:' + p.color + '"></i>' +
        NV.esc(p.name) + ' <b style="font-variant-numeric:tabular-nums">' + p.value +
        "</b> · " + Math.round(p.value / total * 100) + "%</span>").join("");
      host.appendChild(l);
    },

    /* sparkline, no axes - used inside table rows */
    spark(values, color) {
      const W = 70, H = 20, max = Math.max.apply(null, values.concat([1]));
      const pts = values.map((v, i) => [2 + i * (W - 4) / Math.max(values.length - 1, 1),
        H - 3 - (v / max) * (H - 7)]);
      return '<svg viewBox="0 0 ' + W + " " + H + '" width="' + W + '" height="' + H +
        '" aria-hidden="true" style="display:block"><path d="M' +
        pts.map((p) => p[0].toFixed(1) + "," + p[1].toFixed(1)).join("L") +
        '" fill="none" stroke="' + (color || "var(--seq-2)") + '" stroke-width="1.5"/>' +
        '<circle cx="' + pts[pts.length - 1][0].toFixed(1) + '" cy="' +
        pts[pts.length - 1][1].toFixed(1) + '" r="2.2" fill="' + (color || "var(--seq-2)") + '"/></svg>';
    },
  };

  /* ---------------- drawer ----------------
     Kept as a stack. Drilling from a list into one of its rows opens a second
     drawer, and Back returns to the list it came from. Two things matter here:
     showModal() throws if the dialog is already open, so it is only called when
     the dialog is closed; and replacing the contents discards the previous
     frame's event handlers, so each frame carries the function that re-binds
     them. */
  const frames = [];

  function paintDrawer() {
    const dlg = document.getElementById("nv-drawer");
    const f = frames[frames.length - 1];
    if (!f) return;
    dlg.innerHTML = '<div class="dh"><div><h3>' + f.title + "</h3></div>" +
      (f.chip ? NV.clsChip(f.chip) : "") +
      '<div class="row" style="gap:6px">' +
      (frames.length > 1 ? '<button class="btn" type="button" id="nv-dback">← Back</button>' : "") +
      '<button class="btn" type="button" id="nv-dclose">Close</button></div></div>' +
      '<div class="db">' + f.html + "</div>";
    dlg.querySelector("#nv-dclose").addEventListener("click", () => {
      frames.length = 0;
      dlg.close();
    });
    const back = dlg.querySelector("#nv-dback");
    if (back) {
      back.addEventListener("click", () => { frames.pop(); paintDrawer(); });
    }
    if (f.rewire) f.rewire(dlg);
    NV.wireKeyboard(dlg);
  }

  NV.drawer = (title, bodyHtml, chipKind, rewire) => {
    let dlg = document.getElementById("nv-drawer");
    if (!dlg) {
      dlg = document.createElement("dialog");
      dlg.id = "nv-drawer";
      dlg.className = "drawer";
      dlg.addEventListener("close", () => { frames.length = 0; });
      document.body.appendChild(dlg);
    }
    frames.push({ title: title, html: bodyHtml, chip: chipKind, rewire: rewire });
    paintDrawer();
    if (!dlg.open) dlg.showModal();
  };

  /* call evidence renderer, shared by every prototype */
  NV.callEvidence = (id) => {
    const c = NV.call(id);
    if (!c) return "<p>Call not found.</p>";
    const e = NV.emp(c.employer);
    const turns = (D.snippets[id] || []);
    const keyTurn = (c.intent[0] && c.intent[0].turn) || null;
    const shown = keyTurn ? turns.slice(Math.max(0, keyTurn - 2), keyTurn + 1) : turns.slice(0, 3);
    const rows = [
      ["Employer", e.name + " · " + (e.region || "")],
      ["Broker", NV.brk(e.broker).agency],
      ["Caller", c.caller_name + " · " + c.caller_type.toLowerCase() + (c.authority ? " · " + c.authority : "")],
      ["Agent", c.agent_name + " · " + c.agent],
      ["Category", c.category + " · " + c.product_line],
      ["Touchpoint", c.touchpoint ? NV.titleCase(c.touchpoint) : "none — no upstream artefact at fault"],
      ["Outcome", c.outcome],
      ["Quality score", c.score + "/100"],
      ["Talk time", NV.mmss(c.aht) + " · " + c.turns + " turns"],
      ["Member effort", c.effort + "/100 (" + c.effort_band + ")"],
    ];
    return '<div><h4>Call ' + c.id + " · " + c.date + "</h4><dl style='display:grid;grid-template-columns:auto 1fr;gap:4px 14px;font-size:12.5px;margin:0'>" +
      rows.map((r) => "<dt style='color:var(--ink-2)'>" + r[0] + "</dt><dd style='margin:0'>" + NV.esc(r[1]) + "</dd>").join("") + "</dl></div>" +
      (c.signals.length ? "<div><h4>Signals raised " + NV.clsChip("observed") + "</h4>" +
        c.signals.map((s) => '<div class="row" style="justify-content:space-between"><span>' +
          NV.titleCase(s.code) + '</span><span class="sev sev-' + s.severity + '">' + s.severity +
          " · " + NV.esc(s.owner) + "</span></div>").join("") + "</div>" : "") +
      /* The rules a call turns on, quoted from the rulebook rather than left as
         bare ids - the id alone tells the reader nothing about what was asked. */
      ((c.rule_refs && c.rule_refs.length) ? "<div><h4>Rules in play " +
        NV.clsChip("reference") + "</h4>" + c.rule_refs.map((id) => {
          const r = (D.rules || {})[id];
          return '<div style="padding:4px 0;border-bottom:1px solid var(--rule)">' +
            '<b class="mono">' + NV.esc(id) + "</b>" +
            (r ? ' <span class="sm">' + NV.esc(r.area || "") + "</span>" +
              '<div class="sm" style="margin-top:2px">' + NV.esc(r.rule || "") + "</div>" : "") +
            "</div>";
        }).join("") + "</div>" : "") +
      (c.kf_present ? "<div><h4>Knowledge failure</h4><p style='margin:0;font-size:12.5px'>Rule <b>" +
        c.kf_rule + "</b> — " + NV.esc(c.kf_statement) + "</p>" +
        ((D.rules || {})[c.kf_rule] ? "<p class='sm' style='margin:6px 0 0'>Published: " +
          NV.esc(D.rules[c.kf_rule].rule) + "</p>" : "") + "</div>" : "") +
      (c.pg_present ? "<div><h4>Process gap proposed</h4><p style='margin:0;font-size:12.5px'>" +
        NV.esc(c.pg_change) + " <span class='sm'>(" + NV.titleCase(c.pg_touchpoint) + " · raised by " +
        c.pg_raised_by.toLowerCase() + " · " + c.pg_status + ")</span></p></div>" : "") +
      (c.control_exceptions.length ? "<div><h4>Control exceptions</h4><p style='margin:0;font-size:12.5px'>" +
        c.control_exceptions.map(NV.titleCase).join(", ") + "</p></div>" : "") +
      "<div><h4>Transcript evidence</h4>" + shown.map((t) =>
        '<p class="quote" style="margin-bottom:8px">' + NV.esc(t.text) +
        "<cite>" + NV.esc(t.who) + " · " + c.id + "</cite></p>").join("") +
      "<p class='sm'>" + turns.length + " turns in full transcript.</p></div>";
  };

  NV.openCall = (id) => NV.drawer("Call evidence", NV.callEvidence(id), "observed");
})();
