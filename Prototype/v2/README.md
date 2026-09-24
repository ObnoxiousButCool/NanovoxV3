# Account Signals v2

A reworked version of the six pages, built from review feedback. It sits beside the
original and reuses its `../data.js`, `../app.js` and `../app.css`, adding only two files:

- `nv2.js`: page names, the lean filter bar, tooltips, AI insight cards, and the
  playbooks behind every red or orange number (`NV.PLAYBOOK`)
- `v2.css`: larger type, tiles, the AI surfaces, the action page

Serve the Prototype folder and open `v2/exec.html`:

```bash
python -m http.server 4599 --directory Prototype
```

## What changed

- Pages are named as questions, each with a one-line plain-English subtext.
- Explanations moved into (i) tooltips. No table is wider than six columns.
- The scope line and "Copy link" are gone. Advanced filters sits next to Reset all.
- Every red or orange number links to `actions.html?focus=<issue>`, which shows what
  the issue means, the recommended steps, a suggested owner, the accounts and calls
  behind it, and any action already in progress.
- AI insights are one clearly marked surface per page: a feed on the Executive
  overview (each card expands to its evidence and a "What to do" button), and a strip on
  every other page.
- The cost-to-serve section is removed.
- The Executive overview no longer repeats the Risks page. It carries a "Needs attention now"
  alert feed, AI insights through four lenses (employers, churn and retention, product and
  service, payer and carrier), emerging issues with an action for each, and a one-line
  action progress strip.
- The action board is Trello-style: labels, due badges, owner avatars, a green edge on
  completed cards and a two-column card view with a checklist, the calls behind the card,
  an activity timeline and "Move to". Moves are in-memory only.
- Charts are drawn at real pixel size (`NV.vbars`, `NV.vline` in nv2.js), so labels stay
  12px at any width. Weeks with no calls show as gaps, not zeros.

- Cards can be created, ticked off, updated and completed from the board. The card always
  shows the next step. Changes are kept in this browser's storage (`nvx-actions-v2`), so they
  survive a reload; `NV.actReset()` in the console clears them.
- `calls.html` lists every call with search, sort, paging and row selection, and downloads
  the filtered or selected calls as a 26-column CSV.
- Footer source notes moved into each page title's (i) tooltip under "About this data".

## Before production

- **AI text is templated.** Each page builds its insights from the figures it computes.
  Look for `PRODUCTION:` comments: that is where a model call goes. Pass it the same
  computed facts and ask it to summarise, never to calculate.
- **The recommended steps are generic.** They are a starting playbook and need review
  by the owning teams (Operations, Compliance, Account Management, Knowledge Management).
- **"Newly flagged" ignores the filters.** It is counted across the whole book, and the
  tooltip says so.
