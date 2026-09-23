# Account Signals prototype

Six static pages sharing one stylesheet, one behaviour file, and one generated
dataset. No build step and no framework — open them, read them, change them.

| Page | The question it answers |
| --- | --- |
| `exec.html` | Board scorecard — five questions, answered in figures |
| `index.html` | Where is the retention risk? |
| `employer.html` | Why this account? |
| `actions.html` | What are we doing about it? |
| `hierarchy.html` | Is this isolated, or systemic? |
| `rules.html` | What do we fail to explain? — **hidden from the rail**, open it directly |

## Previewing it

Opening the files straight from disk largely works — there are no modules and no
`fetch`, just plain `<script src>` — but serve them anyway. Browsers differ over
whether a `file://` document gets storage, and storage is what remembers your
theme and your filters.

```bash
python -m http.server 4599 --directory Prototype
```

Then open <http://localhost:4599/index.html>. Any static server will do; nothing
here needs a backend, a database, or the project's virtualenv.

In Claude Code or VS Code, copy the tracked template once and the `prototype`
server appears alongside `backend` and `frontend`:

```bash
cp .claude/launch.json.example .claude/launch.json
```

`.claude/launch.json` itself is git-ignored, because the ports in it are a local
choice — so edit yours freely. On a machine where `python` is not on PATH, change
that entry's `runtimeExecutable` to `python3` or to your interpreter's full path.

## Where the numbers come from

Every figure traces to the v9 corpus — the build bible workbook and the batch 1
transcripts PDF. `data.js` is generated from both by the four-stage pipeline in
[`tools/`](tools/README.md); it is committed so the prototype opens without
running anything, and regenerated when the corpus is re-issued.

Nothing here is hand-typed or illustrative. If a number looks wrong, it is the
pipeline or the corpus that is wrong, and `tools/README.md` records the figures
each stage should produce.

## Reading the epistemic chips

Every claim carries a chip saying what kind of claim it is, because the whole
point is not to let call behaviour masquerade as a churn prediction.

| Chip | What it means |
| --- | --- |
| `OBSERVED` | Counted directly from the corpus |
| `REFERENCE` | An account fact from the workbook, not from a call |
| `DERIVED` | Computed by us from observed values — the formula is stated |
| `PATTERN` | A shape across calls, with no cause claimed |
| `INFERENCE` | A reading that goes beyond the data |
| `RECOMMENDATION` | A suggested action |

The risk band counts indicators; it is **not** a churn score. The corpus carries
no termination outcomes, so nothing here has been validated against real churn,
and the employer churn profile the corpus was generated from is deliberately kept
out of the band to avoid scoring accounts on their own label.

## Theme

A three-way control at the foot of the rail: **Light**, **Dark**, **Auto**.

**Light is the default**, not Auto — this gets read in meetings and printed, where a
dark ground is the wrong starting point however the laptop is set. Auto follows the
OS and is a deliberate choice rather than the fallback. Whatever is picked persists
per browser and is stamped before first paint, so the ground colour never flashes.

Charts bake some colours into SVG attributes, so a switch clears the ink cache and
redraws rather than leaving it to CSS. If you add a chart that resolves a token at
render time, it has to go through `NV.inkOn` for the same reason.
