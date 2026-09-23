import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from '@/app/App'
import { createQueryClient } from '@/app/queryClient'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

function renderApp(initialPath: string): void {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network down')))
  render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter initialEntries={[initialPath]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('App', () => {
  it('renders the status page at the root route', () => {
    renderApp('/')

    expect(screen.getByRole('heading', { name: 'NanoVox Insights' })).toBeInTheDocument()
  })

  it('redirects an unknown route to the root', () => {
    renderApp('/does-not-exist-yet')

    expect(screen.getByRole('heading', { name: 'NanoVox Insights' })).toBeInTheDocument()
  })
})
