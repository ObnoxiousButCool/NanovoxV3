/**
 * The drawer, tested for the stacking behaviour that is its whole point.
 *
 * A drawer that replaces its contents instead of stacking looks identical
 * until a reader goes two levels deep and finds Back has taken them out of
 * the drawer entirely. That is the failure this file exists to catch.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createQueryClient } from '@/app/queryClient'
import { Drawer, DrawerProvider, useDrawer } from '@/shared/design/drawer'
import { CallList, EvidenceLink } from '@/shared/design/drawer/Evidence'

/** One call, as `GET /insights/calls/{reference}` returns it. */
const CALL = {
  reference: 'C-0042',
  callerType: 'MEMBER',
  callerRef: 'MEM-7',
  agentRef: 'AG-03',
  employerRef: 'EMP-1001',
  resolutionStatus: 'RESOLVED',
  resolutionReason: null,
  transcriptMissing: false,
  turns: [
    { sequence: 0, role: 'CALLER', text: 'I was billed twice for one visit.' },
    { sequence: 1, role: 'AGENT', text: 'I can see the duplicate and will correct it.' },
  ],
}

function serve(body: unknown, status = 200): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify(body), {
          status,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    ),
  )
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

function Opener() {
  const { open } = useDrawer()
  return (
    <button
      type="button"
      onClick={() => {
        open({ title: 'First frame', chip: 'observed', body: <Nested /> })
      }}
    >
      open evidence
    </button>
  )
}

function Nested() {
  const { open } = useDrawer()
  return (
    <button
      type="button"
      onClick={() => {
        open({ title: 'Second frame', body: <p>deepest</p> })
      }}
    >
      go deeper
    </button>
  )
}

function setup(ui: React.ReactNode = <Opener />) {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <DrawerProvider>
        {ui}
        <Drawer />
      </DrawerProvider>
    </QueryClientProvider>,
  )
}

describe('Drawer', () => {
  it('is closed until something opens it', () => {
    setup()

    expect(screen.queryByText('First frame')).not.toBeInTheDocument()
  })

  it('opens a frame', async () => {
    const user = userEvent.setup()
    setup()

    await user.click(screen.getByRole('button', { name: 'open evidence' }))

    expect(screen.getByText('First frame')).toBeInTheDocument()
  })

  it('offers no Back at the first frame', async () => {
    const user = userEvent.setup()
    setup()

    await user.click(screen.getByRole('button', { name: 'open evidence' }))

    expect(screen.queryByRole('button', { name: '← Back' })).not.toBeInTheDocument()
  })

  it('stacks rather than replacing, and Back returns to the previous frame', async () => {
    // The reason the drawer is a stack at all: evidence has evidence.
    const user = userEvent.setup()
    setup()

    await user.click(screen.getByRole('button', { name: 'open evidence' }))
    await user.click(screen.getByRole('button', { name: 'go deeper' }))
    expect(screen.getByText('Second frame')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '← Back' }))

    expect(screen.getByText('First frame')).toBeInTheDocument()
    expect(screen.queryByText('deepest')).not.toBeInTheDocument()
  })

  it('closes from depth rather than unwinding one frame at a time', async () => {
    const user = userEvent.setup()
    setup()

    await user.click(screen.getByRole('button', { name: 'open evidence' }))
    await user.click(screen.getByRole('button', { name: 'go deeper' }))
    await user.click(screen.getByRole('button', { name: 'Close' }))

    expect(screen.queryByText('Second frame')).not.toBeInTheDocument()
    expect(screen.queryByText('First frame')).not.toBeInTheDocument()
  })

  it('clears the stack when dismissed, so the next open starts fresh', async () => {
    // Otherwise the next open resumes halfway down a stack the reader
    // already dismissed, which looks like the app losing its place.
    const user = userEvent.setup()
    setup()

    await user.click(screen.getByRole('button', { name: 'open evidence' }))
    await user.click(screen.getByRole('button', { name: 'go deeper' }))
    await user.click(screen.getByRole('button', { name: 'Close' }))
    await user.click(screen.getByRole('button', { name: 'open evidence' }))

    expect(screen.getByText('First frame')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '← Back' })).not.toBeInTheDocument()
  })

  it('carries the epistemic class of the frame it is showing', async () => {
    const user = userEvent.setup()
    setup()

    await user.click(screen.getByRole('button', { name: 'open evidence' }))

    expect(screen.getByText('observed')).toBeInTheDocument()
  })
})

describe('EvidenceLink', () => {
  it('opens the calls behind a figure', async () => {
    const user = userEvent.setup()
    setup(<EvidenceLink callIds={['C-0001', 'C-0002']} title="Unresolved calls" />)

    await user.click(screen.getByRole('button', { name: '2 calls' }))

    expect(screen.getByText('Unresolved calls')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'C-0001' })).toBeInTheDocument()
  })

  it('renders nothing when a figure has no calls behind it', () => {
    // A link promising evidence that turns out to be empty is worse than
    // no link: the reader has to click to find out there is nothing.
    setup(<EvidenceLink callIds={[]} />)

    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('counts one call in the singular', () => {
    setup(<EvidenceLink callIds={['C-0001']} />)

    expect(screen.getByRole('button', { name: '1 call' })).toBeInTheDocument()
  })
})

describe('CallList', () => {
  it('says how many calls are behind the figure', () => {
    setup(<CallList callIds={['C-0001', 'C-0002', 'C-0003']} />)

    expect(screen.getByText('3 calls are behind this figure.')).toBeInTheDocument()
  })

  it('opens a call onto its turns', async () => {
    serve(CALL)
    const user = userEvent.setup()
    setup(<CallList callIds={['C-0042']} />)

    await user.click(screen.getByRole('button', { name: 'C-0042' }))

    await waitFor(() => {
      expect(screen.getByText('I was billed twice for one visit.')).toBeInTheDocument()
    })
    expect(screen.getByText('I can see the duplicate and will correct it.')).toBeInTheDocument()
  })

  it('shows the caller reference, never a member name', async () => {
    serve(CALL)
    const user = userEvent.setup()
    setup(<CallList callIds={['C-0042']} />)

    await user.click(screen.getByRole('button', { name: 'C-0042' }))

    await waitFor(() => {
      expect(screen.getByText(/MEM-7/)).toBeInTheDocument()
    })
  })

  it('says a call has no stored transcript rather than rendering nothing', async () => {
    // An empty evidence panel reads as "there is nothing behind this
    // figure", which is the opposite of true. A call with no turns is a
    // different statement from a call with nothing to say.
    serve({ ...CALL, transcriptMissing: true, turns: [] })
    const user = userEvent.setup()
    setup(<CallList callIds={['C-0042']} />)

    await user.click(screen.getByRole('button', { name: 'C-0042' }))

    await waitFor(() => {
      expect(screen.getByText(/no transcript stored for this call/i)).toBeInTheDocument()
    })
  })

  it('says what failed rather than failing silently', async () => {
    serve(
      {
        title: 'No such call in this corpus.',
        status: 404,
        code: 'not_found',
        correlation_id: null,
        detail: 'reference=C-0042',
      },
      404,
    )
    const user = userEvent.setup()
    setup(<CallList callIds={['C-0042']} />)

    await user.click(screen.getByRole('button', { name: 'C-0042' }))

    await waitFor(() => {
      expect(screen.getByText(/no such call in this corpus/i)).toBeInTheDocument()
    })
  })
})
