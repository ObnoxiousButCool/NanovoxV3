import { useQuery } from '@tanstack/react-query'

import { getJson } from '@/shared/api/client'

export type ComponentStatus = 'up' | 'down'

export interface ComponentHealth {
  readonly name: string
  readonly status: ComponentStatus
  readonly detail: string | null
}

export interface HealthResponse {
  readonly status: ComponentStatus
  readonly application: string
  readonly version: string
  readonly environment: string
  readonly checked_at: string
  readonly components: readonly ComponentHealth[]
}

const HEALTH_QUERY_KEY = ['health'] as const

export function useHealth() {
  return useQuery({
    queryKey: HEALTH_QUERY_KEY,
    queryFn: () => getJson<HealthResponse>('/health', { acceptStatuses: [503] }),
  })
}
