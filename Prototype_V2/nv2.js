/* NanoVox Account Signals - v2 layer.
   Loaded after ../app.js. Leaves the original behaviour file untouched and
   overrides only what v2 changes:
     - page names in the rail (questions, not module names)
     - a leaner filter bar (no scope line, no copy link, Advanced next to Reset)
     - shared building blocks: tooltip, tiles, clickable "act" numbers,
       AI insight strip and feed
     - the playbooks behind every red or orange number (NV.PLAYBOOK)
   Everything computed stays in code. The only generated text is the AI insight
   copy, which is templated over computed figures here and marked where a model
   call would plug in. */
(function () {
  const NV = window.NV, D = NV.D, S = NV.S;

  /* ---------------- rail ---------------- */
  const PAGES = [
    ["exec.html", "Executive overview", "The period at a glance"],
    ["index.html", "What are the risks?", "Accounts, drivers, signals"],
    ["employer.html", "Insights & patterns around employers", "One account at a time"],
    ["actions.html", "What should we do next?", "Steps, owners, progress"],
    ["hierarchy.html", "Isolated or systemic?", "Region, broker, account"],
    ["agents.html", "How are agents handling calls?", "Conduct events"],
    ["calls.html", "All calls", "Browse, filter, export"],
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
      '<span class="footnote">Batch 1 · ' + D.kpis.calls_written + " of " +
      D.kpis.calls_planned + " calls<br>6 Jul – 25 Sep 2026</span></div></aside>";
  };

  /* ---------------- filter bar ---------------- */
  const uniq = (arr) => Array.from(new Set(arr.filter(Boolean))).sort();
  const opts = (list, cur, anyLabel) =>
    '<option value="">' + anyLabel + "</option>" +
    list.map((o) => {
      const v = typeof o === "string" ? o : o.v, l = typeof o === "string" ? NV.titleCase(o) : o.l;
      return '<option value="' + NV.esc(v) + '"' + (cur === v ? " selected" : "") + ">" +
        NV.esc(l) + "</option>";
    }).join("");
  const fg = (label, id, html) =>
    '<div class="fg"><label for="' + id + '">' + label + "</label>" + html + "</div>";
  const sel = (id, key, list, anyLabel) =>
    '<select id="' + id + '" data-k="' + key + '">' + opts(list, S[key], anyLabel) + "</select>";

  const ADV_KEYS = ["category", "line", "touchpoint", "outcome", "quality", "archetype", "signal",
    "esc", "repeat", "compliance", "effort", "complexity", "callerType", "intent", "complaint", "agent"];

  NV.filterBar = (o) => {
    const compact = !!(o && o.compact);
    const period =
      '<div class="fg"><label>Period</label><div class="seg" role="group" aria-label="Period granularity">' +
      ["week", "month", "custom"].map((m) =>
        '<button type="button" data-mode="' + m + '" aria-pressed="' + (S.mode === m) + '">' +
        NV.titleCase(m) + "</button>").join("") + "</div></div>" +
      '<div class="fg"><label for="f-week">' +
      (S.mode === "custom" ? "Date range" : S.mode === "month" ? "Month" : "Week") + "</label>" +
      '<div class="row" style="gap:6px">' + (S.mode === "week"
        ? sel("f-week", "week", D.weeks.map((w) => ({ v: "" + w, l: "Wk " + w + " · " + NV.weekDates(w) })), "All 12 weeks")
        : S.mode === "month"
          ? sel("f-month", "month", ["Jul", "Aug", "Sep"].map((m) => ({ v: m, l: m + " 2026" })), "All 3 months")
          : '<input type="date" id="f-from" data-k="from" value="' + S.from + '" min="2026-07-06" max="2026-09-25" aria-label="From">' +
            '<input type="date" id="f-to" data-k="to" value="' + S.to + '" min="2026-07-06" max="2026-09-25" aria-label="To">') +
      "</div></div>";
    const region = fg("Region", "f-region", sel("f-region", "region", uniq(D.employers.map((e) => e.region)), "All 6 regions"));

    if (compact) {
      return '<div class="filters">' + period + region +
        '<div class="fbtns"><button type="button" class="btn ghost" id="f-reset">Reset all</button></div></div>' +
        NV.appliedBar();
    }

    const nAdv = ADV_KEYS.filter((k) => S[k]).length;
    const primary = period + region +
      fg("Broker", "f-broker", sel("f-broker", "broker", D.brokers.map((b) => ({ v: b.id, l: b.agency })), "All 30 brokers")) +
      fg("Employer", "f-employer", sel("f-employer", "employer",
        D.employers.slice().sort((a, b) => a.name.localeCompare(b.name)).map((e) => ({ v: e.id, l: e.name })), "All 95 employers")) +
      fg("Risk band", "f-band", sel("f-band", "band", ["High", "Elevated", "Watch", "None"], "Any band")) +
      '<div class="fbtns"><button type="button" class="btn ghost" id="f-reset">Reset all</button>' +
      '<button type="button" class="btn advbtn" id="f-adv" aria-expanded="' + !!NV.advOpen + '">' +
      "Advanced filters" + (nAdv ? ' <span class="advn">' + nAdv + "</span>" : "") +
      ' <span aria-hidden="true">' + (NV.advOpen ? "▴" : "▾") + "</span></button></div>";

    const advanced =
      fg("Category", "f-cat", sel("f-cat", "category", uniq(D.calls.map((c) => c.category)), "Any category")) +
      fg("Product line", "f-line", sel("f-line", "line", uniq(D.calls.map((c) => c.product_line)), "Any line")) +
      fg("Touchpoint", "f-tp", sel("f-tp", "touchpoint", uniq(D.calls.map((c) => c.touchpoint)), "Any touchpoint")) +
      fg("Outcome", "f-out", sel("f-out", "outcome", ["RESOLVED", "PARTIALLY RESOLVED", "ESCALATED", "UNRESOLVED"], "Any outcome")) +
      fg("Call quality", "f-qual", sel("f-qual", "quality",
        NV.QUALITY_BANDS.map(([k, , label, range]) => ({ v: k, l: label + " · " + range })), "Any quality")) +
      fg("Handling", "f-arch", sel("f-arch", "archetype", NV.ARCHETYPES.map(([n]) => n), "Any handling")) +
      fg("Signal", "f-sig", sel("f-sig", "signal", uniq(D.calls.flatMap((c) => c.signals.map((s) => s.code))), "Any signal")) +
      fg("Escalation", "f-esc", sel("f-esc", "esc", [{ v: "triggered", l: "Warranted" }, { v: "handled", l: "Handled" },
        { v: "missed", l: "Warranted, not handled" }, { v: "requested", l: "Caller asked" }], "Any")) +
      fg("Repeat contact", "f-rep", sel("f-rep", "repeat", [{ v: "yes", l: "Repeat only" }, { v: "no", l: "First contact only" }], "Any")) +
      fg("Compliance", "f-comp", sel("f-comp", "compliance", [{ v: "yes", l: "Exception raised" }], "Any")) +
      fg("Member effort", "f-eff", sel("f-eff", "effort", ["High", "Medium", "Low"], "Any")) +
      fg("Complexity", "f-cx", sel("f-cx", "complexity", ["High", "Medium", "Low"], "Any")) +
      fg("Caller", "f-ct", sel("f-ct", "callerType", ["MEMBER", "EMPLOYER"], "Member and employer")) +
      fg("Intent", "f-int", sel("f-int", "intent", ["expansion", "market_test", "cancellation"], "Any intent")) +
      fg("Complaint against", "f-cmpl", sel("f-cmpl", "complaint", ["CHOICE", "BROKER", "CARRIER", "PROVIDER"], "Any")) +
      fg("Agent", "f-agent", sel("f-agent", "agent", Object.values(D.agents).map((a) => ({ v: a.id, l: a.name })), "All 20 agents"));

    return '<div class="filters">' + primary + "</div>" +
      '<div class="advpanel"' + (NV.advOpen ? "" : " hidden") + '><div class="filters">' + advanced + "</div></div>" +
      NV.appliedBar();
  };

  const LABELS = {
    region: "Region", broker: "Broker", employer: "Employer", band: "Risk band",
    category: "Category", line: "Line", touchpoint: "Touchpoint", outcome: "Outcome",
    quality: "Quality", archetype: "Handling",
    signal: "Signal", agent: "Agent", callerType: "Caller", effort: "Effort",
    complexity: "Complexity", esc: "Escalation", repeat: "Repeat", compliance: "Compliance",
    intent: "Intent", complaint: "Complaint vs", actionStatus: "Action status",
  };
  /* Only the filters someone set, each removable. No scope line, no copy link. */
  NV.appliedBar = () => {
    const chips = Object.keys(LABELS).filter((k) => S[k]).map((k) => {
      let v = S[k];
      if (k === "broker") v = NV.brk(v).agency;
      if (k === "employer") v = NV.emp(v).name;
      if (k === "agent") v = (D.agents[v] || {}).name || v;
      return '<span class="chipf">' + LABELS[k] + ": " + NV.esc(NV.titleCase(v)) +
        '<button type="button" data-clear="' + k + '" aria-label="Remove filter">×</button></span>';
    });
    return chips.length ? '<div class="appliedbar">' + chips.join("") + "</div>" : "";
  };

  const baseBind = NV.bindFilters;
  NV.bindFilters = (root) => {
    baseBind(root);
    const adv = root.querySelector("#f-adv");
    if (adv) adv.addEventListener("click", () => {
      NV.advOpen = !NV.advOpen;
      const p = root.querySelector(".advpanel");
      if (p) p.hidden = !NV.advOpen;
      adv.setAttribute("aria-expanded", NV.advOpen);
      adv.lastElementChild.textContent = NV.advOpen ? "▴" : "▾";
    });
  };

  /* ---------------- small building blocks ---------------- */
  let tipSeq = 0;
  NV.info = (html, cls) => {
    const id = "nvtip" + (++tipSeq);
    return '<span class="info ' + (cls || "") + '"><button type="button" aria-label="What this means" ' +
      'aria-describedby="' + id + '">i</button><span role="tooltip" id="' + id + '">' + html + "</span></span>";
  };

  /* Every epistemic tag explains itself on hover. */
  const CLS_TIP = {
    observed: "<b>Observed.</b> Counted directly from the calls.",
    reference: "<b>Reference.</b> A fact about the account from the workbook, not from a call.",
    derived: "<b>Derived.</b> Calculated by us from observed values. The formula is in the section's (i).",
    pattern: "<b>Pattern.</b> A shape across several calls. No cause is claimed.",
    inference: "<b>Inference.</b> A possible explanation that goes beyond the data. Test it before acting on it.",
    recommendation: "<b>Recommendation.</b> A suggested action based on the evidence, for the owning team to confirm.",
  };
  NV.clsChip = (kind, extra) => {
    const tip = CLS_TIP[kind] || extra;
    const chip = '<span class="cls cls-' + kind + '"' + (tip ? ' tabindex="0"' : "") + ">" + kind + "</span>";
    return tip ? '<span class="info chipinfo right">' + chip + '<span role="tooltip">' + tip +
      (extra && CLS_TIP[kind] ? "<br>" + NV.esc(extra) : "") + "</span></span>" : chip;
  };

  /* Tooltips are positioned in the viewport, so a panel with its own scroll
     (the insight feed, a wide table) can no longer clip them. */
  function placeTip(host) {
    const tip = host.querySelector(':scope > [role="tooltip"]');
    if (!tip) return;
    tip.style.position = "fixed";
    tip.style.display = "block";
    tip.style.left = "0px"; tip.style.top = "0px";
    const r = host.getBoundingClientRect(), tw = tip.offsetWidth, th = tip.offsetHeight;
    let x = host.classList.contains("right") ? r.right - tw + 8 : r.left - 8;
    if (x < 8) x = r.left - 8;                                   // no room on the left: open rightwards
    if (x + tw > window.innerWidth - 8) x = r.right - tw + 8;    // no room on the right: open leftwards
    x = Math.max(8, Math.min(x, window.innerWidth - tw - 8));
    let y = r.bottom + 8;
    if (y + th > window.innerHeight - 8) y = Math.max(8, r.top - th - 8);
    tip.style.left = x + "px"; tip.style.top = y + "px";
  }
  function hideTip(host) {
    const tip = host.querySelector(':scope > [role="tooltip"]');
    if (tip) tip.style.display = "";
  }
  document.addEventListener("mouseover", (e) => {
    const h = e.target.closest && e.target.closest(".info");
    if (h && !h.contains(e.relatedTarget)) placeTip(h);
  });
  document.addEventListener("mouseout", (e) => {
    const h = e.target.closest && e.target.closest(".info");
    if (h && !h.contains(e.relatedTarget)) hideTip(h);
  });
  document.addEventListener("focusin", (e) => { const h = e.target.closest && e.target.closest(".info"); if (h) placeTip(h); });
  document.addEventListener("focusout", (e) => { const h = e.target.closest && e.target.closest(".info"); if (h) hideTip(h); });
  /* On scroll, keep an open tooltip attached to its trigger. */
  window.addEventListener("scroll", () => document.querySelectorAll('.info > [role="tooltip"]').forEach((t) => {
    if (t.style.display === "block") placeTip(t.parentElement);
  }), { passive: true });

  /* The page head is sticky. Tables stick their header row just under it,
     so the column names stay visible while scrolling a long list. */
  function measureHead() {
    const h = document.querySelector(".pagehead");
    if (h) document.documentElement.style.setProperty("--headH", h.offsetHeight + "px");
  }
  window.addEventListener("resize", measureHead);
  window.addEventListener("load", measureHead);
  setTimeout(measureHead, 50);
  NV.measureHead = measureHead;
  let stuck = false;
  window.addEventListener("scroll", () => {
    const h = document.querySelector(".pagehead");
    if (!h) return;
    /* Hysteresis, so a page only just taller than the screen cannot flicker. */
    const s2 = stuck ? window.scrollY > 40 : window.scrollY > 180 &&
      document.documentElement.scrollHeight - window.innerHeight > 420;
    if (s2 !== stuck) { stuck = s2; h.classList.toggle("stuck", s2); measureHead(); }
  }, { passive: true });

  /* A link to the action page, focused on one issue. Every red or orange
     number on every page goes through this, so "what do I do about this?" is
     always one click. `extra` adds query params such as employer=EMP-1004. */
  NV.actHref = (key, extra) => {
    const base = NV.href("actions.html");
    const q = "focus=" + encodeURIComponent(key) +
      (extra ? "&" + Object.keys(extra).map((k) => k + "=" + encodeURIComponent(extra[k])).join("&") : "");
    return base + (base.indexOf("?") === -1 ? "?" : "&") + q;
  };
  NV.act = (key, inner, tone, extra) =>
    '<a class="act ' + (tone || "hot") + '" href="' + NV.actHref(key, extra) + '" title="What to do about this">' +
    inner + "</a>";

  /* Tile. `tone` hot|warm|withheld|""; `focus` makes the value a link to the
     action page and shows the "What to do" cue. */
  NV.tile = (o) => {
    const v = o.focus ? NV.act(o.focus, o.v, o.tone || "hot", o.extra) : o.v;
    return '<div class="big ' + (o.tone || "") + '"><span class="k">' + o.k +
      (o.tip ? NV.info(o.tip) : "") + '</span><span class="v">' + v +
      '</span><span class="m">' + o.m + "</span>" +
      (o.focus ? '<a class="todo" href="' + NV.actHref(o.focus, o.extra) + '">What to do →</a>' : "") + "</div>";
  };
  NV.tiles = (arr) => '<div class="bigrow">' + arr.map(NV.tile).join("") + "</div>";

  /* The footer source line used to sit under every page. Nobody reads it
     there, so it moves into the title's tooltip as "About this data". */
  NV.pageHead = (title, sub, tip) => {
    let src = "";
    const sl = document.querySelector(".srcline");
    if (sl) { src = sl.innerHTML; sl.remove(); }
    const t = (tip || "") + (src ? '<p class="src"><b>About this data.</b> ' + src + "</p>" : "");
    return "<h1>" + title + (t ? NV.info(t) : "") + "</h1>" + '<p class="q">' + sub + "</p>";
  };

  const SPARK = '<svg viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><path d="M8 0l1.7 5.1L15 7 9.7 8.9 8 14l-1.7-5.1L1 7l5.3-1.9z"/><path d="M13.5 10.5l.6 1.6 1.6.6-1.6.6-.6 1.6-.6-1.6-1.6-.6 1.6-.6z" opacity=".7"/></svg>';
  NV.aiBadge = (label) => '<span class="aibadge">' + SPARK + (label || "AI insights") + "</span>";
  const AI_TIP = "<p>Written from the figures computed on this page. The insight restates them " +
    "and points at what to do; it never calculates, forecasts or adds a number of its own.</p>" +
    "<p>If an insight and a figure ever disagree, the figure is right.</p>";

  /* AI insight strip for the working pages: 2-4 cards across.
     Each insight: { sev: high|med|good|info, html, meta, focus, extra }.
     PRODUCTION: replace the templated `html` with a model call that receives
     the same computed facts and is asked to summarise, never to calculate. */
  NV.insightStrip = (list) => {
    if (!list.length) return "";
    return '<section class="aistrip" aria-label="AI insights"><header>' + NV.aiBadge() +
      '<span class="gen">From this period’s calls · updates with your filters</span>' +
      NV.info(AI_TIP, "right") + '</header><div class="aicards">' +
      list.map((i) => '<article class="aicard sev-' + (i.sev || "info") + '"><p>' + i.html + "</p>" +
        '<footer><span class="meta">' + (i.meta || "") + "</span>" +
        (i.focus ? '<a href="' + NV.actHref(i.focus, i.extra) + '">What to do →</a>' : "") +
        "</footer></article>").join("") + "</div></section>";
  };

  /* Richer feed for the executive overview: each card expands in place to show
     the evidence and the next step, instead of scrolling the reader away. */
  NV.insightFeed = (list, label) => {
    return '<section class="aifeed" aria-label="AI insights"><header>' + NV.aiBadge(label) +
      NV.info(AI_TIP, "right") + '</header><p class="gen">Generated from ' +
      NV.calls().length + " calls in this period · updates with your filters</p>" +
      list.map((i, n) => '<details class="aiitem sev-' + (i.sev || "info") + '"' + (n === 0 ? " open" : "") + ">" +
        "<summary><span class=\"ai-t\">" + i.html + '</span><span class="ai-meta">' +
        '<span>' + (i.meta || "") + "</span>" +
        (i.evidence ? '<span class="ai-more">' + (i.moreLabel || "Evidence") + "</span>" : "") +
        "</span></summary>" +
        (i.evidence ? '<div class="ai-ev">' + i.evidence + "</div>" : "") +
        '<div class="ai-act">' +
        (i.focus ? '<a class="btn primary" href="' + NV.actHref(i.focus, i.extra) + '">What to do →</a>' : "") +
        (i.anchor ? '<a class="btn ghost" href="#' + i.anchor + '">Show in overview</a>' : "") +
        "</div></details>").join("") + "</section>";
  };

  /* ---------------- action edits ----------------
     The prototype has no backend, so edits made on the action board (moves,
     checklist ticks, logged updates, new actions) are kept in this browser's
     storage and re-applied on every page. Wrapped: storage can be blocked. */
  const AKEY = "nvx-actions-v2";
  NV.actStore = { edits: {}, created: [] };
  try {
    const raw = localStorage.getItem(AKEY);
    if (raw) NV.actStore = Object.assign(NV.actStore, JSON.parse(raw));
  } catch (e) { /* defaults */ }
  NV.actStore.created.forEach((a) => { if (!D.actions.some((x) => x.id === a.id)) D.actions.push(a); });
  D.actions.forEach((a) => {
    const e = NV.actStore.edits[a.id];
    if (e) ["status", "action_taken", "outcome", "owner", "due", "priority"].forEach((k) => { if (e[k] !== undefined) a[k] = e[k]; });
  });
  NV.actSave = (a, patch) => {
    const e = NV.actStore.edits[a.id] = Object.assign(NV.actStore.edits[a.id] || {}, patch || {});
    ["status", "action_taken", "outcome", "owner", "due", "priority"].forEach((k) => { if (e[k] !== undefined) a[k] = e[k]; });
    try { localStorage.setItem(AKEY, JSON.stringify(NV.actStore)); } catch (x) { /* session only */ }
  };
  NV.actCreate = (a) => {
    NV.actStore.created.push(a); D.actions.push(a);
    try { localStorage.setItem(AKEY, JSON.stringify(NV.actStore)); } catch (x) { /* session only */ }
  };
  NV.actReset = () => {
    try { localStorage.removeItem(AKEY); } catch (x) { /* ignore */ }
    location.reload();
  };
  NV.toast = (msg) => {
    let t = document.getElementById("nv-toast");
    if (!t) { t = document.createElement("div"); t.id = "nv-toast"; t.setAttribute("role", "status"); document.body.appendChild(t); }
    t.textContent = msg; t.classList.add("on");
    clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("on"), 2200);
  };

  /* ---------------- shared short names ---------------- */
  NV.IND_SHORT = {
    exit_language: ["Exit language", true],
    escalation_missed: ["Escalation missed", true],
    critical_signal: ["Critical signal", true],
    complaint_choice: ["Complaint vs us", false],
    knowledge_failure: ["Wrong rule stated", false],
    control_exception: ["Control exception", false],
    unresolved: ["Unresolved", false],
    repeat_contact: ["Repeat contact", false],
    broker_adverse: ["Broker adverse", false],
    high_effort: ["High effort", false],
  };
  const IND_ORDER = Object.keys(NV.IND_SHORT);
  NV.fireChips = (e, max) => {
    const codes = e.scoped_indicators.map((i) => i.code)
      .sort((a, b) => IND_ORDER.indexOf(a) - IND_ORDER.indexOf(b));
    const shown = codes.slice(0, max || 3);
    return '<div class="fires">' + shown.map((c) =>
      '<a class="fire' + (NV.IND_SHORT[c][1] ? " crit" : "") + '" href="' +
      NV.actHref(c, { employer: e.id }) + '" title="What to do about this">' +
      NV.esc(NV.IND_SHORT[c][0]) + "</a>").join("") +
      (codes.length > shown.length ? '<span class="fire more" title="' +
        NV.esc(codes.slice(shown.length).map((c) => NV.IND_SHORT[c][0]).join(", ")) + '">+' +
        (codes.length - shown.length) + "</span>" : "") + "</div>";
  };

  /* Renewal distance counted from the end of the corpus window (September). */
  NV.AS_OF_M = 9;
  NV.monthsTo = (m) => ((m - NV.AS_OF_M) + 12) % 12 || 12;
  NV.RENEW_SOON = 4;
  NV.renewCell = (e) => {
    const m = NV.monthsTo(e.renewal_m);
    return NV.esc(e.renewal_month) + (m <= NV.RENEW_SOON
      ? '<span class="soon">in ' + m + " mo</span>" : '<span class="later">' + m + " mo</span>");
  };
  NV.isFlagged = (e) => e.scoped_band === "High" || e.scoped_band === "Elevated";

  NV.spark = (values, w, h, color) => {
    const W = w || 70, H = h || 20, max = Math.max.apply(null, values.concat([1]));
    const c = color || "var(--seq-2)";
    const pts = values.map((v, i) => [3 + i * (W - 6) / Math.max(values.length - 1, 1),
      H - 3 - (v / max) * (H - 7)]);
    const last = pts[pts.length - 1];
    return '<svg viewBox="0 0 ' + W + " " + H + '" width="' + W + '" height="' + H +
      '" aria-hidden="true" style="display:block;overflow:visible"><path d="M' +
      pts.map((p) => p[0].toFixed(1) + "," + p[1].toFixed(1)).join("L") +
      '" fill="none" stroke="' + c + '" stroke-width="1.75" stroke-linejoin="round"/>' +
      '<circle cx="' + last[0].toFixed(1) + '" cy="' + last[1].toFixed(1) + '" r="2.8" fill="' + c + '"/></svg>';
  };
  NV.barcell = (n, max, bad) =>
    '<div class="barcell"><div class="track"><i class="' + (bad ? "bad" : "") +
    '" style="width:' + (max ? Math.max(4, Math.round(n / max * 100)) : 0) + '%"></i></div><span>' +
    n + "</span></div>";

  NV.tbl = (cols, rows, rowAttrs) => {
    if (!rows.length) return '<div class="empty"><b>Nothing in scope</b>Widen the period or clear a filter.</div>';
    return '<div class="tblwrap"><table><thead><tr>' +
      cols.map((c) => "<th" + (c[1] ? ' class="' + c[1] + '"' : "") + ">" + c[0] + "</th>").join("") +
      "</tr></thead><tbody>" + rows.map((r, ri) => "<tr" + (rowAttrs ? rowAttrs(ri) : "") + ">" +
        r.map((cell, i) => {
          const cls = (cols[i] || [])[1];
          return "<td" + (cls ? ' class="' + cls + '"' : "") + ">" + cell + "</td>";
        }).join("") + "</tr>").join("") + "</tbody></table></div>";
  };
  /* Rows that navigate: data-href on the row, links inside stay links. */
  NV.wireRows = (root) => {
    root.querySelectorAll("tr[data-href]").forEach((tr) => {
      tr.classList.add("clickable");
      tr.addEventListener("click", (e) => {
        if (e.target.closest("a, button")) return;
        window.location.href = tr.dataset.href;
      });
    });
    root.querySelectorAll("[data-call]").forEach((el) =>
      el.addEventListener("click", (e) => { e.preventDefault(); e.stopPropagation(); NV.openCall(el.dataset.call); }));
    NV.wireKeyboard(root);
  };
  NV.empHref = (id) => {
    const base = NV.href("employer.html").replace(/([?&])employer=[^&]*&?/, "$1").replace(/[?&]$/, "");
    return base + (base.indexOf("?") === -1 ? "?" : "&") + "employer=" + encodeURIComponent(id);
  };
  /* ---------------- charts ----------------
     Drawn at the host's real pixel width, so a 12px label stays 12px at any
     screen size. (The shared charts in ../app.js draw into a fixed viewBox and
     scale, which is why their type and strokes balloon on a wide panel.)
     Redrawn on resize. Values of null are gaps, not zeros. */
  const charts = [];
  let rsz;
  window.addEventListener("resize", () => {
    clearTimeout(rsz);
    rsz = setTimeout(() => charts.forEach((c) => { if (document.body.contains(c.host)) c.draw(); }), 120);
  });
  function niceMax(v) {
    if (v <= 5) return 5;
    const p = Math.pow(10, Math.floor(Math.log10(v))), n = v / p;
    return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * p;
  }
  function chartShell(host, cfg, drawBody) {
    const draw = () => {
      const W = Math.max(host.clientWidth, 280), H = cfg.height || 240;
      const P = { t: 12, r: 12, b: cfg.xTitle ? 46 : 30, l: cfg.yTitle ? 52 : 38 };
      const lo = cfg.yMin || 0;
      const hi = cfg.yMax != null ? cfg.yMax : niceMax(Math.max.apply(null,
        cfg.series.flatMap((s) => s.values.filter((v) => v != null)).concat([1])));
      const y = (v) => P.t + (1 - (v - lo) / (hi - lo)) * (H - P.t - P.b);
      const iw = W - P.l - P.r, n = cfg.labels.length, bw = iw / n;
      let g = "";
      const ticks = cfg.ticks || 4;
      for (let i = 0; i <= ticks; i++) {
        const v = lo + (hi - lo) * i / ticks;
        g += '<line x1="' + P.l + '" x2="' + (W - P.r) + '" y1="' + y(v) + '" y2="' + y(v) + '" stroke="var(--rule)" stroke-width="1"/>' +
          '<text x="' + (P.l - 8) + '" y="' + (y(v) + 4) + '" text-anchor="end" font-size="12" fill="var(--ink-3)">' +
          (Math.round(v * 10) / 10) + (cfg.suffix || "") + "</text>";
      }
      const every = n > 8 && W < 520 ? 2 : 1;
      cfg.labels.forEach((l, i) => {
        if (i % every) return;
        g += '<text x="' + (P.l + bw * i + bw / 2) + '" y="' + (H - P.b + 18) + '" text-anchor="middle" font-size="12" fill="var(--ink-2)">' + NV.esc(l) + "</text>";
      });
      if (cfg.xTitle) g += '<text x="' + (P.l + iw / 2) + '" y="' + (H - 6) + '" text-anchor="middle" font-size="12" fill="var(--ink-3)">' + NV.esc(cfg.xTitle) + "</text>";
      if (cfg.yTitle) g += '<text transform="translate(13 ' + (P.t + (H - P.t - P.b) / 2) + ') rotate(-90)" text-anchor="middle" font-size="12" fill="var(--ink-3)">' + NV.esc(cfg.yTitle) + "</text>";
      g += drawBody({ W: W, H: H, P: P, y: y, bw: bw, n: n, lo: lo });
      host.innerHTML = '<div class="vlegend">' + cfg.series.map((s) => '<span><i style="background:' + s.color + '"></i>' + NV.esc(s.name) + "</span>").join("") +
        '</div><svg width="' + W + '" height="' + H + '" role="img" aria-label="' + NV.esc(cfg.aria || "chart") + '" style="display:block;overflow:visible">' + g + "</svg>";
      /* one hover band per x position */
      const svg = host.querySelector("svg");
      cfg.labels.forEach((l, i) => {
        const r = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        r.setAttribute("x", P.l + bw * i); r.setAttribute("y", P.t); r.setAttribute("width", bw);
        r.setAttribute("height", H - P.t - P.b); r.setAttribute("fill", "transparent");
        r.addEventListener("mousemove", (e) => NV.showTip(e, "<b>" + NV.esc(cfg.tipTitle ? cfg.tipTitle(i) : l) + "</b><dl>" +
          cfg.series.map((s) => "<dt>" + NV.esc(s.name) + "</dt><dd>" + (s.values[i] == null ? "–" : s.values[i] + (cfg.suffix || "")) + "</dd>").join("") +
          "</dl>" + (cfg.note && cfg.note(i) ? '<div style="margin-top:6px;color:var(--ink-3)">' + cfg.note(i) + "</div>" : "")));
        r.addEventListener("mouseleave", NV.hideTip);
        svg.appendChild(r);
      });
    };
    charts.push({ host: host, draw: draw });
    draw();
  }
  /* Grouped vertical bars, rounded tops. */
  NV.vbars = (host, cfg) => chartShell(host, cfg, (d) => {
    const k = cfg.series.length, gap = Math.min(d.bw * .28, 26);
    const w = Math.max(Math.min((d.bw - gap) / k, 18), 3);
    let g = "";
    cfg.labels.forEach((l, i) => {
      const x0 = d.P.l + d.bw * i + (d.bw - w * k - (k - 1) * 2) / 2;
      cfg.series.forEach((s, si) => {
        const v = s.values[i];
        if (!v) return;
        const top = d.y(v), bot = d.y(d.lo), h = Math.max(bot - top, 2), x = x0 + si * (w + 2), r = Math.min(3, w / 2);
        g += '<path d="M' + x + "," + bot + "V" + (bot - h + r) + "Q" + x + "," + (bot - h) + " " + (x + r) + "," + (bot - h) +
          "H" + (x + w - r) + "Q" + (x + w) + "," + (bot - h) + " " + (x + w) + "," + (bot - h + r) + "V" + bot + 'Z" fill="' + s.color + '"/>';
      });
      if (cfg.empty && cfg.empty(i)) g += '<text x="' + (d.P.l + d.bw * i + d.bw / 2) + '" y="' + (d.y(d.lo) - 8) +
        '" text-anchor="middle" font-size="11" fill="var(--ink-3)">none</text>';
    });
    return g;
  });
  /* Lines with a dot on every point; null breaks the line. */
  NV.vline = (host, cfg) => chartShell(host, cfg, (d) => {
    let g = "";
    cfg.series.forEach((s) => {
      let seg = [];
      const flush = () => {
        if (seg.length > 1) g += '<path d="M' + seg.map((p) => p.join(",")).join("L") + '" fill="none" stroke="' + s.color + '" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>';
        seg = [];
      };
      s.values.forEach((v, i) => {
        if (v == null) { flush(); return; }
        seg.push([d.P.l + d.bw * i + d.bw / 2, d.y(v)]);
      });
      flush();
      s.values.forEach((v, i) => {
        if (v == null) return;
        g += '<circle cx="' + (d.P.l + d.bw * i + d.bw / 2) + '" cy="' + d.y(v) + '" r="3.5" fill="' + s.color + '" stroke="var(--surface)" stroke-width="1.5"/>';
      });
    });
    return g;
  });
  /* Tiny three-bucket bars for inline use (emerging issues). */
  NV.minibars = (vals, color) => {
    const max = Math.max.apply(null, vals.concat([1]));
    return '<span class="minibars" aria-hidden="true">' + vals.map((v, i) =>
      '<i style="height:' + Math.max(8, Math.round(v / max * 100)) + "%;background:" +
      (i === vals.length - 1 ? color || "var(--seq-3)" : "var(--seq-1)") + '"><b>' + v + "</b></i>").join("") + "</span>";
  };

  NV.money = (v) => (!v ? "–" : v >= 1000000 ? "$" + (v / 1000000).toFixed(2) + "m"
    : v >= 10000 ? "$" + Math.round(v / 1000) + "k" : "$" + Math.round(v).toLocaleString());
  NV.pctOf = (n, d) => (d ? Math.round(n / d * 100) + "%" : "–");

  /* ---------------- playbooks ----------------
     What sits behind every clickable red/orange number. `calls` is a predicate
     over calls in scope; `accounts` returns employers; `actions` returns items.
     `source` matches the action items this issue produces.
     The steps are generic good practice written for the prototype - they need
     review by the client's operations and compliance owners before use. */
  const byInd = (code) => (NV.INDICATORS.find((x) => x[0] === code) || [])[2];
  NV.PLAYBOOK = {
    flagged: {
      label: "Accounts flagged", unit: "accounts", owner: "Account Management", sev: "high",
      meaning: "Accounts whose calls raise two or more unrelated risk indicators.",
      why: "Several unrelated problems on one account is the pattern worth a conversation before renewal.",
      accounts: () => NV.employersInScope().filter(NV.isFlagged),
      steps: ["Work the list top-down: most indicators and soonest renewal first.",
        "Open each account's evidence and confirm the issues are real.",
        "Name an owner and one next step per account.",
        "Review the list weekly until it shrinks."],
    },
    high: {
      label: "High-risk accounts", unit: "accounts", owner: "Account Management", sev: "high",
      meaning: "Accounts raising three or more unrelated risk indicators.",
      why: "These are the shortest list to work, and the most likely to need a senior conversation.",
      accounts: () => NV.employersInScope().filter((e) => e.scoped_band === "High"),
      steps: ["Assign a senior account manager to each account this week.",
        "Close any open service issue before contacting the employer.",
        "Call the employer contact with a summary of what went wrong and what is fixed.",
        "Keep the account on weekly watch until two clean periods."],
    },
    renew_soon: {
      label: "Flagged and renewing soon", unit: "accounts", owner: "Account Management", sev: "high",
      meaning: "Flagged accounts whose renewal falls between October and January.",
      why: "Unresolved service problems are hardest to recover once renewal talks start.",
      accounts: () => NV.employersInScope().filter((e) => NV.isFlagged(e) && NV.monthsTo(e.renewal_m) <= NV.RENEW_SOON),
      steps: ["Book a service review with each employer before the renewal meeting.",
        "Fix or give a date for every open issue on the account first.",
        "Brief the broker of record with what went wrong and what was done.",
        "Log the review outcome against the renewal."],
    },
    unresolved: {
      label: "Unresolved calls", unit: "calls", owner: "Operations", sev: "high", calls: byInd("unresolved"),
      meaning: "The caller ended the call in the same position they started, with nobody owning the next step.",
      why: "Unresolved calls come back as repeat contacts and complaints.",
      source: "process_gap",
      steps: ["Call each member back within two working days and confirm the issue is closed.",
        "Tag the root cause on each call: rule, system or process.",
        "Where two or more calls share a topic, raise a fix with that touchpoint's owner.",
        "Re-check the count in four weeks."],
    },
    escalation_missed: {
      label: "Escalations missed", unit: "calls", owner: "Operations", sev: "high", calls: byInd("escalation_missed"),
      meaning: "A supervisor was warranted on the call, and the call ended without one.",
      why: "This is a control failure, and the member knows they were refused.",
      source: "escalation_missed",
      steps: ["Team lead reviews each call within 48 hours.",
        "Contact the caller and offer the supervisor conversation they did not get.",
        "Brief the agents involved on when escalation is mandatory.",
        "Audit escalation handling weekly until integrity is above 90%."],
    },
    complaint_choice: {
      label: "Complaints against us", unit: "calls", owner: "Account Management", sev: "med", calls: byInd("complaint_choice"),
      meaning: "The caller complained, and the complaint was about us rather than a carrier or broker.",
      why: "Complaints we own are the ones we can fix directly.",
      source: "process_gap",
      steps: ["Log each complaint formally and acknowledge it to the member.",
        "Group complaints by topic and fix the largest topic first.",
        "Brief the broker on affected accounts before their renewal.",
        "Track the complaint count per account at the next review."],
    },
    repeat_contact: {
      label: "Repeat contacts", unit: "calls", owner: "Operations", sev: "med", calls: byInd("repeat_contact"),
      meaning: "The member called again about an issue they had already called about.",
      why: "Each repeat is a first call that failed, and it costs the member time twice.",
      source: "process_gap",
      steps: ["Link each repeat to its first call and find why the first call failed.",
        "Fix the cause at the touchpoint, not only in the call centre.",
        "Set a first-contact resolution target for the topic."],
    },
    exit_language: {
      label: "Exit or market-test language", unit: "calls", owner: "Account Management", sev: "high", calls: byInd("exit_language"),
      meaning: "Someone on the call said, in their own words, that they may leave or look elsewhere.",
      why: "This is the most direct retention signal the calls carry.",
      source: "retention_risk",
      steps: ["Account manager calls the employer contact within five working days.",
        "Review renewal terms and open service issues before that call.",
        "Loop in the broker of record.",
        "Keep the account on watch until renewal and log the outcome."],
    },
    critical_signal: {
      label: "Critical signals", unit: "calls", owner: "Compliance", sev: "high", calls: byInd("critical_signal"),
      meaning: "A call raised a signal tagged critical severity.",
      why: "Critical signals can mean member harm or a regulatory line crossed.",
      steps: ["Review each call the same day with the owning team.",
        "Confirm whether a member was harmed or a rule breached.",
        "Record the remediation and close the loop with the member."],
    },
    control_exception: {
      label: "Compliance control exceptions", unit: "calls", owner: "Compliance", sev: "high", calls: byInd("control_exception"),
      meaning: "A required step, such as a recording disclosure, was missed or done in the wrong order.",
      why: "It is a breach on that call however few calls the agent has.",
      source: "control_exception",
      steps: ["Log each exception in the compliance register.",
        "Coach the agents involved and recheck their next ten calls.",
        "Move to formal review if one agent repeats the exception.",
        "Change the call script so the step cannot be skipped."],
    },
    knowledge_failure: {
      label: "Rules stated incorrectly", unit: "calls", owner: "Knowledge Management", sev: "med", calls: byInd("knowledge_failure"),
      meaning: "An agent explained a published rule wrongly on the call.",
      why: "The member may act on wrong information about their cover.",
      source: "knowledge_failure",
      steps: ["Correct the information with each affected member.",
        "If more than one agent got the same rule wrong, rewrite the rule's wording.",
        "If only one agent did, schedule targeted coaching.",
        "Add the rule to the next knowledge check."],
    },
    high_effort: {
      label: "High member effort", unit: "calls", owner: "Operations", sev: "med", calls: byInd("high_effort"),
      meaning: "Long calls that also repeated, escalated or ended unresolved.",
      why: "Effort is what members remember, even when the issue is solved.",
      source: "process_gap",
      steps: ["Review the longest calls for avoidable steps.",
        "Simplify the process or add self-service for the top topic.",
        "Re-measure effort after the change."],
    },
    broker_adverse: {
      label: "Broker named adversely", unit: "calls", owner: "Broker Relations", sev: "med", calls: byInd("broker_adverse"),
      meaning: "A caller named their broker and was unhappy with them.",
      why: "A pattern across one broker's groups is a channel problem, not an account problem.",
      steps: ["Log each mention against the broker.",
        "Raise it with the broker at the next check-in.",
        "If one broker reaches three mentions across two employers, escalate to a channel review."],
    },
    brush_off: {
      label: "Calls brushed off", unit: "calls", owner: "Operations / QA", sev: "high",
      calls: (c) => c.archetype === "Brush-off",
      meaning: "The agent ended the call without solving it or naming a next step.",
      why: "It is a behaviour, and behaviours respond to coaching.",
      steps: ["QA reviews each call with the agent concerned.",
        "Coach on ownership: no call ends without a named next step.",
        "Recheck those agents' next ten calls."],
    },
    circular: {
      label: "Circular calls", unit: "calls", owner: "Operations", sev: "med",
      calls: (c) => c.archetype === "Circular",
      meaning: "The caller went round in loops without getting anywhere.",
      why: "It is a process problem: the agent had no route to an answer.",
      steps: ["Map where each call looped: which rule, system or hand-off.",
        "Give agents a clear route for that case.",
        "Re-check the topic in four weeks."],
    },
    overdue: {
      label: "Overdue actions", unit: "actions", owner: "Team leads", sev: "high",
      actions: () => D.actions.filter((a) => a.status === "overdue"),
      meaning: "Actions past their due date and not yet done.",
      why: "An overdue fix means the problem it was raised for is still happening.",
      steps: ["Chase each owner for a new date or an escalation.",
        "Reassign any item with no owner response within two days.",
        "Report the overdue count at the weekly operations meeting."],
    },
    unowned: {
      label: "Flagged accounts with no action", unit: "accounts", owner: "Account Management", sev: "med",
      accounts: () => {
        const acted = new Set(D.actions.map((a) => a.employer).filter(Boolean));
        return NV.employersInScope().filter((e) => NV.isFlagged(e) && !acted.has(e.id));
      },
      meaning: "Flagged accounts that no action names yet.",
      why: "A flag with no owner is a flag nobody is working.",
      steps: ["Pick the top five by indicators and renewal date.",
        "Raise one action per account with a named owner.",
        "Review the rest at the next weekly meeting."],
    },
  };
  /* Playbooks for things that are not one of the fixed issues: a rising
     touchpoint, topic, signal or product line. Keys: tp_<touchpoint>,
     cat_<category>, sig_<signal>, pl_<product line>. Built on demand so the
     Executive overview's emerging issues can each link to their own steps. */
  NV.pb = (key) => {
    if (!key) return null;
    if (NV.PLAYBOOK[key]) return NV.PLAYBOOK[key];
    const m = String(key).match(/^(tp|cat|sig|pl)_(.+)$/);
    if (!m) return null;
    const kind = m[1], v = m[2];
    const tp = kind === "tp" ? (D.touchpoints[v] || {}) : {};
    const nice = kind === "cat" ? v : NV.titleCase(v);
    const pred = kind === "tp" ? (c) => c.touchpoint === v
      : kind === "cat" ? (c) => c.category === v
      : kind === "sig" ? (c) => c.signals.some((s) => s.code === v)
      : (c) => c.product_line === v;
    const noun = { tp: "touchpoint", cat: "call topic", sig: "signal", pl: "product line" }[kind];
    const owner = kind === "tp" ? (tp.owner || "Operations")
      : v === "Broker Conduct" || v === "broker_conduct_adverse" ? "Broker Relations"
      : v === "retention_risk" ? "Account Management" : "Operations";
    return NV.PLAYBOOK[key] = {
      label: nice, unit: "calls", owner: owner, sev: "med", calls: pred, dynamic: true,
      meaning: "Calls about the " + nice.toLowerCase() + " " + noun + " are rising across the quarter.",
      why: kind === "tp" && tp.controls ? "This touchpoint is controlled by " + tp.controls.toLowerCase() +
        ", so that is where a fix lands." : "A rising count is an early signal, too thin yet to call a trend.",
      steps: ["Read the calls behind the rise and note what each caller was trying to do.",
        "Check whether they share one account, one broker or one document.",
        (kind === "tp" ? "Take the pattern to " + owner + ", who owns this touchpoint." : "Take the pattern to " + owner + "."),
        "Set a watch: re-check the count in four weeks before committing to a fix."],
    };
  };

  NV.pbCount = (key) => {
    const p = NV.pb(key);
    if (!p) return 0;
    if (p.calls) return NV.calls().filter(p.calls).length;
    if (p.accounts) return p.accounts().length;
    if (p.actions) return p.actions().length;
    return 0;
  };
})();
