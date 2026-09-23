import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createQueryClient } from '@/app/queryClient'
import { StatusPage } from '@/app/StatusPage'

function renderWithClient(client: QueryClient = createQueryClient()): void {
  render(
    <QueryClientProvider client={client}>
      <StatusPage />
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('StatusPage', () => {
  it('shows the API status once the health check resolves', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            status: 'up',
            application: 'NanoVox Insights',
            version: '0.1.0',
            environment: 'local',
            checked_at: '2026-09-22T12:00:00Z',
            components: [],
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    )

    renderWithClient()

    expect(screen.getByText(/checking the api/i)).toBeInTheDocument()
    await waitFor(() => { expect(screen.getByText('up')).toBeInTheDocument(); })
  })

  it('shows an error when the API cannot be reached', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network down')))

    // Retries would otherwise push this past waitFor's default timeout —
    // the failure itself, not the shared retry policy, is what's under test.
    renderWithClient(new QueryClient({ defaultOptions: { queries: { retry: false } } }))

    await waitFor(() => { expect(screen.getByRole('alert')).toBeInTheDocument(); })
    expect(screen.getByRole('alert')).toHaveTextContent('Could not reach the API')
  })
})
