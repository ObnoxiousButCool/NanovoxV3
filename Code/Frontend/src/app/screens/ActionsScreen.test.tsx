/**
 * `/actions` end to end against a mocked server.
 *
 * The lane list here is deliberately **not** the prototype's seven codes —
 * `triage` / `in_hand` / `resolved` rather than `needs_action` / `assigned` /
 * … / `completed`. If anything in the screen or its components hardcoded a
 * lane's code, these tests would fail on that alone, which is the point:
 * the board must draw whatever `GET /insights/actions/board` sends.
 *
 * A stateful fetch mock stands in for the server: PATCH and POST mutate an
 * in-memory store, and the next GET reads it back, so "ticking a step calls
 * PATCH and the UI reflects it" is one real round trip rather than an
 * assertion on a mock call alone.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from '@/app/App'
import { createQueryClient } from '@/app/queryClient'
import { DrawerProvider } from '@/shared/design/drawer'
import { ThemeProvider } from '@/shared/design/ThemeProvider'

const SCOPE = {
  considered: 40,
  matched: 40,
  excludedCalls: 0,
  sources: ['CORPUS_PDF'],
  appliedFilters: [],
  caveats: [],
  unmeasurable: [],
  corpusPeriod: { from: '2026-07-06', to: '2026-09-21' },
  period: null,
}

const OPTIONS = {
  regions: [],
  brokers: [],
  employers: [{ ref: 'EMP-1001', name: 'Cedar Point Workforce Partners' }],
  agentRefs: [],
  touchpoints: [],
  signals: [],
  complaintTargets: [],
  outcomes: [],
  categories: [],
  productLines: [],
  intents: [],
  qualityBands: [],
  corpusPeriod: { from: '2026-07-06', to: '2026-09-21' },
  unlabelledFilters: [],
}

const FINDINGS = {
  scope: SCOPE,
  asOf: '2026-09-21',
  windowWeeks: 12,
  items: [
    {
      signal: { code: 'unresolved', label: 'Unresolved calls' },
      severity: { code: 'HIGH', label: 'High' },
      ownerTeam: 'Operations',
      calls: 3,
      callIds: ['C-0001', 'C-0002', 'C-0003'],
    },
    {
      signal: { code: 'escalation_missed', label: 'Escalations missed' },
      severity: { code: 'CRITICAL', label: 'Critical' },
      ownerTeam: 'Operations',
      calls: 1,
      callIds: ['C-0009'],
    },
    {
      // Not one of the frontend's fourteen static issue keys — a dynamic
      // touchpoint key, which the row renders without a link.
      signal: { code: 'tp_denial_letter_eob', label: 'Denial letter EOB' },
      severity: { code: 'LOW', label: 'Low' },
      ownerTeam: 'Claims Operations',
      calls: 2,
      callIds: ['C-0020', 'C-0021'],
    },
  ],
  owners: [
    {
      ownerTeam: 'Operations',
      critical: 1,
      calls: 4,
      items: [],
    },
  ],
  controlExceptions: [
    {
      exceptionType: { code: 'recording_disclosure', label: 'Recording disclosure' },
      figure: {
        value: 0.1,
        published: true,
        n: 40,
        callIds: [],
        basis: { code: 'OBSERVED', label: 'Observed' },
        withheldReason: null,
        caveats: ['A floor on the true rate.'],
      },
    },
  ],
  controlDenominatorCaveat: 'The Metrics sheet has no field for calls requiring the control.',
  didItWork: {
    insight: 22,
    question: 'Did the fix work?',
    why: 'A comparable second batch does not exist yet.',
    unlockedBy: 'A second batch of calls after the fix.',
  },
}

const PLAYBOOK_UNRESOLVED = {
  key: 'unresolved',
  label: 'Unresolved calls',
  unit: 'calls',
  ownerTeam: 'Operations',
  severity: 'high',
  meaning: 'The caller ended the call in the same position they started.',
  why: 'Unresolved calls come back as repeat contacts and complaints.',
  steps: ['Call each member back within two working days.', 'Tag the root cause on each call.'],
  source: 'process_gap',
  dynamic: false,
  claim: 'recommendation',
  reviewed: false,
}

const LANES = [
  { code: 'triage', label: 'Triage', open: true, requires: [] },
  { code: 'in_hand', label: 'In hand', open: true, requires: [] },
  { code: 'monitoring', label: 'Monitoring', open: false, requires: ['measurement_window'] },
  { code: 'resolved', label: 'Resolved', open: false, requires: ['action_taken', 'outcome'] },
]

function makeAction(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    reference: 'ACT-001',
    title: 'Call back the unresolved members',
    sourceKind: 'process_gap',
    sourceDetail: null,
    issueKey: 'unresolved',
    evidence: 'Three calls ended unresolved this period.',
    recommendation: { text: 'Start with the members who called more than once.', claim: 'recommendation' },
    ownerTeam: 'Operations',
    owner: 'Alex Kim',
    priority: 'high',
    status: 'triage',
    statusLabel: 'Triage',
    pastDue: false,
    employerRef: 'EMP-1001',
    brokerRef: null,
    callIds: ['C-0001', 'C-0002'],
    steps: [
      { text: 'Call each member back within two working days.', done: false },
      { text: 'Tag the root cause on each call.', done: false },
    ],
    log: [{ at: '2026-09-20T10:00:00Z', text: 'Card created' }],
    createdAt: '2026-09-20T10:00:00Z',
    assignedOn: '2026-09-20',
    due: '2026-10-01',
    actionTaken: null,
    outcome: null,
    measurementWindow: null,
    ...overrides,
  }
}

interface Store {
  actions: Record<string, unknown>[]
  nextId: number
  failNextCreate?: boolean
}

let store: Store

function resetStore(): void {
  store = { actions: [makeAction()], nextId: 2 }
}

function laneLabel(code: string): string {
  return LANES.find((lane) => lane.code === code)?.label ?? code
}

function applyPatch(action: Record<string, unknown>, body: Record<string, unknown>): void {
  if (typeof body.status === 'string') {
    action.status = body.status
    action.statusLabel = laneLabel(body.status)
  }
  if (body.clearOwner) action.owner = null
  else if (typeof body.owner === 'string') action.owner = body.owner
  if (body.clearDue) action.due = null
  else if (typeof body.due === 'string') action.due = body.due
  if (typeof body.actionTaken === 'string') action.actionTaken = body.actionTaken
  if (typeof body.outcome === 'string') action.outcome = body.outcome
  if (body.measurementWindow) action.measurementWindow = body.measurementWindow
  if (Array.isArray(body.ticks)) {
    const steps = action.steps as { text: string; done: boolean }[]
    for (const tick of body.ticks as { index: number; done: boolean }[]) {
      const step = steps[tick.index]
      if (step) step.done = tick.done
    }
  }
  if (typeof body.note === 'string') {
    ;(action.log as { at: string; text: string }[]).push({
      at: new Date().toISOString(),
      text: body.note,
    })
  }
}

function handle(url: string, init?: RequestInit): unknown {
  const method = (init?.method ?? 'GET').toUpperCase()
  const path = url.replace('http://api.test/api/v1', '')

  if (path.startsWith('/insights/filters')) return OPTIONS
  if (path.startsWith('/insights/playbooks/unresolved')) return PLAYBOOK_UNRESOLVED
  if (path.startsWith('/insights/playbooks/')) {
    return { title: 'No playbook for this key.', status: 404, code: 'not_found', correlation_id: null, detail: null }
  }
  if (path === '/insights/actions/board' && method === 'GET') {
    return { lanes: LANES, actions: store.actions, trustNote: 'There is no sign-in; anyone who can reach this can edit it.' }
  }
  const patchMatch = /^\/insights\/actions\/(\d+)$/.exec(path)
  if (patchMatch && method === 'PATCH') {
    const id = Number(patchMatch[1])
    const action = store.actions.find((a) => a.id === id)
    if (!action) {
      return { title: 'No such action.', status: 404, code: 'not_found', correlation_id: null, detail: null }
    }
    const body = JSON.parse(init?.body as string) as Record<string, unknown>
    applyPatch(action, body)
    return action
  }
  if (patchMatch && method === 'GET') {
    return store.actions.find((a) => a.id === Number(patchMatch[1])) ?? {}
  }
  if (path === '/insights/actions' && method === 'POST') {
    if (store.failNextCreate) {
      store.failNextCreate = false
      return {
        title: 'A title is required.',
        status: 422,
        code: 'validation_error',
        correlation_id: null,
        detail: 'title',
      }
    }
    const body = JSON.parse(init?.body as string) as Record<string, unknown>
    const status = typeof body.status === 'string' ? body.status : 'triage'
    const created = makeAction({
      id: store.nextId,
      reference: `ACT-${String(100 + store.nextId)}`,
      title: body.title,
      issueKey: body.issueKey ?? null,
      evidence: body.evidence ?? '',
      recommendation: null,
      ownerTeam: body.ownerTeam ?? 'Operations',
      owner: body.owner ?? null,
      priority: body.priority ?? 'medium',
      status,
      statusLabel: laneLabel(status),
      due: body.due ?? null,
      callIds: body.callIds ?? [],
      steps: ((body.steps as string[] | undefined) ?? []).map((text) => ({ text, done: false })),
      log: [{ at: new Date().toISOString(), text: 'Card created' }],
      actionTaken: null,
      outcome: null,
    })
    store.nextId += 1
    store.actions = [created, ...store.actions]
    return created
  }
  if (path.startsWith('/insights/actions')) return FINDINGS
  if (path.startsWith('/insights/calls/')) {
    return {
      reference: 'C-0001',
      callerType: 'MEMBER',
      callerRef: 'MEM-1',
      agentRef: 'AG-01',
      employerRef: 'EMP-1001',
      resolutionStatus: 'UNRESOLVED',
      resolutionReason: null,
      transcriptMissing: false,
      turns: [],
    }
  }
  return {}
}

function serve(): void {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: string, init?: RequestInit) => {
      const status = init?.method === 'POST' ? 201 : 200
      const body = handle(input, init)
      const isProblem =
        typeof body === 'object' && body !== null && 'code' in (body as Record<string, unknown>) &&
        (body as Record<string, unknown>).status !== undefined &&
        typeof (body as Record<string, unknown>).status === 'number'
      return Promise.resolve(
        new Response(JSON.stringify(body), {
          status: isProblem ? ((body as { status: number }).status) : status,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    }),
  )
}

function renderAt(path: string): void {
  render(
    <QueryClientProvider client={createQueryClient()}>
      <ThemeProvider>
        <DrawerProvider>
          <MemoryRouter initialEntries={[path]}>
            <App />
          </MemoryRouter>
        </DrawerProvider>
      </ThemeProvider>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  resetStore()
  serve()
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('the action board', () => {
  it('draws the lanes the server sent, not a hardcoded seven', async () => {
    renderAt('/actions')

    await waitFor(() => {
      expect(screen.getAllByText('Triage').length).toBeGreaterThan(0)
    })
    expect(screen.getAllByText('In hand').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Resolved').length).toBeGreaterThan(0)
    // None of the prototype's own lane labels leaked in from a hardcoded list.
    expect(screen.queryByText('Needs action')).not.toBeInTheDocument()
    expect(screen.queryByText('Completed')).not.toBeInTheDocument()
  })

  it('opens the card modal with the card’s own detail on a click', async () => {
    const user = userEvent.setup()
    renderAt('/actions')

    await waitFor(() => {
      expect(screen.getByText('Call back the unresolved members')).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /Call back the unresolved members/ }))

    await waitFor(() => {
      expect(screen.getByText('Three calls ended unresolved this period.')).toBeInTheDocument()
    })
    // Appears twice on purpose: once as the "next step" banner, once as the
    // first checklist row.
    expect(screen.getAllByText('Call each member back within two working days.').length).toBeGreaterThan(0)
    expect(screen.getByText('Tag the root cause on each call.')).toBeInTheDocument()
  })

  it('ticks a checklist step through PATCH, and the board reflects it', async () => {
    const user = userEvent.setup()
    renderAt('/actions')

    await waitFor(() => {
      expect(screen.getByText('Call back the unresolved members')).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /Call back the unresolved members/ }))

    await waitFor(() => {
      expect(screen.getByText('0/2')).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: 'Mark step done' }))

    await waitFor(() => {
      expect(screen.getByText('1/2')).toBeInTheDocument()
    })
    expect(store.actions[0]?.steps).toEqual([
      { text: 'Call each member back within two working days.', done: true },
      { text: 'Tag the root cause on each call.', done: false },
    ])
  })

  it('moves a card to another lane through PATCH', async () => {
    const user = userEvent.setup()
    renderAt('/actions')

    await waitFor(() => {
      expect(screen.getByText('Call back the unresolved members')).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /Call back the unresolved members/ }))

    await waitFor(() => {
      // The Move-to button's accessible name is exactly the lane label; the
      // stage-strip button beside it also says "In hand" but always with a
      // trailing count, so the exact match is the one inside the card.
      expect(screen.getByRole('button', { name: 'In hand' })).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: 'In hand' }))

    await waitFor(() => {
      expect(store.actions[0]?.status).toBe('in_hand')
    })
    await waitFor(() => {
      expect(screen.getAllByText('In hand').length).toBeGreaterThan(0)
    })
  })

  it('records action taken and an outcome, each its own PATCH', async () => {
    // All steps already done, so the card is ready for "what was done".
    store.actions = [
      makeAction({
        steps: [
          { text: 'Call each member back within two working days.', done: true },
          { text: 'Tag the root cause on each call.', done: true },
        ],
      }),
    ]
    const user = userEvent.setup()
    renderAt('/actions')

    await waitFor(() => {
      expect(screen.getByText('Call back the unresolved members')).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /Call back the unresolved members/ }))

    await waitFor(() => {
      expect(screen.getByText('All steps are done. Record what was done.')).toBeInTheDocument()
    })
    await user.type(
      screen.getByPlaceholderText(/Called the member back/i),
      'Called every member back and closed the query.',
    )
    await user.click(screen.getByRole('button', { name: 'Save and mark action taken' }))

    await waitFor(() => {
      expect(store.actions[0]?.actionTaken).toBe('Called every member back and closed the query.')
    })

    await waitFor(() => {
      expect(screen.getByText('Measure the effect, then record the outcome.')).toBeInTheDocument()
    })
    await user.type(
      screen.getByPlaceholderText(/No repeat contact/i),
      'No repeat contact on this topic for four weeks.',
    )
    // The measurement window, alongside the outcome — a lane requiring it
    // (Monitoring, in this fixture) reads that back rather than a hardcoded
    // field name.
    await user.type(screen.getByLabelText('Measurement window start'), '2026-09-01')
    await user.type(screen.getByLabelText('Measurement window end'), '2026-09-28')
    await user.click(screen.getByRole('button', { name: 'Save outcome' }))

    await waitFor(() => {
      expect(store.actions[0]?.outcome).toBe('No repeat contact on this topic for four weeks.')
    })
    expect(store.actions[0]?.measurementWindow).toEqual({ start: '2026-09-01', end: '2026-09-28' })
  })

  it('disables a Move-to lane until the action carries what it requires', async () => {
    const user = userEvent.setup()
    renderAt('/actions')

    await waitFor(() => {
      expect(screen.getByText('Call back the unresolved members')).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /Call back the unresolved members/ }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Monitoring' })).toBeInTheDocument()
    })
    const monitoring = screen.getByRole('button', { name: 'Monitoring' })
    expect(monitoring).toBeDisabled()
    expect(monitoring).toHaveAttribute('title', expect.stringContaining('measurement window'))
  })

  it('logs an activity update and saves the owner and due date, each its own PATCH', async () => {
    const user = userEvent.setup()
    renderAt('/actions')

    await waitFor(() => {
      expect(screen.getByText('Call back the unresolved members')).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /Call back the unresolved members/ }))

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Spoke to the employer/i)).toBeInTheDocument()
    })
    await user.type(screen.getByPlaceholderText(/Spoke to the employer/i), 'Waiting on HR to confirm.')
    await user.click(screen.getByRole('button', { name: 'Save update' }))

    await waitFor(() => {
      expect(
        (store.actions[0]?.log as { text: string }[]).some(
          (entry) => entry.text === 'Waiting on HR to confirm.',
        ),
      ).toBe(true)
    })

    await user.clear(screen.getByPlaceholderText('Assign someone'))
    await user.type(screen.getByPlaceholderText('Assign someone'), 'Jordan Lee')
    await user.click(screen.getByRole('button', { name: /Save owner/ }))

    await waitFor(() => {
      expect(store.actions[0]?.owner).toBe('Jordan Lee')
    })
  })

  it('opens the evidence drawer for a call linked to the card', async () => {
    const user = userEvent.setup()
    renderAt('/actions')

    await waitFor(() => {
      expect(screen.getByText('Call back the unresolved members')).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /Call back the unresolved members/ }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /C-0001/ })).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /C-0001/ }))

    await waitFor(() => {
      expect(screen.getByText('Call C-0001')).toBeInTheDocument()
    })
    // The card dialog closes so the evidence drawer replaces it, the same
    // way the prototype's card closes before opening a transcript.
    expect(screen.queryByText('Three calls ended unresolved this period.')).not.toBeInTheDocument()
  })

  it('filters the board to one stage from the stage chips', async () => {
    store.actions = [
      makeAction({ id: 1, title: 'Call back the unresolved members', status: 'triage' }),
      makeAction({ id: 2, title: 'Chase the broker reply', status: 'in_hand' }),
    ]
    const user = userEvent.setup()
    renderAt('/actions')

    await waitFor(() => {
      expect(screen.getByText('Chase the broker reply')).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /^Triage/ }))

    await waitFor(() => {
      expect(screen.queryByText('Chase the broker reply')).not.toBeInTheDocument()
    })
    expect(screen.getByText('Call back the unresolved members')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Show all 2 actions/ })).toBeInTheDocument()
  })

  it('opens a card from the table view by keyboard', async () => {
    const user = userEvent.setup()
    renderAt('/actions')

    await waitFor(() => {
      expect(screen.getByText('Call back the unresolved members')).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: 'Table' }))

    const row = await screen.findByText('Call back the unresolved members')
    row.closest('tr')?.focus()
    await user.keyboard('{Enter}')

    await waitFor(() => {
      // Also present in the table row behind the dialog, so this counts
      // rather than insisting on a single match.
      expect(screen.getAllByText('Three calls ended unresolved this period.').length).toBeGreaterThan(0)
    })
    expect(screen.getByRole('button', { name: 'Mark step done' })).toBeInTheDocument()
  })

  it('switches between the board and the table view', async () => {
    const user = userEvent.setup()
    renderAt('/actions')

    await waitFor(() => {
      expect(screen.getByText('Call back the unresolved members')).toBeInTheDocument()
    })
    expect(screen.queryByRole('columnheader', { name: 'Outcome' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Table' }))

    await waitFor(() => {
      expect(screen.getByRole('columnheader', { name: 'Outcome' })).toBeInTheDocument()
    })
    expect(screen.getByText('Not yet measured')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Board' }))

    await waitFor(() => {
      expect(screen.queryByRole('columnheader', { name: 'Outcome' })).not.toBeInTheDocument()
    })
  })
})

describe('raising an action', () => {
  it('submits the composer through POST and the board refetches with the new card', async () => {
    const user = userEvent.setup()
    renderAt('/actions')

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '+ New action' })).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: '+ New action' }))

    const title = await screen.findByLabelText('Title')
    await user.clear(title)
    await user.type(title, 'Chase the overdue broker reply')
    await user.click(screen.getByRole('button', { name: 'Create action' }))

    await waitFor(() => {
      expect(store.actions.some((a) => a.title === 'Chase the overdue broker reply')).toBe(true)
    })
    // The composer hands off to the card it just created.
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Chase the overdue broker reply' })).toBeInTheDocument()
    })
  })

  it('edits the checklist and drops a linked call before creating', async () => {
    const user = userEvent.setup()
    renderAt('/actions?focus=unresolved')

    await waitFor(() => {
      expect(screen.getByText('Unresolved calls')).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: 'Raise an action' }))

    await screen.findByLabelText('Title')
    expect(screen.getByText('3 found')).toBeInTheDocument()
    // Uncheck one of the linked calls.
    await user.click(screen.getByRole('checkbox', { name: /C-0002/ }))
    // Add a step, then remove the playbook's second step.
    await user.click(screen.getByRole('button', { name: '+ Add a step' }))
    const stepInputs = screen.getAllByLabelText(/^Step \d/)
    await user.type(stepInputs[stepInputs.length - 1] as HTMLInputElement, 'Confirm with the team lead.')
    await user.click(screen.getAllByRole('button', { name: 'Remove step' })[1] as HTMLElement)

    await user.click(screen.getByRole('button', { name: 'Create action' }))

    await waitFor(() => {
      const created = store.actions.find(
        (a) => typeof a.title === 'string' && a.title.includes('Unresolved calls'),
      )
      expect(created?.callIds).toEqual(['C-0001', 'C-0003'])
      expect(created?.steps).toEqual([
        { text: 'Call each member back within two working days.', done: false },
        { text: 'Confirm with the team lead.', done: false },
      ])
    })
  })

  it('scopes the composer to the account named in the URL', async () => {
    const user = userEvent.setup()
    renderAt('/actions?focus=unresolved&employer=EMP-1001')

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Raise an action' })).toBeInTheDocument()
    })
    expect(screen.getAllByText(/Cedar Point Workforce Partners/).length).toBeGreaterThan(0)
    await user.click(screen.getByRole('button', { name: 'Raise an action' }))

    await screen.findByLabelText('Title')
    // The account panel in the composer's sidebar, resolved to a name.
    expect(screen.getAllByText('Cedar Point Workforce Partners').length).toBeGreaterThan(0)
  })

  it('says what failed rather than failing silently when the create is refused', async () => {
    store.failNextCreate = true
    const user = userEvent.setup()
    renderAt('/actions')

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '+ New action' })).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: '+ New action' }))
    await user.click(screen.getByRole('button', { name: 'Create action' }))

    await waitFor(() => {
      expect(screen.getByText(/a title is required/i)).toBeInTheDocument()
    })
  })

  it('cancels without creating anything', async () => {
    const user = userEvent.setup()
    renderAt('/actions')

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '+ New action' })).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: '+ New action' }))
    await screen.findByLabelText('Title')
    const before = store.actions.length

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.queryByLabelText('Title')).not.toBeInTheDocument()
    expect(store.actions.length).toBe(before)
  })
})

describe('the focused issue view', () => {
  it('renders the playbook for ?focus= and links to a prefilled composer', async () => {
    const user = userEvent.setup()
    renderAt('/actions?focus=unresolved')

    await waitFor(() => {
      expect(screen.getByText('Unresolved calls')).toBeInTheDocument()
    })
    expect(
      screen.getByText('The caller ended the call in the same position they started.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Call each member back within two working days.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Raise an action' }))

    const title = await screen.findByLabelText('Title')
    expect((title as HTMLInputElement).value).toContain('Unresolved calls')
  })

  it('excludes the focused issue from "other issues to act on"', async () => {
    renderAt('/actions?focus=unresolved')

    await waitFor(() => {
      expect(screen.getByText('Other issues to act on')).toBeInTheDocument()
    })
    const list = screen.getByRole('link', { name: /Escalations missed/ })
    expect(list).toBeInTheDocument()
    // The focused issue's own row does not repeat inside the list below.
    const attnList = list.closest('ul')
    expect(attnList ? within(attnList).queryAllByText('Unresolved calls') : []).toHaveLength(0)
  })

  it('renders a dynamic issue without a link, rather than guessing a route for it', async () => {
    renderAt('/actions')

    await waitFor(() => {
      expect(screen.getByText('Denial letter EOB')).toBeInTheDocument()
    })
    expect(
      screen.queryByRole('link', { name: /Denial letter EOB/ }),
    ).not.toBeInTheDocument()
  })

  it('says there is no playbook for a stray or held-back key, rather than an empty panel', async () => {
    renderAt('/actions?focus=brush_off')

    await waitFor(() => {
      expect(screen.getByText('No playbook for this issue')).toBeInTheDocument()
    })
  })

  it('says nothing is left to act on rather than showing an empty list silently', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: string, init?: RequestInit) => {
        const path = input.replace('http://api.test/api/v1', '')
        const body = path.startsWith('/insights/actions') && !path.includes('/board')
          ? { ...FINDINGS, items: [] }
          : handle(input, init)
        return Promise.resolve(
          new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } }),
        )
      }),
    )
    renderAt('/actions')

    await waitFor(() => {
      expect(screen.getByText('Nothing to act on')).toBeInTheDocument()
    })
  })
})

describe('no browser storage', () => {
  it('never writes to localStorage across create, tick and move', async () => {
    const setItem = vi.spyOn(Storage.prototype, 'setItem')
    const user = userEvent.setup()
    renderAt('/actions')

    await waitFor(() => {
      expect(screen.getByText('Call back the unresolved members')).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /Call back the unresolved members/ }))
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Mark step done' })).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: 'Mark step done' }))
    await waitFor(() => {
      expect(store.actions[0]?.steps).toEqual([
        { text: 'Call each member back within two working days.', done: true },
        { text: 'Tag the root cause on each call.', done: false },
      ])
    })

    expect(setItem).not.toHaveBeenCalled()
  })
})
