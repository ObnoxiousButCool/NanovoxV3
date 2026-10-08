/**
 * Sign-in, end to end through the UI (feature/email-otp-login, not on main).
 *
 * Starts logged out, unlike every other test in the suite — see
 * `src/test/setup.ts` on why that is the default and this file the
 * exception.
 */

import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from '@/app/App'
import { AppProviders } from '@/app/providers'
import { setAuthToken } from '@/shared/api/client'

const LOGIN_URL = 'http://api.test/api/v1/auth/login'
const FILTERS_URL = 'http://api.test/api/v1/insights/filters'

const USERNAME = 'Technossus'
const PASSWORD = 'Tech@2026'

// Every field `FilterBar` reads, empty: it queries independently of whatever
// screen it sits on, so a login test that lands on a real screen afterward
// still has to feed it something shaped correctly.
const EMPTY_FILTER_OPTIONS = {
  regions: [],
  brokers: [],
  employers: [],
  agents: [],
  touchpoints: [],
  signals: [],
  complaintTargets: [],
  outcomes: [],
  categories: [],
  productLines: [],
  intents: [],
  qualityBands: [],
}

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
}

function serve(): void {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: string, init?: RequestInit) => {
      if (input === LOGIN_URL) {
        const body = JSON.parse(init?.body as string) as { username: string; password: string }
        if (body.username === USERNAME && body.password === PASSWORD) {
          return Promise.resolve(jsonResponse({ token: 'issued-token', username: body.username }))
        }
        return Promise.resolve(
          jsonResponse(
            {
              type: 'about:blank',
              title: 'Incorrect username or password.',
              status: 401,
              detail: null,
              code: 'authentication_error',
              correlation_id: null,
            },
            { status: 401 },
          ),
        )
      }
      if (input === FILTERS_URL) {
        return Promise.resolve(jsonResponse(EMPTY_FILTER_OPTIONS))
      }
      // Anything else the authenticated app asks for once signed in — left
      // as an error (rather than a bogus 200) so each screen's own "no data
      // yet" state renders instead of a handler crashing on a malformed body.
      return Promise.resolve(
        jsonResponse({ title: 'not mocked', status: 500, code: 'test_fallback' }, { status: 500 }),
      )
    }),
  )
}

function renderApp(): void {
  render(
    <AppProviders>
      <MemoryRouter initialEntries={['/exec']}>
        <App />
      </MemoryRouter>
    </AppProviders>,
  )
}

beforeEach(() => {
  // Overrides setup.ts's default pre-authenticated session: this file is
  // specifically about the unauthenticated-to-authenticated transition.
  localStorage.removeItem('nvx-session')
  setAuthToken(null)
  serve()
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  localStorage.clear()
  setAuthToken(null)
})

describe('signed out', () => {
  it('shows the login screen instead of any app route', () => {
    renderApp()

    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Screens' })).not.toBeInTheDocument()
  })

  it('signs in and shows the app on the correct credentials', async () => {
    const user = userEvent.setup()
    renderApp()

    await user.type(screen.getByLabelText('Username'), USERNAME)
    await user.type(screen.getByLabelText('Password'), PASSWORD)
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('navigation', { name: 'Screens' })).toBeInTheDocument()
  })

  it('persists the session so a reload stays signed in', async () => {
    const user = userEvent.setup()
    renderApp()

    await user.type(screen.getByLabelText('Username'), USERNAME)
    await user.type(screen.getByLabelText('Password'), PASSWORD)
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    await screen.findByRole('navigation', { name: 'Screens' })

    const stored = localStorage.getItem('nvx-session')
    expect(stored).not.toBeNull()
    expect(JSON.parse(stored as string)).toEqual({ token: 'issued-token', username: USERNAME })
  })

  it('shows the server message and clears the password on a wrong password', async () => {
    const user = userEvent.setup()
    renderApp()

    await user.type(screen.getByLabelText('Username'), USERNAME)
    await user.type(screen.getByLabelText('Password'), 'wrong-password')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect username or password.')
    expect(screen.getByLabelText('Password')).toHaveValue('')
    expect(screen.queryByRole('navigation', { name: 'Screens' })).not.toBeInTheDocument()
  })

  it('rejects a wrong username the same way as a wrong password', async () => {
    const user = userEvent.setup()
    renderApp()

    await user.type(screen.getByLabelText('Username'), 'someone-else')
    await user.type(screen.getByLabelText('Password'), PASSWORD)
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect username or password.')
  })
})

describe('signing out', () => {
  it('returns to the login screen and clears the stored session', async () => {
    const user = userEvent.setup()
    renderApp()

    await user.type(screen.getByLabelText('Username'), USERNAME)
    await user.type(screen.getByLabelText('Password'), PASSWORD)
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    const rail = await screen.findByRole('navigation', { name: 'Screens' })
    const foot = rail.parentElement as HTMLElement

    await user.click(within(foot).getByRole('button', { name: 'Sign out' }))

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    })
    expect(localStorage.getItem('nvx-session')).toBeNull()
  })
})
