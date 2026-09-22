import { describe, expect, it } from 'vitest'

import { ApiError } from '@/shared/api/client'
import { createQueryClient, shouldRetry } from '@/app/queryClient'

describe('shouldRetry', () => {
  it('retries a network error', () => {
    expect(shouldRetry(0, new Error('network down'))).toBe(true)
  })

  it('retries a 5xx ApiError', () => {
    const error = new ApiError({
      type: 'about:blank',
      title: 'Bad gateway',
      status: 502,
      detail: null,
      code: 'http_502',
      correlation_id: null,
    })

    expect(shouldRetry(0, error)).toBe(true)
  })

  it('does not retry a 4xx ApiError', () => {
    const error = new ApiError({
      type: 'about:blank',
      title: 'Not found',
      status: 404,
      detail: null,
      code: 'not_found',
      correlation_id: null,
    })

    expect(shouldRetry(0, error)).toBe(false)
  })

  it('stops after the maximum number of retries', () => {
    expect(shouldRetry(2, new Error('network down'))).toBe(false)
  })
})

describe('createQueryClient', () => {
  it('builds a client with the shared defaults applied', () => {
    const client = createQueryClient()

    const defaults = client.getDefaultOptions()
    expect(defaults.queries?.retry).toBe(shouldRetry)
    expect(defaults.queries?.refetchOnWindowFocus).toBe(false)
  })
})
