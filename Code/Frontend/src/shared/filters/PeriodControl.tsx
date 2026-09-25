/**
 * The period: **Week · Month · Custom**, as the prototype has it.
 *
 * A segmented control picks the mode, and a second control beside it changes
 * with that mode — a week list, a month list, or two date inputs. All three
 * resolve to `from` and `to`, which is what the API takes (decision **D11**:
 * the period bounds the corpus and does not redefine any metric's window).
 *
 * ## Where this departs from the prototype, and why
 *
 * The prototype's weeks and months are batch-1 artefacts:
 *
 * - its **weeks** are indices anchored on a hard-coded `2026-07-06`, each
 *   running Monday to Friday because that corpus has no weekend calls;
 * - its **months** are four-week blocks wearing month names —
 *   `Aug = [5,6,7,8]` is 3 to 28 August, so picking "Aug 2026" silently
 *   drops five of its days.
 *
 * Both are reproduced in *shape* and corrected in *substance*: weeks are
 * real seven-day weeks from the corpus start, months are real calendar
 * months. Reproducing a boundary known to be wrong would be the wrong kind
 * of fidelity, and a reader comparing a month here against a month anywhere
 * else would find them disagree with nothing to explain it.
 *
 * The lists are built from the corpus extent the server reports, so a week
 * is only offered if the corpus reaches it.
 */

import { useMemo } from 'react'

export type PeriodMode = 'week' | 'month' | 'custom'

const MODES: { value: PeriodMode; label: string }[] = [
  { value: 'week', label: 'Week' },
  { value: 'month', label: 'Month' },
  { value: 'custom', label: 'Custom' },
]

const MONTH_NAMES = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
]

interface Span {
  from: string
  to: string
  label: string
}

function iso(day: Date): string {
  return day.toISOString().slice(0, 10)
}

function shortDate(value: string): string {
  const [, month, day] = value.split('-').map(Number)
  return `${String(day)} ${MONTH_NAMES[(month ?? 1) - 1] ?? ''}`
}

/** Real seven-day weeks from the corpus start, earliest first. */
function weeksIn(from: string, to: string): Span[] {
  const spans: Span[] = []
  const end = new Date(`${to}T00:00:00Z`)
  let cursor = new Date(`${from}T00:00:00Z`)
  let index = 1
  while (cursor <= end && index <= 60) {
    const close = new Date(cursor)
    close.setUTCDate(close.getUTCDate() + 6)
    const last = close > end ? end : close
    spans.push({
      from: iso(cursor),
      to: iso(last),
      label: `Wk ${String(index)} · ${shortDate(iso(cursor))} – ${shortDate(iso(last))}`,
    })
    cursor = new Date(last)
    cursor.setUTCDate(cursor.getUTCDate() + 1)
    index += 1
  }
  return spans
}

/** Real calendar months, clipped to the corpus at either end. */
function monthsIn(from: string, to: string): Span[] {
  const spans: Span[] = []
  const start = new Date(`${from}T00:00:00Z`)
  const end = new Date(`${to}T00:00:00Z`)
  let year = start.getUTCFullYear()
  let month = start.getUTCMonth()

  while (year < end.getUTCFullYear() || (year === end.getUTCFullYear() && month <= end.getUTCMonth())) {
    const first = new Date(Date.UTC(year, month, 1))
    const last = new Date(Date.UTC(year, month + 1, 0))
    spans.push({
      from: iso(first < start ? start : first),
      to: iso(last > end ? end : last),
      label: `${MONTH_NAMES[month] ?? ''} ${String(year)}`,
    })
    month += 1
    if (month > 11) {
      month = 0
      year += 1
    }
  }
  return spans
}

export function PeriodControl({
  mode,
  from,
  to,
  corpusFrom,
  corpusTo,
  onChange,
}: {
  mode: PeriodMode
  from: string | null
  to: string | null
  corpusFrom: string | null
  corpusTo: string | null
  /** One call per action: mode and dates together, never two writes. */
  onChange: (next: { mode: PeriodMode; from: string | null; to: string | null }) => void
}) {
  const spans = useMemo(() => {
    if (corpusFrom === null || corpusTo === null) return []
    return mode === 'week' ? weeksIn(corpusFrom, corpusTo) : monthsIn(corpusFrom, corpusTo)
  }, [mode, corpusFrom, corpusTo])

  const current = spans.find((span) => span.from === from && span.to === to)
  const noun = mode === 'week' ? 'weeks' : 'months'

  return (
    <>
      <div className="nv-fg">
        <span>Period</span>
        <div className="nv-seg" role="group" aria-label="Period">
          {MODES.map((option) => (
            <button
              key={option.value}
              type="button"
              aria-pressed={mode === option.value}
              onClick={() => {
                // Switching mode clears the selection rather than carrying a
                // week's dates into a month picker, where they would show as
                // "All months" while the screen still showed one week.
                onChange({ mode: option.value, from: null, to: null })
              }}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {mode === 'custom' ? (
        <>
          <label className="nv-fg">
            <span>Date range</span>
            <input
              type="date"
              aria-label="From"
              value={from ?? ''}
              min={corpusFrom ?? undefined}
              // An inverted range is refused by the API with a 400 naming
              // both dates; capping here stops the reader before the request.
              max={to ?? corpusTo ?? undefined}
              onChange={(event) => {
                onChange({ mode, from: event.target.value || null, to })
              }}
            />
          </label>
          <label className="nv-fg">
            <span>&nbsp;</span>
            <input
              type="date"
              aria-label="To"
              value={to ?? ''}
              min={from ?? corpusFrom ?? undefined}
              max={corpusTo ?? undefined}
              onChange={(event) => {
                onChange({ mode, from, to: event.target.value || null })
              }}
            />
          </label>
        </>
      ) : (
        <label className="nv-fg">
          <span>{mode === 'week' ? 'Week' : 'Month'}</span>
          <select
            value={current ? `${current.from}|${current.to}` : ''}
            disabled={spans.length === 0}
            onChange={(event) => {
              if (!event.target.value) {
                onChange({ mode, from: null, to: null })
                return
              }
              const [start, end] = event.target.value.split('|')
              onChange({ mode, from: start ?? null, to: end ?? null })
            }}
          >
            <option value="">
              {spans.length === 0
                ? 'No dated calls'
                : `All ${String(spans.length)} ${noun}`}
            </option>
            {spans.map((span) => (
              <option key={span.from} value={`${span.from}|${span.to}`}>
                {span.label}
              </option>
            ))}
          </select>
        </label>
      )}
    </>
  )
}
