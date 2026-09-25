import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from '@/app/App'
import { createQueryClient } from '@/app/queryClient'
import { UNPLACED_SCREENS } from '@/shared/design/navigation'
import { DrawerProvider } from '@/shared/design/drawer'
import { ThemeProvider } from '@/shared/design/ThemeProvider'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
})

function renderApp(initialPath: string): void {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network down')))
  render(
    <QueryClientProvider client={createQueryClient()}>
      <ThemeProvider>
        <DrawerProvider>
          <MemoryRouter initialEntries={[initialPath]}>
            <App />
          </MemoryRouter>
        </DrawerProvider>
      </ThemeProvider>
    </QueryClientProvider>,
  )
}

describe('App', () => {
  it('sends the root to the executive overview', () => {
    renderApp('/')

    expect(screen.getByRole('heading', { name: 'Executive overview' })).toBeInTheDocument()
  })

  it('redirects an unknown route rather than showing nothing', () => {
    renderApp('/does-not-exist-yet')

    expect(screen.getByRole('heading', { name: 'Executive overview' })).toBeInTheDocument()
  })

  it('says a screen is unbuilt rather than rendering an empty one', () => {
    // An empty screen reads as "no data", which is the one thing this
    // application must never accidentally claim.
    //
    // `/calls` rather than `/risk`: risk is built now. The assertion needs a
    // route that is genuinely still a placeholder, or it stops testing
    // anything the day the last screen lands.
    renderApp('/calls')

    expect(screen.getByText(/not built yet/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'All calls' })).toBeInTheDocument()
  })

  it('keeps the status page reachable at its own route', () => {
    renderApp('/status')

    expect(screen.getByRole('heading', { name: 'NanoVox Insights' })).toBeInTheDocument()
  })

  it('renders the rail on every screen', () => {
    renderApp('/agents')

    expect(screen.getByRole('navigation', { name: 'Screens' })).toBeInTheDocument()
  })

  it('does not route to a screen whose place is still undecided', () => {
    // C5 and C6. Both endpoints are built; neither screen has been agreed.
    // An unknown path redirects, so reaching the overview is the assertion
    // that no placeholder was silently mounted for them.
    for (const unplaced of UNPLACED_SCREENS) {
      renderApp(unplaced.to)

      expect(screen.getAllByRole('heading', { name: 'Executive overview' }).length).toBeGreaterThan(
        0,
      )
      screen.getAllByRole('navigation').forEach((nav) => {
        expect(nav.textContent).not.toContain(unplaced.label)
      })
    }
  })
})
