import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from '@/app/App'
import { createQueryClient } from '@/app/queryClient'
import { NAV_ITEMS, OFF_RAIL_SCREENS, UNPLACED_SCREENS } from '@/shared/design/navigation'
import { DrawerProvider } from '@/shared/design/drawer'
import { AuthProvider } from '@/shared/auth/AuthProvider'
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
        <AuthProvider>
          <DrawerProvider>
            <MemoryRouter initialEntries={[initialPath]}>
              <App />
            </MemoryRouter>
          </DrawerProvider>
        </AuthProvider>
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

  it.each(NAV_ITEMS.map((item) => [item.to] as const))(
    'renders a real screen at %s, never a placeholder',
    (to) => {
      // This replaces an assertion that a placeholder said "not built yet".
      // Its own comment predicted this day: it "stops testing anything the
      // day the last screen lands", and `/agents` was the last one. The
      // property worth keeping is the reason the placeholder existed — a
      // rail entry must never lead somewhere that renders as "no data" —
      // so this walks every entry and asserts the opposite.
      //
      // It no longer asserts the page heading equals the rail label. The
      // two are allowed to differ and `/hierarchy` is where they do: the
      // rail says "Isolated or systemic?" where the page asks "Is it
      // isolated or systemic?", which is the prototype's own pairing. Each
      // screen's own heading is asserted in `screens.test.tsx`, against
      // that screen rather than against the rail.
      renderApp(to)

      const [heading] = screen.getAllByRole('heading', { level: 1 })
      expect(heading?.textContent?.trim()).toBeTruthy()
      expect(screen.queryByText(/not built yet/i)).not.toBeInTheDocument()
    },
  )

  it('keeps the status page reachable at its own route', () => {
    renderApp('/status')

    expect(screen.getByRole('heading', { name: 'NanoVox Insights' })).toBeInTheDocument()
  })

  it('renders the rail on every screen', () => {
    renderApp('/agents')

    expect(screen.getByRole('navigation', { name: 'Screens' })).toBeInTheDocument()
  })

  it('routes to an off-rail screen that was decided, without putting it on the rail', () => {
    // D14 closed C5: `/rules` ships, reached from `/agents`. Landing on the
    // overview here would mean the catch-all had swallowed it again, which
    // is what `/agents`' link did for as long as the route was missing.
    for (const offRail of OFF_RAIL_SCREENS) {
      renderApp(offRail.to)

      expect(screen.getByRole('heading', { name: offRail.label })).toBeInTheDocument()
      screen.getAllByRole('navigation').forEach((nav) => {
        expect(nav.textContent).not.toContain(offRail.label)
      })
    }
  })

  it('does not route to a screen whose place is still undecided', () => {
    // C6. The endpoint is built; the screen has not been agreed. An unknown
    // path redirects, so reaching the overview is the assertion that no
    // placeholder was silently mounted for it.
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
