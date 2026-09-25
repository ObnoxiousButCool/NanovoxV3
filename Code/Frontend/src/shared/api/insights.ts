/**
 * Queries against the insights endpoints.
 *
 * Typed from the generated client, so a backend contract change surfaces
 * here as a type error rather than as `undefined` on a screen.
 */

import { useQuery } from '@tanstack/react-query'

import { getJson } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type FilterOptions = components['schemas']['FilterOptionsResponse']
export type ExecScorecard = components['schemas']['ExecScorecardResponse']

/**
 * The values the filter bar can offer.
 *
 * Sent with the current search string so the corpus scope — sources and
 * period — applies. The endpoint ignores the rest: narrowing the options by
 * the current selection is a one-way door, and the server refuses to do it.
 *
 * Cached for longer than the default. Reference data does not move between
 * two clicks of a dropdown, and re-fetching the whole book each time a
 * filter changes would make the bar feel broken.
 */
export function useFilterOptions(search: string) {
  return useQuery({
    queryKey: ['insights', 'filters', search],
    queryFn: () => getJson<FilterOptions>(`/insights/filters${search ? `?${search}` : ''}`),
    staleTime: 5 * 60 * 1000,
  })
}
