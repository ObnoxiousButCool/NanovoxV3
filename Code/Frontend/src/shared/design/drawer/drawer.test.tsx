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
import { unrunAnalysis } from '@/shared/design/drawer/analysisFixture'

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
  analysis: unrunAnalysis('MEM-7'),
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
      expect(screen.getByText(/its conversation was not stored/i)).toBeInTheDocument()
    })
    // "No transcript", not "Not run": nothing ran or failed to run on the
    // conversation. What is missing is the recording, not an analysis.
    expect(screen.getByText('No transcript')).toBeInTheDocument()
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

describe("a call's panels", () => {
  /** L1 to L4, as a fully analysed call has them. */
  const ANALYSED = {
    ...CALL,
    analysis: {
      l1: {
        ran: true,
        callerRef: 'MEM-7',
        controlExceptions: [
          { code: 'no_recording_disclosure', label: 'No recording disclosure' },
        ],
      },
      l2: {
        ran: true,
        run: {
          provider: 'openai',
          model: 'gpt-test',
          promptVersion: '1.0.0',
          completedAt: '2026-09-20T10:05:00Z',
        },
        outcome: { code: 'RESOLVED', label: 'Resolved' },
        category: 'Claims & EOB',
        productLines: [{ code: 'chiro', label: 'Chiropractic' }],
        complaintPresent: false,
        intent: [],
        secondaryIssues: [],
        summary: 'Billed twice for one visit.',
      },
      l3: {
        ran: true,
        qualityScore: 74,
        qualityStatus: { code: 'provisional', label: 'Provisional — not final' },
        qualityTier: { code: 'AVERAGE', label: 'Average' },
        markers: [],
        knowledgeFailurePresent: true,
        knowledgeFailureRuleId: 'P-18',
      },
      l4: {
        ran: false,
        notRunBecause:
          'This layer has not run on this call. It is not required for a call to ' +
          'have an analysis, so the other panels still stand.',
        signals: [],
      },
    },
  }

  async function openAnalysed(body: unknown = ANALYSED) {
    serve(body)
    const user = userEvent.setup()
    setup(<CallList callIds={['C-0042']} />)
    await user.click(screen.getByRole('button', { name: 'C-0042' }))
    await waitFor(() => {
      expect(screen.getByText(/what we made of this call/i)).toBeInTheDocument()
    })
    return user
  }

  it('offers one panel per layer, and the conversation beside them', async () => {
    await openAnalysed()

    expect(screen.getByText(/L1 — Deterministic extraction/)).toBeInTheDocument()
    expect(screen.getByText(/L2 — Classification/)).toBeInTheDocument()
    expect(screen.getByText(/L3 — Quality & knowledge/)).toBeInTheDocument()
    expect(screen.getByText(/L4 — Signals & gaps/)).toBeInTheDocument()
    // The transcript is a panel of the same kind, not a heading and a list:
    // it is one more named part of what we hold about this call.
    expect(screen.getByText('The conversation')).toBeInTheDocument()
  })

  it('names each panel’s producer in words, not only in colour', async () => {
    // The accent colours carry the same distinction, and a reader who
    // cannot separate them would otherwise lose it entirely. `StatusPill`
    // makes the same argument in the design system: shape, not only colour.
    await openAnalysed()

    expect(screen.getAllByText('Code')).toHaveLength(1)
    expect(screen.getAllByText('Model')).toHaveLength(3)
    // The transcript is neither computed nor inferred. Calling it "Code" to
    // avoid a third badge would say the conversation was calculated.
    expect(screen.getAllByText('Source')).toHaveLength(1)
  })

  it('says a layer has not run rather than reporting a clean call', async () => {
    // The single most important assertion in this panel set. "No signals
    // raised" for a layer that never ran reports a call as clean on the
    // strength of never having looked at it.
    const user = await openAnalysed()

    expect(screen.getByText('Not run')).toBeInTheDocument()
    await user.click(screen.getByText(/L4 — Signals & gaps/))

    expect(screen.getByText(/has not run on this call/i)).toBeInTheDocument()
    expect(screen.queryByText(/raised no signal/i)).not.toBeInTheDocument()
  })

  it('does not attribute a knowledge failure to the agent', async () => {
    // D7, open with Karim. Schema field 8 is the rule stated wrongly and is
    // organisational; the agent-conduct event is the separate L4 signal.
    // Nothing in code may reconcile the two, so the panel says whose it is.
    const user = await openAnalysed()

    await user.click(screen.getByText(/L3 — Quality & knowledge/))

    expect(screen.getByText(/not attributed to the agent/i)).toBeInTheDocument()
  })

  it('shows which run produced a layer, and when, without naming the vendor', async () => {
    // Plan §7 requires provenance on every analysis; the page names no
    // provider or model anywhere.
    await openAnalysed()

    expect(screen.getAllByText(/^prompt 1\.0\.0/).length).toBeGreaterThan(0)
    expect(screen.queryByText(/openai|gpt-test/)).not.toBeInTheDocument()
  })

  it('renders every panel for a call nothing has run on', async () => {
    await openAnalysed({ ...CALL, analysis: unrunAnalysis('MEM-7') })

    expect(screen.getAllByText('Not run')).toHaveLength(4)
    // L1 and L2 share the sentence: L1 is written in the same transaction,
    // so there is no state where one has run and the other has not.
    expect(screen.getAllByText(/pipeline has not run on this call/i)).toHaveLength(2)
  })
})
