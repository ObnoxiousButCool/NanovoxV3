/**
 * The drawer, tested for the stacking behaviour that is its whole point.
 *
 * A drawer that replaces its contents instead of stacking looks identical
 * until a reader goes two levels deep and finds Back has taken them out of
 * the drawer entirely. That is the failure this file exists to catch.
 *
 * What a call itself says is tested in `CallScreen.test.tsx` now, because a
 * call is a page. What the drawer still owns is the frame in front of it:
 * the list of calls behind a figure, and getting from one of them to the
 * page without leaving a dialog open over it.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createQueryClient } from '@/app/queryClient'
import { Drawer, DrawerProvider, useDrawer } from '@/shared/design/drawer'
import { CallList, EvidenceLink } from '@/shared/design/drawer/Evidence'

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
        open({
          title: 'Second frame',
          body: (
            <>
              <p>deepest</p>
              {/* Evidence has evidence: the second frame holds the calls
                  behind the first one's figure. */}
              <CallList callIds={['C-0042']} />
            </>
          ),
        })
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
        <MemoryRouter initialEntries={['/exec']}>
          {ui}
          <Drawer />
          <Routes>
            <Route path="/exec" element={null} />
            <Route path="/calls/:reference" element={<p>the call page</p>} />
          </Routes>
        </MemoryRouter>
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

  it('counts one in the singular', () => {
    setup(<CallList callIds={['C-0042']} />)

    expect(screen.getByText('One call is behind this figure.')).toBeInTheDocument()
  })

  it('opens a call as a page rather than another frame', async () => {
    const user = userEvent.setup()
    setup(<CallList callIds={['C-0042']} />)

    await user.click(screen.getByRole('button', { name: 'C-0042' }))

    expect(screen.getByText('the call page')).toBeInTheDocument()
  })

  it('closes the drawer on the way, so no dialog is left over the call', async () => {
    // The failure this catches is silent in the DOM and obvious on screen:
    // a modal backdrop over the page the reader just asked for.
    const user = userEvent.setup()
    setup()

    await user.click(screen.getByRole('button', { name: 'open evidence' }))
    await user.click(screen.getByRole('button', { name: 'go deeper' }))
    await user.click(screen.getByRole('button', { name: 'C-0042' }))

    expect(screen.getByText('the call page')).toBeInTheDocument()
    expect(screen.queryByText('First frame')).not.toBeInTheDocument()
    expect(screen.queryByText('Second frame')).not.toBeInTheDocument()
  })
})
