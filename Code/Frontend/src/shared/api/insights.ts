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

export type ExecScorecard = components['schemas']['ExecScorecardResponse']
export type RiskScreen = components['schemas']['RiskScreenResponse']
export type AccountDetail = components['schemas']['AccountResponse']
export type Hierarchy = components['schemas']['HierarchyResponse']

/**
 * A screen's query, keyed by the filters that produced it.
 *
 * The search string is part of the key rather than a dependency of the
 * function, so two filter states never share a cache entry. React Query
 * would otherwise serve the previous scope's figures under the new scope's
 * chips for as long as the refetch took, and a figure shown under the wrong
 * scope is worse than a spinner.
 */
function useScreen<T>(name: string, path: string, search: string) {
  return useQuery({
    queryKey: ['insights', name, search],
    queryFn: () => getJson<T>(`${path}${search ? `?${search}` : ''}`),
  })
}

export function useExec(search: string) {
  return useScreen<ExecScorecard>('exec', '/insights/exec', search)
}

export function useRisk(search: string) {
  return useScreen<RiskScreen>('risk', '/insights/risk', search)
}

export function useHierarchy(search: string) {
  return useScreen<Hierarchy>('hierarchy', '/insights/hierarchy', search)
}

/**
 * One account.
 *
 * `employerRef` joins the key because it selects a different resource, not
 * a different view of the same one — sharing a cache entry across accounts
 * is how one employer's figures end up under another's name.
 */
export function useAccount(employerRef: string, search: string) {
  return useQuery({
    queryKey: ['insights', 'account', employerRef, search],
    queryFn: () =>
      getJson<AccountDetail>(
        `/insights/accounts/${encodeURIComponent(employerRef)}${search ? `?${search}` : ''}`,
      ),
  })
}

export type ActionsFindings = components['schemas']['ActionsResponse']

/**
 * Findings to act on — routed by team, with compliance exposure.
 *
 * **Not** the action board (`@/shared/api/actionBoard`). This is a reading
 * of the calls, with no status; the board is the persisted record of what
 * somebody is doing about it. Keeping the two on separate hooks matches the
 * separation the backend insists on: merging them is how a finding acquires
 * a fake status.
 */
export function useActionsFindings(search: string) {
  return useScreen<ActionsFindings>('actionsFindings', '/insights/actions', search)
}

export type CallsPage = components['schemas']['CallsPageResponse']
export type CallRow = components['schemas']['CallRowResponse']
export type CallEvidenceData = components['schemas']['CallEvidenceResponse']

/** The workbench. `search` already carries filters, search, sort and paging. */
export function useCalls(search: string) {
  return useScreen<CallsPage>('calls', '/insights/calls', search)
}

/**
 * One call's evidence.
 *
 * Deliberately **not** keyed by the current filters. Evidence is one call
 * by reference: if the key carried the filter state, opening the same call
 * from two screens would refetch it and could show two different frames
 * for the same call, which is the opposite of evidence.
 *
 * `staleTime: Infinity` for the same reason — a call that has already been
 * read does not change while the reader is looking at it, and a refetch
 * behind an open drawer would replace the turns under their eyes.
 */
export function useCallEvidence(reference: string | null) {
  return useQuery({
    queryKey: ['insights', 'call', reference],
    queryFn: () =>
      getJson<CallEvidenceData>(`/insights/calls/${encodeURIComponent(reference ?? '')}`),
    enabled: reference !== null,
    staleTime: Infinity,
  })
}

export type GeneratedInsights = components['schemas']['GeneratedInsightsResponse']
export type Insight = components['schemas']['InsightResponse']

/**
 * A screen's generated insights.
 *
 * Its own query, never folded into the screen's, so the figures never wait
 * on a model. The scorecard paints; the sentences arrive after, or an
 * unavailable panel does.
 *
 * `retry: false` because the two failures worth distinguishing are both
 * already answers rather than errors — no provider configured, and a model
 * that stated a figure nobody measured. Both come back 200 with a reason to
 * render, and retrying a rejected answer would spend a second model call to
 * be told the same thing.
 */
export function useGeneratedInsights(screen: 'exec', search: string) {
  const query = new URLSearchParams(search)
  query.set('screen', screen)
  return useQuery({
    queryKey: ['insights', 'generated', screen, search],
    queryFn: () => getJson<GeneratedInsights>(`/insights/generated?${query.toString()}`),
    retry: false,
    staleTime: 5 * 60 * 1000,
  })
}
