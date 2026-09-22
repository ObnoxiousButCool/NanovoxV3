import { describe, expect, it, vi } from 'vitest'

import { ApiError, CORRELATION_ID_HEADER, getJson, NetworkError } from '@/shared/api/client'

const BASE_URL = 'http://api.test/api/v1'

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
}

describe('getJson', () => {
  it('parses a successful JSON response', async () => {
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse({ hello: 'world' }))

    const result = await getJson<{ hello: string }>('/health', { baseUrl: BASE_URL, fetchFn })

    expect(result).toEqual({ hello: 'world' })
    expect(fetchFn).toHaveBeenCalledWith(`${BASE_URL}/health`, expect.objectContaining({
      method: 'GET',
    }))
  })

  it('throws ApiError built from the problem document on failure', async () => {
    const problem = {
      type: 'about:blank',
      title: 'Not found',
      status: 404,
      detail: 'no such call',
      code: 'not_found',
      correlation_id: 'trace-1',
    }
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse(problem, { status: 404 }))

    await expect(getJson('/calls/999', { baseUrl: BASE_URL, fetchFn })).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
      code: 'not_found',
      correlationId: 'trace-1',
    })
  })

  it('synthesises a problem for a non-JSON error body', async () => {
    const fetchFn = vi
      .fn()
      .mockResolvedValue(new Response('<html>502</html>', { status: 502, statusText: 'Bad Gateway' }))

    await expect(getJson('/health', { baseUrl: BASE_URL, fetchFn })).rejects.toMatchObject({
      status: 502,
      code: 'http_502',
    })
  })

  it('accepts a listed non-2xx status as a valid payload', async () => {
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse({ status: 'down' }, { status: 503 }))

    const result = await getJson<{ status: string }>('/health', {
      baseUrl: BASE_URL,
      fetchFn,
      acceptStatuses: [503],
    })

    expect(result).toEqual({ status: 'down' })
  })

  it('wraps a fetch failure in a NetworkError', async () => {
    const fetchFn = vi.fn().mockRejectedValue(new TypeError('network down'))

    await expect(getJson('/health', { baseUrl: BASE_URL, fetchFn })).rejects.toBeInstanceOf(
      NetworkError,
    )
  })
})

describe('ApiError', () => {
  it('carries every field from the problem document', () => {
    const error = new ApiError({
      type: 'about:blank',
      title: 'Bad request',
      status: 400,
      detail: 'missing field',
      code: 'validation_error',
      correlation_id: 'abc',
    })

    expect(error.message).toBe('Bad request')
    expect(error.status).toBe(400)
    expect(error.code).toBe('validation_error')
    expect(error.correlationId).toBe('abc')
    expect(error.detail).toBe('missing field')
  })
})

// Reference so the header constant stays exported and used, not orphaned.
describe('CORRELATION_ID_HEADER', () => {
  it('is the header name the backend sets', () => {
    expect(CORRELATION_ID_HEADER).toBe('X-Correlation-ID')
  })
})
