/**
 * The call page.
 *
 * Most of this file moved here from `drawer.test.tsx` unchanged, because
 * what a call says about itself did not change when it stopped being a
 * dialog — only where it says it. The assertions about layers that never
 * ran are the ones worth keeping closest: a panel that reports a call as
 * clean on the strength of never having looked at it is the single worst
 * thing this screen could do.
 *
 * What is new is the chrome. Back and Close make different promises, and
 * the one that can be false — Back, on a link somebody was sent — has to be
 * absent rather than wrong.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

/** What `MemoryRouter` takes: a path, or one carrying history state. */
type Entry = string | { pathname: string; search?: string; state?: unknown }
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createQueryClient } from '@/app/queryClient'
import { CallScreen } from '@/app/screens/CallScreen'
import { DrawerProvider } from '@/shared/design/drawer'
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

/** L1 to L4, as a fully analysed call has them. */
const ANALYSED = {
  ...CALL,
  analysis: {
    l1: {
      ran: true,
      callerRef: 'MEM-7',
      controlExceptions: [{ code: 'no_recording_disclosure', label: 'No recording disclosure' }],
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

/** The call page, reached the way a reader reaches it from the calls table. */
const FROM_CALLS: Entry[] = [
  { pathname: '/calls', search: '?page=3' },
  {
    pathname: '/calls/C-0042',
    state: { from: { pathname: '/calls', search: '?page=3' } },
  },
]

/** The same page opened cold, from a link somebody was sent. */
const DEEP_LINK: Entry[] = ['/calls/C-0042']

function setup(entries: Entry[] = FROM_CALLS) {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <DrawerProvider>
        <MemoryRouter initialEntries={entries} initialIndex={entries.length - 1}>
          <Routes>
            <Route path="/calls" element={<p>the calls table</p>} />
            <Route path="/calls/:reference" element={<CallScreen />} />
          </Routes>
        </MemoryRouter>
      </DrawerProvider>
    </QueryClientProvider>,
  )
}

async function loaded(body: unknown = ANALYSED, entries?: Entry[]) {
  serve(body)
  const user = userEvent.setup()
  setup(entries)
  await waitFor(() => {
    expect(screen.getByText(/what we made of this call/i)).toBeInTheDocument()
  })
  return user
}

describe('the call page', () => {
  it('names the call before the call has loaded', () => {
    // The chrome outlives the content: a reader waiting on a slow call is
    // still somewhere, with a way out.
    serve(CALL)
    setup()

    expect(screen.getByRole('heading', { name: 'Call C-0042' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument()
  })

  it('draws the page while it waits, not the word Loading', () => {
    serve(CALL)
    const { container } = setup()

    expect(container.querySelector('.nv-skel')).not.toBeNull()
    expect(screen.queryByText('Loading…')).not.toBeInTheDocument()
  })

  it('shows the turns', async () => {
    await loaded(CALL)

    expect(screen.getByText('I was billed twice for one visit.')).toBeInTheDocument()
    expect(screen.getByText('I can see the duplicate and will correct it.')).toBeInTheDocument()
  })

  it('shows the caller reference, never a member name', async () => {
    await loaded(CALL)

    expect(screen.getByText(/MEM-7/)).toBeInTheDocument()
  })

  it('says a call has no stored transcript rather than rendering nothing', async () => {
    // An empty conversation panel reads as "there is nothing behind this
    // figure", which is the opposite of true. A call with no turns is a
    // different statement from a call with nothing to say.
    await loaded({ ...CALL, transcriptMissing: true, turns: [] })

    expect(screen.getByText(/its conversation was not stored/i)).toBeInTheDocument()
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
    setup()

    await waitFor(() => {
      expect(screen.getByText(/no such call in this corpus/i)).toBeInTheDocument()
    })
    // And the way out survives the failure, which the dialog's error box
    // managed only because it was a dialog.
    expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument()
  })
})

describe('getting back out', () => {
  it('names the screen the call was opened from', async () => {
    await loaded()

    expect(screen.getByRole('button', { name: /← Back to All calls/ })).toBeInTheDocument()
  })

  it('returns to that screen, in the state it was in', async () => {
    const user = await loaded()

    await user.click(screen.getByRole('button', { name: /← Back to All calls/ }))

    expect(screen.getByText('the calls table')).toBeInTheDocument()
  })

  it('offers no Back on a link somebody was sent', async () => {
    // There is no history to return to, and a Back that leaves the
    // application is worse than no Back at all.
    await loaded(ANALYSED, DEEP_LINK)

    expect(screen.queryByRole('button', { name: /Back/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument()
  })

  it('offers no Back when history state is not ours', async () => {
    await loaded(ANALYSED, [{ pathname: '/calls/C-0042', state: { from: 'somewhere' } }])

    expect(screen.queryByRole('button', { name: /Back/ })).not.toBeInTheDocument()
  })

  it('closes to the full list, which works from anywhere', async () => {
    const user = await loaded(ANALYSED, DEEP_LINK)

    await user.click(screen.getByRole('button', { name: 'Close' }))

    expect(screen.getByText('the calls table')).toBeInTheDocument()
  })

  it('still answers Escape, because a year of the dialog taught that reflex', async () => {
    const user = await loaded()

    await user.keyboard('{Escape}')

    expect(screen.getByText('the calls table')).toBeInTheDocument()
  })
})

describe('the verdict band', () => {
  /** L2 warranted an escalation; what L4 says about it is the variable. */
  const ESCALATED = {
    ...ANALYSED,
    analysis: {
      ...ANALYSED.analysis,
      l2: { ...ANALYSED.analysis.l2, escalationTriggered: true, complaintPresent: true },
    },
  }

  function withL4(l4: Record<string, unknown>) {
    return { ...ESCALATED, analysis: { ...ESCALATED.analysis, l4 } }
  }

  it('leads with the summary sentence', async () => {
    await loaded()

    expect(screen.getByText('Billed twice for one visit.')).toBeInTheDocument()
  })

  it('prints that sentence once, not once here and once in L2', async () => {
    // It was moved out of the L2 panel rather than copied. One finding
    // printed twice on one screen reads as two.
    await loaded()

    expect(screen.getAllByText('Billed twice for one visit.')).toHaveLength(1)
  })

  it('shows the outcome and the score without opening a panel', async () => {
    await loaded()

    const band = screen.getByLabelText('What happened on this call')
    expect(within(band).getByText('Resolved')).toBeInTheDocument()
    expect(within(band).getByText('74')).toBeInTheDocument()
    // Provisional is "not final", a different thing from a low score.
    expect(within(band).getByText('Provisional')).toBeInTheDocument()
  })

  it('calls an escalation missed when L4 ran and says it was not handled', async () => {
    await loaded(withL4({ ran: true, escalationHandled: false, signals: [] }))

    expect(screen.getByText('Escalation missed')).toBeInTheDocument()
  })

  it('does not call an escalation missed when L4 never looked', async () => {
    // The whole reason this band is gated. `escalationTriggered &&
    // !escalationHandled` is true on a call L4 never ran on, and reporting
    // that as a miss is a finding against an agent nobody checked.
    await loaded(withL4({ ran: false, notRunBecause: 'Not run.', signals: [] }))

    expect(screen.queryByText('Escalation missed')).not.toBeInTheDocument()
    expect(
      screen.getByText('Escalation warranted — handling not checked'),
    ).toBeInTheDocument()
  })

  it('says a concern once when the fields and the signals both raise it', async () => {
    // The structured L2/L4 fields say the escalation was missed and the
    // signal taxonomy raises a signal of the same name, so both arrive.
    await loaded(
      withL4({
        ran: true,
        escalationHandled: false,
        signals: [
          {
            type: { code: 'escalation_missed', label: 'Escalation missed' },
            severity: { code: 'HIGH', label: 'High' },
            quote: 'I want a supervisor.',
            turnSeq: 4,
          },
        ],
      }),
    )

    // Scoped to the band: the L4 panel below still shows the signal with
    // its quote and turn, which is the point of having both.
    const band = screen.getByLabelText('What happened on this call')
    expect(within(band).getAllByText('Escalation missed')).toHaveLength(1)
    expect(screen.getAllByText('Escalation missed').length).toBeGreaterThan(1)
  })

  it('never reports a call with unrun layers as clean', async () => {
    // "Nothing flagged" over a pipeline that did not finish is a clean bill
    // of health nobody issued.
    await loaded({ ...CALL, analysis: unrunAnalysis('MEM-7') })

    expect(screen.queryByText('Nothing flagged on this call.')).not.toBeInTheDocument()
    expect(screen.getByText(/it is an unfinished one/)).toBeInTheDocument()
  })

  it('says a figure is missing rather than showing a zero', async () => {
    await loaded({ ...CALL, analysis: unrunAnalysis('MEM-7') })

    const band = screen.getByLabelText('What happened on this call')
    expect(within(band).getByText('Not scored')).toBeInTheDocument()
    expect(within(band).queryByText('0')).not.toBeInTheDocument()
  })
})

describe("a call's panels", () => {
  it('offers one panel per layer, and the conversation beside them', async () => {
    await loaded()

    expect(screen.getByText(/L1 — Deterministic extraction/)).toBeInTheDocument()
    expect(screen.getByText(/L2 — Classification/)).toBeInTheDocument()
    expect(screen.getByText(/L3 — Quality & knowledge/)).toBeInTheDocument()
    expect(screen.getByText(/L4 — Signals & gaps/)).toBeInTheDocument()
    // The transcript is a panel of the same kind, not a heading and a list:
    // it is one more named part of what we hold about this call.
    expect(screen.getByText('The conversation')).toBeInTheDocument()
  })

  it('says a layer has not run rather than reporting a clean call', async () => {
    // The single most important assertion in this panel set. "No signals
    // raised" for a layer that never ran reports a call as clean on the
    // strength of never having looked at it.
    const user = await loaded()

    expect(screen.getByText('Not run')).toBeInTheDocument()
    await user.click(screen.getByText(/L4 — Signals & gaps/))

    expect(screen.getByText(/has not run on this call/i)).toBeInTheDocument()
    expect(screen.queryByText(/raised no signal/i)).not.toBeInTheDocument()
  })

  it('does not attribute a knowledge failure to the agent', async () => {
    // D7, open with Karim. Schema field 8 is the rule stated wrongly and is
    // organisational; the agent-conduct event is the separate L4 signal.
    // Nothing in code may reconcile the two, so the panel says whose it is.
    const user = await loaded()

    await user.click(screen.getByText(/L3 — Quality & knowledge/))

    expect(screen.getByText(/not attributed to the agent/i)).toBeInTheDocument()
  })

  it('names no provider or model, now that the run footer is gone', async () => {
    // Plan §7 keeps provenance on every analysis in the database and on the
    // wire — `run` is still in this fixture and still in the response. What
    // was removed is the line that printed it. The rule it was carrying,
    // that no screen names a vendor, is the one that must not lapse with it.
    await loaded()

    expect(screen.queryByText(/openai|gpt-test/)).not.toBeInTheDocument()
    expect(screen.queryByText(/^prompt 1\.0\.0/)).not.toBeInTheDocument()
  })

  it('tells the layers apart in words, not only by accent colour', async () => {
    // The "Code" / "Model" / "Source" badges were removed on request. The
    // titles and subtitles carry the same distinction, and a reader who
    // cannot separate the accents has to keep getting it from somewhere.
    await loaded()

    expect(screen.queryByText('Code')).not.toBeInTheDocument()
    expect(screen.queryByText('Source')).not.toBeInTheDocument()
    expect(
      screen.getByText(/No model, and the same transcript always gives the same answer/),
    ).toBeInTheDocument()
  })

  it('renders every panel for a call nothing has run on', async () => {
    await loaded({ ...CALL, analysis: unrunAnalysis('MEM-7') })

    expect(screen.getAllByText('Not run')).toHaveLength(4)
    // L1 and L2 share the sentence: L1 is written in the same transaction,
    // so there is no state where one has run and the other has not.
    expect(screen.getAllByText(/pipeline has not run on this call/i)).toHaveLength(2)
  })
})
