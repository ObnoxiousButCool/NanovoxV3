/**
 * The filter set, with the URL as the source of truth.
 *
 * Not React state mirrored to the URL — the URL **is** the state, read on
 * every render and written by every change. That is what makes a view
 * shareable: paste the address to a colleague and they see the same figures,
 * which for a screen whose whole job is evidence is not a nicety.
 *
 * It also makes the back button work the way a reader expects: undoing a
 * filter is browser history rather than something this code has to model.
 *
 * ## Repeated parameters, not comma-joined lists
 *
 * `?category=Claims+%26+EOB&category=Billing+%26+Premium`, matching the API
 * exactly. The workbook's own category names contain `&` and spaces, so any
 * separator risks appearing inside a value — a parser waiting to split the
 * wrong string. `URLSearchParams` speaks repetition natively.
 *
 * ## Unset is not empty
 *
 * A parameter that is absent narrows nothing. An empty selection would mean
 * "match nothing" and render a blank screen, and an unfiltered dashboard is
 * the common case.
 */

import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'

/** Filters that take one or more values. */
export const MULTI_KEYS = [
  'region',
  'broker',
  'employer',
  'agent',
  'category',
  'productLine',
  'touchpoint',
  'outcome',
  'signal',
  'intent',
  'complaintTarget',
  'qualityBand',
] as const

/** Filters that are a single value. */
export const SINGLE_KEYS = ['from', 'to', 'asOf', 'period'] as const

/**
 * Yes/no filters. Absent means unset; `false` is a real selection.
 *
 * `repeat` is one of these on the wire and not in meaning: a repeat is a
 * relationship between two calls rather than a property of one, which is why
 * the API computes it over the whole corpus and applies it after the other
 * filters. Nothing here has to know that — but it is why the control says
 * "Repeat only" and "First contact only" rather than yes and no.
 */
export const FLAG_KEYS = ['escalated', 'repeat', 'complaint', 'complianceException'] as const

export type MultiKey = (typeof MULTI_KEYS)[number]
export type SingleKey = (typeof SINGLE_KEYS)[number]
export type FlagKey = (typeof FLAG_KEYS)[number]

export interface FilterState {
  multi: Record<MultiKey, string[]>
  single: Partial<Record<SingleKey, string>>
  flags: Partial<Record<FlagKey, boolean>>
}

/** Keys the filter bar shows behind the Advanced disclosure. */
export const ADVANCED_KEYS: readonly (MultiKey | FlagKey)[] = [
  'category',
  'productLine',
  'touchpoint',
  'outcome',
  'signal',
  'intent',
  'complaintTarget',
  'qualityBand',
  'agent',
  'escalated',
  'repeat',
  'complaint',
  'complianceException',
]

function apiSearch(params: URLSearchParams): string {
  const next = new URLSearchParams(params)
  for (const key of UI_ONLY_KEYS) next.delete(key)
  return next.toString()
}

/** Everything the shared filter bar owns, in the order the bar shows it. */
export const SHARED_KEYS = [...MULTI_KEYS, ...SINGLE_KEYS, ...FLAG_KEYS] as const

/**
 * The filter bar's own query string, for a link that changes screen.
 *
 * An allowlist, not a copy with the screen's keys deleted. The bar is shared
 * and the rest of the address is not: `page`, `sort`, `q` and `perPage`
 * belong to the calls table, `flagged` and `minIndicators` to the risk list.
 * Carrying `page=3` onto a screen with no pager is harmless; carrying it
 * back onto the calls table under a different filter set is the stale-page
 * bug `CallsScreen` already guards against. Built from the keys that are
 * known to be shared, so a screen-local key added later is excluded by
 * default rather than by someone remembering to exclude it.
 *
 * `period` travels with `from` and `to` deliberately: it says which picker
 * is showing, and arriving on the next screen with the dates applied but the
 * picker snapped back to Week would misdescribe the filter that is in force.
 */
export function sharedSearch(params: URLSearchParams): string {
  const next = new URLSearchParams()
  for (const key of SHARED_KEYS) {
    for (const value of params.getAll(key)) next.append(key, value)
  }
  return next.toString()
}

/** The shared filter bar's query string for the current address. */
export function useSharedSearch(): string {
  const [params] = useSearchParams()
  return useMemo(() => sharedSearch(params), [params])
}

function readState(params: URLSearchParams): FilterState {
  const multi = Object.fromEntries(
    MULTI_KEYS.map((key) => [key, params.getAll(key)]),
  ) as Record<MultiKey, string[]>

  const single: Partial<Record<SingleKey, string>> = {}
  for (const key of SINGLE_KEYS) {
    const value = params.get(key)
    if (value !== null) single[key] = value
  }

  const flags: Partial<Record<FlagKey, boolean>> = {}
  for (const key of FLAG_KEYS) {
    const value = params.get(key)
    // Only `true` and `false` count. Anything else is treated as unset
    // rather than coerced, because coercing "yes" to true would silently
    // apply a filter the reader did not ask for.
    if (value === 'true') flags[key] = true
    if (value === 'false') flags[key] = false
  }

  return { multi, single, flags }
}

export interface Filters extends FilterState {
  /** How many filters carry a chip, for the applied-filters row. */
  activeCount: number
  /** Whether anything the bar or the screen owns is set, for Reset. */
  canReset: boolean
  /** Every set filter, flattened for the applied-filters chip row. */
  applied: { key: string; value: string }[]
  toggleMulti: (key: MultiKey, value: string) => void
  setSingle: (key: SingleKey, value: string | null) => void
  /**
   * Several single-valued keys in **one** write.
   *
   * Calling `setSingle` twice in an event handler does not work:
   * `setSearchParams` navigates from the router's current state, which does
   * not advance between synchronous calls, so the second navigation is
   * computed from the same starting point and silently discards the first.
   * Switching period mode wrote the mode, then cleared the dates, and the
   * mode vanished.
   */
  setMany: (values: Partial<Record<SingleKey, string | null>>) => void
  setFlag: (key: FlagKey, value: boolean | null) => void
  clear: (key: string, value?: string) => void
  reset: () => void
  /** The address bar's query string, including UI-only keys. */
  search: string
  /**
   * The query string to send to the API.
   *
   * Strips the keys that exist only to restore the interface — `period` is
   * which picker is showing, not a filter. FastAPI would ignore it, but
   * sending it would put a parameter in the request that nothing documents
   * and the next person would have to work out whether it mattered.
   */
  apiSearch: string
}

/**
 * URL keys that steer the interface rather than the query.
 *
 * `period` is which picker is open. `stage` and `focus` belong to the action
 * screen: the stage strip narrows the board in the browser, and `focus`
 * chooses which playbook to open. None of the three is documented on any
 * endpoint, and a request carrying one leaves the next person working out
 * whether it mattered -- which is what this list exists to prevent.
 */
const UI_ONLY_KEYS = ['period', 'stage', 'focus'] as const

/**
 * Keys a screen owns rather than the bar: the calls table's search, sort
 * and paging, and the action board's stage strip and focused issue.
 *
 * They narrow what a reader is looking at exactly as a filter does, so
 * "Reset all" clears them and is enabled while any is set. It used to do
 * neither: the button went grey over a screen narrowed by a search term,
 * and when a chip did enable it, clicking it left `q`, `sort` and
 * `perPage` behind. A button called Reset all has to mean it.
 *
 * `page` is here for a second reason: a page number kept across a reset
 * points into a result the reset just resized, which is the stale-page bug
 * `CallsScreen` already guards against.
 */
const SCREEN_KEYS = ['q', 'sort', 'order', 'page', 'perPage', 'stage', 'focus'] as const

/** Everything "Reset all" clears, and everything that enables it. */
const RESETTABLE_KEYS: readonly string[] = [
  ...MULTI_KEYS,
  ...SINGLE_KEYS,
  ...FLAG_KEYS,
  ...SCREEN_KEYS,
]

export function useFilters(): Filters {
  const [params, setParams] = useSearchParams()
  const state = useMemo(() => readState(params), [params])

  const write = useCallback(
    (mutate: (next: URLSearchParams) => void) => {
      // The functional form, not `new URLSearchParams(params)`. Two calls in
      // one event handler both close over the same render's `params`, so the
      // second silently discards the first — switching period mode wrote the
      // mode and then cleared the dates, and the mode vanished.
      setParams(
        (previous) => {
          const next = new URLSearchParams(previous)
          mutate(next)
          return next
        },
        // `replace: false` so each change is a history entry and Back undoes
        // one filter rather than leaving the screen.
        { replace: false },
      )
    },
    [setParams],
  )

  const toggleMulti = useCallback(
    (key: MultiKey, value: string) => {
      write((next) => {
        const current = next.getAll(key)
        next.delete(key)
        const wanted = current.includes(value)
          ? current.filter((item) => item !== value)
          : [...current, value]
        for (const item of wanted) next.append(key, item)
      })
    },
    [write],
  )

  const setSingle = useCallback(
    (key: SingleKey, value: string | null) => {
      write((next) => {
        if (value === null || value === '') next.delete(key)
        else next.set(key, value)
      })
    },
    [write],
  )

  const setMany = useCallback(
    (values: Partial<Record<SingleKey, string | null>>) => {
      write((next) => {
        for (const [key, value] of Object.entries(values)) {
          if (value === null || value === '') next.delete(key)
          else next.set(key, value)
        }
      })
    },
    [write],
  )

  const setFlag = useCallback(
    (key: FlagKey, value: boolean | null) => {
      write((next) => {
        if (value === null) next.delete(key)
        else next.set(key, String(value))
      })
    },
    [write],
  )

  const clear = useCallback(
    (key: string, value?: string) => {
      write((next) => {
        if (value === undefined) {
          next.delete(key)
          return
        }
        const remaining = next.getAll(key).filter((item) => item !== value)
        next.delete(key)
        for (const item of remaining) next.append(key, item)
      })
    },
    [write],
  )

  const reset = useCallback(() => {
    write((next) => {
      for (const key of RESETTABLE_KEYS) next.delete(key)
    })
  }, [write])

  /**
   * Whether anything at all is set for Reset to clear.
   *
   * Deliberately not `activeCount`, which counts chips. A period, a search
   * term or a stage shows in its own control rather than as a chip, so a
   * chip count said "nothing is set" over a plainly narrowed screen and
   * the button sat disabled.
   */
  const canReset = useMemo(
    () => RESETTABLE_KEYS.some((key) => params.has(key)),
    [params],
  )

  const applied = useMemo(() => {
    const rows: { key: string; value: string }[] = []
    for (const key of MULTI_KEYS) {
      for (const value of state.multi[key]) rows.push({ key, value })
    }
    for (const key of FLAG_KEYS) {
      const value = state.flags[key]
      if (value !== undefined) rows.push({ key, value: value ? 'yes' : 'no' })
    }
    return rows
  }, [state])

  return {
    ...state,
    // Chips only. The period is excluded because it is always set to
    // something and shown in its own control, so counting it would make the
    // applied-filters row claim a filter the reader cannot see. What Reset
    // acts on is `canReset`, which is a different question.
    activeCount: applied.length,
    canReset,
    applied,
    toggleMulti,
    setSingle,
    setMany,
    setFlag,
    clear,
    reset,
    search: params.toString(),
    apiSearch: apiSearch(params),
  }
}
