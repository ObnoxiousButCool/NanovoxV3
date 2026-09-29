import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from '@/app/App'
import { createQueryClient } from '@/app/queryClient'
import { NAV_ITEMS, UNPLACED_SCREENS } from '@/shared/design/navigation'
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
