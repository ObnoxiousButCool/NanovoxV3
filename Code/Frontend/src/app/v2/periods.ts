/**
 * The "Last 30 days" filter's presets.
 *
 * Anchored on the corpus's own latest dated call, never on the browser's
 * clock. `InsightsReader.scope()` (`application/use_cases/read_insights.py`)
 * resolves an absent `asOf` the same way — `corpus.available_until` first,
 * the real clock only as a last resort when no call carries a date at all —
 * and for the same reason stated there: this is a frozen historical batch,
 * and a window measured from today would silently slide off the back of
 * the data with every day that passes without a new one being loaded.
 *
 * `from`/`to` are the one filter this page reads from `/insights/filters`,
 * `/insights/exec`, `/insights/risk`, `/insights/calls` and
 * `/insights/actions/board` already share (`InsightsQuery`,
 * `frameworks_drivers/api/v1/insights/query.py` — "the filter bar is one
 * filter bar"), so this sends exactly the query string those endpoints
 * already parse rather than inventing a new one.
 */

export interface PeriodPreset {
  key: string
  label: string
  /** Calendar days the window covers, counting the anchor day itself.
   * `null` is "the whole corpus" — no `from`/`to` at all. */
  days: number | null
}

export const PERIOD_PRESETS: readonly PeriodPreset[] = [
  { key: '7d', label: 'Last 7 days', days: 7 },
  { key: '30d', label: 'Last 30 days', days: 30 },
  { key: '90d', label: 'Last 90 days', days: 90 },
  { key: 'all', label: 'All time', days: null },
]

export const DEFAULT_PERIOD_KEY = '30d'

export function periodByKey(key: string): PeriodPreset {
  return PERIOD_PRESETS.find((preset) => preset.key === key) ?? (PERIOD_PRESETS[1] as PeriodPreset)
}

function iso(day: Date): string {
  return day.toISOString().slice(0, 10)
}

/**
 * The query string for one preset, empty for "all time" or until the
 * corpus's own extent is known.
 *
 * `corpusLatest` is `FilterOptionsResponse.corpusPeriod.to` — the last
 * dated call in the whole book, read once from the unfiltered
 * `/insights/filters` call this page already makes, not recomputed per
 * preset.
 */
export function periodSearch(preset: PeriodPreset, corpusLatest: string | null): string {
  if (preset.days === null || corpusLatest === null) return ''
  const to = new Date(`${corpusLatest}T00:00:00Z`)
  const from = new Date(to)
  from.setUTCDate(from.getUTCDate() - (preset.days - 1))
  return new URLSearchParams({ from: iso(from), to: iso(to) }).toString()
}
