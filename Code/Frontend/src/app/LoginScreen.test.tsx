/**
 * The email-OTP sign-in flow, end to end through the UI
 * (feature/email-otp-login, not on main).
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

const REQUEST_URL = 'http://api.test/api/v1/auth/otp/request'
const VERIFY_URL = 'http://api.test/api/v1/auth/otp/verify'
const FILTERS_URL = 'http://api.test/api/v1/insights/filters'

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

function serve(verify: (body: { email: string; code: string }) => Response): void {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: string, init?: RequestInit) => {
      if (input === REQUEST_URL) {
        return Promise.resolve(jsonResponse({ message: 'If that address is approved…' }))
      }
      if (input === VERIFY_URL) {
        const body = JSON.parse(init?.body as string) as { email: string; code: string }
        return Promise.resolve(verify(body))
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
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  localStorage.clear()
  setAuthToken(null)
})

describe('signed out', () => {
  it('shows the login screen instead of any app route', () => {
    serve(() => jsonResponse({}))
    renderApp()

    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Screens' })).not.toBeInTheDocument()
  })

  it('moves to the code step after requesting one', async () => {
    serve(() => jsonResponse({}))
    const user = userEvent.setup()
    renderApp()

    await user.type(screen.getByLabelText('Email'), 'reader@example.com')
    await user.click(screen.getByRole('button', { name: 'Send code' }))

    expect(await screen.findByRole('heading', { name: 'Enter your code' })).toBeInTheDocument()
    expect(screen.getByText('reader@example.com')).toBeInTheDocument()
  })

  it('signs in and shows the app on a correct code', async () => {
    serve((body) =>
      jsonResponse({ token: 'issued-token', email: body.email }),
    )
    const user = userEvent.setup()
    renderApp()

    await user.type(screen.getByLabelText('Email'), 'reader@example.com')
    await user.click(screen.getByRole('button', { name: 'Send code' }))
    await user.type(await screen.findByLabelText('Code'), '123456')
    await user.click(screen.getByRole('button', { name: 'Verify' }))

    expect(await screen.findByRole('navigation', { name: 'Screens' })).toBeInTheDocument()
  })

  it('persists the session so a reload stays signed in', async () => {
    serve((body) => jsonResponse({ token: 'issued-token', email: body.email }))
    const user = userEvent.setup()
    renderApp()

    await user.type(screen.getByLabelText('Email'), 'reader@example.com')
    await user.click(screen.getByRole('button', { name: 'Send code' }))
    await user.type(await screen.findByLabelText('Code'), '123456')
    await user.click(screen.getByRole('button', { name: 'Verify' }))
    await screen.findByRole('navigation', { name: 'Screens' })

    const stored = localStorage.getItem('nvx-session')
    expect(stored).not.toBeNull()
    expect(JSON.parse(stored as string)).toEqual({
      token: 'issued-token',
      email: 'reader@example.com',
    })
  })

  it('shows the server message and stays on the code step for a wrong code', async () => {
    serve(() =>
      jsonResponse(
        { type: 'about:blank', title: 'That code is not valid.', status: 401, detail: null, code: 'authentication_error', correlation_id: null },
        { status: 401 },
      ),
    )
    const user = userEvent.setup()
    renderApp()

    await user.type(screen.getByLabelText('Email'), 'reader@example.com')
    await user.click(screen.getByRole('button', { name: 'Send code' }))
    await user.type(await screen.findByLabelText('Code'), '000000')
    await user.click(screen.getByRole('button', { name: 'Verify' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('That code is not valid.')
    expect(screen.getByRole('heading', { name: 'Enter your code' })).toBeInTheDocument()
  })

  it('returns to the email step on request', async () => {
    serve(() => jsonResponse({}))
    const user = userEvent.setup()
    renderApp()

    await user.type(screen.getByLabelText('Email'), 'reader@example.com')
    await user.click(screen.getByRole('button', { name: 'Send code' }))
    await screen.findByRole('heading', { name: 'Enter your code' })

    await user.click(screen.getByRole('button', { name: 'Use a different email' }))

    // The address is left in the field rather than cleared — a reader
    // fixing a typo should not have to retype the whole thing.
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toHaveValue('reader@example.com')
  })
})

describe('signing out', () => {
  it('returns to the login screen and clears the stored session', async () => {
    serve((body) => jsonResponse({ token: 'issued-token', email: body.email }))
    const user = userEvent.setup()
    renderApp()

    await user.type(screen.getByLabelText('Email'), 'reader@example.com')
    await user.click(screen.getByRole('button', { name: 'Send code' }))
    await user.type(await screen.findByLabelText('Code'), '123456')
    await user.click(screen.getByRole('button', { name: 'Verify' }))
    const rail = await screen.findByRole('navigation', { name: 'Screens' })
    const foot = rail.parentElement as HTMLElement

    await user.click(within(foot).getByRole('button', { name: 'Sign out' }))

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    })
    expect(localStorage.getItem('nvx-session')).toBeNull()
  })
})
