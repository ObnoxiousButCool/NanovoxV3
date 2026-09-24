/**
 * The drawer, tested for the stacking behaviour that is its whole point.
 *
 * A drawer that replaces its contents instead of stacking looks identical
 * until a reader goes two levels deep and finds Back has taken them out of
 * the drawer entirely. That is the failure this file exists to catch.
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { Drawer, DrawerProvider, useDrawer } from '@/shared/design/drawer'
import { CallList, EvidenceLink } from '@/shared/design/drawer/Evidence'

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
    <DrawerProvider>
      {ui}
      <Drawer />
    </DrawerProvider>,
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

  it('says the call view is unbuilt rather than rendering an empty shell', async () => {
    // An empty evidence panel reads as "there is nothing behind this
    // figure", which is the opposite of true.
    const user = userEvent.setup()
    setup(<CallList callIds={['C-0042']} />)

    await user.click(screen.getByRole('button', { name: 'C-0042' }))

    expect(screen.getByText(/arrives in Phase 3/)).toBeInTheDocument()
  })
})
