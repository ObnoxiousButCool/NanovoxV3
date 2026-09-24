import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'

import { NAV_ITEMS, UNPLACED_SCREENS } from '@/shared/design/navigation'
import { Shell } from '@/shared/design/Shell'
import { THEME_STORAGE_KEY } from '@/shared/design/theme'
import { DrawerProvider } from '@/shared/design/drawer'
import { ThemeProvider } from '@/shared/design/ThemeProvider'

afterEach(() => {
  localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
})

function renderShell(at = '/exec') {
  return render(
    <ThemeProvider>
      <DrawerProvider>
        <MemoryRouter initialEntries={[at]}>
          <Shell>
            <p>screen content</p>
          </Shell>
        </MemoryRouter>
      </DrawerProvider>
    </ThemeProvider>,
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

  it('keeps unplaced screens out of the rail until C5 and C6 are decided', () => {
    // Both endpoints are built. Routing to a screen nobody has agreed to
    // show would settle an open question by accident.
    renderShell()
    const nav = screen.getByRole('navigation', { name: 'Screens' })

    for (const screenItem of UNPLACED_SCREENS) {
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
