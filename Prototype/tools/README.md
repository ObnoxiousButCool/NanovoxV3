# Prototype data pipeline

Two source documents in, one `data.js` out. Run it whenever the corpus is
re-issued or a new batch lands.

```bash
Code/Backend/.venv/Scripts/python.exe Prototype/tools/build.py
```

Use that interpreter: stage 2 needs `pypdf`, which the backend virtualenv already
has. Everything else is the standard library. Reload any open prototype
afterwards to pick up the new file.

## Stages

| Stage | Reads | Writes |
| --- | --- | --- |
| `01_read_workbook.py` | `Documents/nanovox_corpus_v9_build_bible_2.xlsx` | `build/workbook.json` |
| `02_read_transcripts.py` | `Documents/nanovox_v9_transcripts_batch1_001-100_1.pdf` | `build/transcripts.txt` |
| `03_join_corpus.py` | both of the above | `build/dataset.json` |
| `04_build_app_data.py` | `build/dataset.json` | `../data.js` |

`build/` is git-ignored — the intermediates exist so a failure can be inspected
rather than guessed at. Only `data.js` is committed.

Source paths live in `paths.py`. Run any stage on its own if you are iterating.

## Pointing it at a new corpus revision

Edit `WORKBOOK` and `TRANSCRIPTS` in `paths.py`. Two things to get right.

**Keep the pair matched.** The workbook and the transcripts PDF are re-issued
together and the filename suffix bumps each time. The 17 Sep 2026 re-issue
reassigned the caller on all 100 calls — C-0001 moved from Rowan Hollis
(CB-7700001) to Leon Castellano (CB-7700205). A tracker from one revision with
transcripts from another misattributes **every call in the corpus**, silently,
because either combination is internally consistent. Stage 3 warns if any call
fails to join or has no transcript turns, which is the symptom to watch for.

**Check the transcript header format.** Caller identity is taken from the tracker
sheet, not the header, precisely because the header changed once already: it used
to read `MEMBER CB-7700001 · Rowan Hollis` and now reads `MEMBER · CB-7700205`,
with the name appearing only as the dialogue speaker label. Stage 3 parses
speaker labels for turn counts and quoted evidence, so a further format change
shows up as a turn-count warning rather than silence.

## What the pipeline computes rather than reads

The workbook is written by openpyxl, which stores formulas without computing
them. Around 1,500 cells hold a formula and no cached value, so they read as
empty. Stage 3 derives what it can from eligible headcount and rule P-33:

- **participation** — enrolled ÷ eligible
- **fee band** — \$25 (2–8), \$30 (9–20), \$35 (21–199), \$50 (200+)
- **COBRA regime** — Cal-COBRA below 20 eligible, federal at 20 and above
- **calls per 100 lives** — planned calls ÷ enrolled × 100

- **annual fee** — fee band × 12
- **annual premium** — enrolled × the per-life lever below

**On annual premium.** An earlier version of this file said it could not be
derived because there is no rate table. That was wrong, and the mistake cost the
prototypes a whole lens. There is no *per-line* rate table, but
`Distribution Targets` carries a single reference figure —
`Annual premium per enrolled life ($)` — which is the lever the Employer Master
population was built from, and it points at Intelligence Register entry 3, the
"what are these accounts worth" question.

`premium_per_life()` in stage 3 **parses** that figure rather than hardcoding it,
so a corpus revision that changes the lever changes every figure downstream, and
warns if it cannot find it. It is flat, so premium per account is headcount in
different units: good for a board total, useless for ranking two accounts of the
same size. The fee band is the number that actually varies.

Two composites are ours, not the corpus's, and the UI labels them `derived`
wherever they appear:

- **member effort** — talk time percentile, plus repeat contact, an escalation
  the caller asked for, and an unresolved or partial outcome
- **complexity** — talk time and turn-count percentiles, plus multiple rule
  references or signals

**Sentiment and a sensitive-content flag are not derived.** The v9 tag schema has
no field for either and nothing here stands in for one.

## Two refusals worth preserving

**The churn profile is not an input to the risk band.** Employer Master carries a
High/Medium/Low churn profile, but it is the label the corpus was *generated*
from. Scoring an account on it would be circular, so it travels through as
`design_churn_profile` and the UI shows it as a segment, outside the indicator
count. The corpus has no termination outcomes, so nothing here has been validated
against real churn.

**Escalation integrity is handled ÷ triggered.** Never escalations ÷ all calls.
Against all calls a rate of zero reads as good news; against warranted calls it
reads as the control failure it is. The prototypes show both numbers side by side
for exactly that reason — 64% integrity against 7% on the wrong denominator.

## Expected output at batch 1

If the figures below change without the corpus changing, something in the
pipeline moved:

```
stage 3: 100 calls, 95 employers, 30 brokers, 20 agents, 122 rules
   outcomes: RESOLVED 63, UNRESOLVED 19, PARTIALLY RESOLVED 11, ESCALATED 7
   turns: mean 17.1, range 9-32
stage 4: 95 employers, 25 actions, 10 drivers
   bands: High 18, Elevated 12, Watch 8, None 57
   escalation integrity: 64% (7 handled of 11 triggered)
   triggers firing: 1 of 5
```

Only one of the five threshold rules fires at this volume, and that is the design
working rather than failing — the thresholds are sized for 600 calls over the same
twelve weeks, so six times the density. **Do not lower a threshold to make batch 1
produce output**; it will flood at full volume.
