import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'

import { NAV_ITEMS, OFF_RAIL_SCREENS, UNPLACED_SCREENS } from '@/shared/design/navigation'
import { Shell } from '@/shared/design/Shell'
import { THEME_STORAGE_KEY } from '@/shared/design/theme'
import { createQueryClient } from '@/app/queryClient'
import { DrawerProvider } from '@/shared/design/drawer'
import { AuthProvider } from '@/shared/auth/AuthProvider'
import { ThemeProvider } from '@/shared/design/ThemeProvider'

afterEach(() => {
  localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
})

function renderShell(at = '/exec') {
  // The shell renders the filter bar, which queries the API — so a test
  // that renders the shell needs the same providers the real app gives it.
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <ThemeProvider>
        <AuthProvider>
          <DrawerProvider>
            <MemoryRouter initialEntries={[at]}>
              <Shell>
                <p>screen content</p>
              </Shell>
            </MemoryRouter>
          </DrawerProvider>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>,
  )
}

describe('Shell', () => {
  it('renders every screen in the rail', () => {
    renderShell()
    const nav = screen.getByRole('navigation', { name: 'Screens' })

    for (const item of NAV_ITEMS) {
      expect(within(nav).getByRole('link', { name: new RegExp(item.label, 'i') })).toBeInTheDocument()
    }
  })

  it('names each screen as a question with its subtext', () => {
    // One of v2's deliberate changes: pages are named as questions, not as
    // module names. Losing the subtext in the port would lose the change.
    renderShell()

    expect(screen.getByText('What are the risks?')).toBeInTheDocument()
    expect(screen.getByText('Accounts, drivers, signals')).toBeInTheDocument()
  })

  it('marks the current screen for assistive technology, not only by colour', () => {
    renderShell('/risk')

    const current = screen.getByRole('link', { current: 'page' })
    expect(current).toHaveTextContent('What are the risks?')
  })

  it('keeps screens off the rail whether they are decided or not', () => {
    // Two different reasons, one assertion. `/demand` is still C6, and
    // routing to a screen nobody has agreed to show would settle an open
    // question by accident. `/rules` is decided and routed, and D14 put it
    // behind `/agents` rather than on the rail — so the rail staying at
    // seven entries is the decision, not a step somebody forgot.
    renderShell()
    const nav = screen.getByRole('navigation', { name: 'Screens' })

    for (const screenItem of [...UNPLACED_SCREENS, ...OFF_RAIL_SCREENS]) {
      expect(within(nav).queryByText(screenItem.label)).not.toBeInTheDocument()
    }
  })

  it('renders the screen it is given', () => {
    renderShell()

    expect(screen.getByText('screen content')).toBeInTheDocument()
  })

  it('switches theme from the rail and remembers the choice', async () => {
    const user = userEvent.setup()
    renderShell()

    await user.click(screen.getByRole('button', { name: 'Dark' }))

    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
    expect(screen.getByRole('button', { name: 'Dark' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('removes the attribute on Auto so the OS query applies', async () => {
    const user = userEvent.setup()
    renderShell()

    await user.click(screen.getByRole('button', { name: 'Dark' }))
    await user.click(screen.getByRole('button', { name: 'Auto' }))

    expect(document.documentElement.hasAttribute('data-theme')).toBe(false)
  })

  it('carries the filter bar from screen to screen', () => {
    // Without this a reader who narrows to a region and then follows the
    // rail to ask the next question arrives at the whole book, with the bar
    // reading "No filters applied". The narrowing is undone by the act of
    // following it up, and nothing on the screen says so.
    renderShell('/exec?region=Bay+Area&outcome=RESOLVED&outcome=ESCALATED&escalated=true')
    const nav = screen.getByRole('navigation', { name: 'Screens' })

    const risk = within(nav).getByRole('link', { name: /What are the risks/i })
    const carried = new URLSearchParams(risk.getAttribute('href')?.split('?')[1] ?? '')

    expect(carried.get('region')).toBe('Bay Area')
    expect(carried.get('escalated')).toBe('true')
    // Repeated, not comma-joined — the same shape the bar and the API use.
    expect(carried.getAll('outcome')).toEqual(['RESOLVED', 'ESCALATED'])
  })

  it('leaves one screen’s own controls behind when it changes screen', () => {
    // An allowlist, so this holds for a screen-local key added later. The
    // sharp one is `page`: carried onto another screen it means nothing,
    // and carried back it points into a result the filters have resized —
    // the stale-page bug the calls screen already guards against.
    renderShell('/calls?region=Bay+Area&page=3&sort=quality&order=asc&q=ironwood&perPage=100')
    const nav = screen.getByRole('navigation', { name: 'Screens' })

    const href = within(nav).getByRole('link', { name: /What are the risks/i }).getAttribute('href')
    const carried = new URLSearchParams(href?.split('?')[1] ?? '')

    expect(carried.get('region')).toBe('Bay Area')
    for (const own of ['page', 'sort', 'order', 'q', 'perPage']) {
      expect(carried.has(own)).toBe(false)
    }
  })

  it('keeps the period picker showing what it was showing', () => {
    // `period` is which picker is open, not a filter, so it is stripped
    // before the API call. It still has to travel: arriving with the dates
    // applied but the picker snapped back to Week would describe the
    // filter in force as something it is not.
    renderShell('/exec?period=month&from=2026-07-06&to=2026-07-31')
    const nav = screen.getByRole('navigation', { name: 'Screens' })

    const href = within(nav).getByRole('link', { name: /agents/i }).getAttribute('href')
    const carried = new URLSearchParams(href?.split('?')[1] ?? '')

    expect(carried.get('period')).toBe('month')
    expect(carried.get('from')).toBe('2026-07-06')
    expect(carried.get('to')).toBe('2026-07-31')
  })

  it('reaches every rail link by keyboard', async () => {
    // Keyboard operation is a Phase 1 deliverable, not a later pass.
    const user = userEvent.setup()
    renderShell()
    const links = screen.getAllByRole('link')

    await user.tab()

    expect(links).toContain(document.activeElement)
  })
})

describe('navigation data', () => {
  it('gives every screen a distinct route', () => {
    const routes = NAV_ITEMS.map((item) => item.to)

    expect(new Set(routes).size).toBe(routes.length)
  })

  it('gives every screen a question and a subtext', () => {
    for (const item of NAV_ITEMS) {
      expect(item.label.trim()).not.toBe('')
      expect(item.hint.trim()).not.toBe('')
    }
  })
})
