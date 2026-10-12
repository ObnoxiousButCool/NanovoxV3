/**
 * The "Last 30 days" filter's date math.
 *
 * The one fact worth pinning down here: the window is anchored on the
 * corpus's own last dated call, never on the clock the test runs at — a
 * frozen historical batch has no "today" of its own to measure from.
 */

import { describe, expect, it } from 'vitest'

import { DEFAULT_PERIOD_KEY, PERIOD_PRESETS, periodByKey, periodSearch } from '@/app/v2/periods'

describe('periodByKey', () => {
  it('finds a preset by its key', () => {
    expect(periodByKey('7d').label).toBe('Last 7 days')
    expect(periodByKey('all').days).toBeNull()
  })

  it('falls back to the default preset for an unknown key', () => {
    expect(periodByKey('nonsense').key).toBe(DEFAULT_PERIOD_KEY)
  })
})

describe('periodSearch', () => {
  it('spans the preset\'s days, counting the anchor day itself', () => {
    // 30 days ending 2026-09-25 starts 2026-08-27, not 2026-08-28 — the
    // anchor day is one of the thirty, not an extra day on top of them.
    const search = periodSearch(periodByKey('30d'), '2026-09-25')

    expect(new URLSearchParams(search).get('from')).toBe('2026-08-27')
    expect(new URLSearchParams(search).get('to')).toBe('2026-09-25')
  })

  it('is empty for "all time", regardless of the corpus extent', () => {
    expect(periodSearch(periodByKey('all'), '2026-09-25')).toBe('')
  })

  it('is empty until the corpus\'s own extent is known', () => {
    // Never falls back to the browser's clock — see the file banner.
    expect(periodSearch(periodByKey('30d'), null)).toBe('')
  })

  it('offers "Last 30 days" as the default, matching the mockup', () => {
    expect(periodByKey(DEFAULT_PERIOD_KEY).label).toBe('Last 30 days')
  })

  it('lists every preset the dropdown reads', () => {
    expect(PERIOD_PRESETS.map((preset) => preset.key)).toEqual(['7d', '30d', '90d', 'all'])
  })
})
