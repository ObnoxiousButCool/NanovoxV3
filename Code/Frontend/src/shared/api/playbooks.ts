/**
 * The playbook behind an issue key (checkpoint I3).
 *
 * `/actions?focus=<key>` reads its meaning, why and recommended steps from
 * here rather than from a copy kept in the frontend — a dead key is a 404
 * from the server, not an empty panel this file guessed at.
 */

import { useQuery } from '@tanstack/react-query'

import { getJson } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type Playbook = components['schemas']['PlaybookResponse']

/**
 * One issue key's playbook.
 *
 * Reference data — a key's meaning does not change between two clicks — so
 * it is cached longer than a screen query, the same reasoning
 * `useFilterOptions` already gives.
 */
export function usePlaybook(key: string | null) {
  return useQuery({
    queryKey: ['insights', 'playbook', key],
    queryFn: () => getJson<Playbook>(`/insights/playbooks/${encodeURIComponent(key ?? '')}`),
    enabled: key !== null,
    staleTime: 5 * 60 * 1000,
  })
}
