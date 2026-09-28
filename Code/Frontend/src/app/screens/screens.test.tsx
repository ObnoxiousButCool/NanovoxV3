/**
 * The four read screens, in the states a reader can actually land in.
 *
 * These test what the screens **refuse to say**, not that they render. A
 * screen that draws the right boxes and quietly turns a withheld figure
 * into 0%, or ninety unassessable accounts into ninety unflagged ones, has
 * passed every test worth failing and is still wrong.
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
  considered: 120,
  matched: 64,
  excludedCalls: 56,
  sources: ['CORPUS_PDF'],
  appliedFilters: [],
  caveats: ['Contact rate is measured over 12 weeks, which is wider than the period asked for.'],
  unmeasurable: [],
  corpusPeriod: { from: '2026-07-06', to: '2026-09-21' },
  period: null,
}

const WITHHELD = {
  value: null,
  published: false,
  n: 4,
  callIds: ['C-1', 'C-2', 'C-3', 'C-4'],
  basis: { code: 'OBSERVED', label: 'Observed' },
  withheldReason: { code: 'BELOW_MIN_N', label: 'Too few calls to publish' },
  caveats: ['Withheld: 4 calls against a minimum of 30 for contact rate.'],
}

const EXEC = {
  scope: SCOPE,
  asOf: '2026-09-21',
  calls: 64,
  metrics: [
    { key: 'contact_rate', name: 'Contact rate', windowWeeks: 12, figure: WITHHELD },
  ],
  escalation: [],
  intentRouted: WITHHELD,
  trends: {
    windowStart: '2026-08-24',
    windowEnd: '2026-09-21',
    windowWeeks: 4,
    priorStart: '2026-07-27',
    priorEnd: '2026-08-23',
    weeks: [
      { start: '2026-08-24', end: '2026-08-30', calls: 8 },
      { start: '2026-08-31', end: '2026-09-06', calls: null },
    ],
    movements: [
      {
        label: 'Complaints',
        now: 4,
        prior: 2,
        callsNow: 40,
        callsPrior: 20,
        expected: 4,
        z: 0,
        beyondNoise: false,
        worse: true,
      },
    ],
    emerging: [],
  },
}

const RISK = {
  scope: SCOPE,
  asOf: '2026-09-21',
  windowWeeks: 12,
  assessed: [],
  assessedCount: 0,
  ineligible: ['EMP-1001', 'EMP-1002'],
  ineligibleCount: 2,
  flaggedShare: {
    value: null,
    published: false,
    n: 0,
    callIds: [],
    basis: { code: 'OBSERVED', label: 'Observed' },
    withheldReason: { code: 'NOT_ELIGIBLE', label: 'Not enough calls to assess' },
    caveats: ['No employer reached 3 calls in this window, so none could be assessed.'],
  },
  exposure: {
    employers: [],
    lives: 0,
    annualPremium: 0,
    premiumIncomplete: false,
    caveat: 'Exposure across 0 flagged account(s): 0 lives. Exposure, not expected loss.',
  },
  bandCalibration: {
    insight: 9,
    question: 'Whether the risk bands actually predict who leaves',
    why: 'No termination or renewal outcome exists in the corpus to calibrate against.',
    unlockedBy: 'a termination/renewal outcome per employer',
  },
  escalationsTriggered: 0,
  escalationsMissed: 0,
  exitLanguageCalls: 0,
}

const ACTION_BOARD = {
  lanes: [
    { code: 'triage', label: 'Triage', open: true, requires: [] },
    { code: 'done', label: 'Done', open: false, requires: [] },
  ],
  actions: [],
  trustNote: 'There is no sign-in; anyone who can reach this can edit it.',
}

const FAMILIES = [
  {
    code: 'unresolved',
    label: 'Unresolved outcome',
    observed: true,
    hits: 3,
    employerCalls: 9,
    rate: 0.33,
    available: true,
    unavailableBecause: '',
  },
  {
    code: 'broker_adverse',
    label: 'Broker named adversely by the caller',
    observed: false,
    hits: 0,
    employerCalls: 9,
    rate: 0,
    available: true,
    unavailableBecause: '',
  },
  {
    code: 'high_effort',
    label: 'High member effort',
    observed: false,
    hits: 0,
    employerCalls: 9,
    rate: null,
    available: false,
    unavailableBecause: 'Member effort is our composite and is not built yet.',
  },
]

const ASSESSED = {
  employerRef: 'EMP-1001',
  calls: 9,
  eligible: true,
  flagged: false,
  quotable: false,
  state: 'Not flagged: 1 of 4 conditions met.',
  conditionsMet: 1,
  conditions: [
    {
      code: 'market_test_intent',
      label: 'Market-test language, quoted from the call',
      met: true,
      callIds: ['C-9'],
    },
    {
      code: 'failure_driven_repeat',
      label: 'A call we failed to resolve, that the caller came back about',
      met: false,
      callIds: [],
    },
  ],
  evidence: ['C-9'],
  observations: FAMILIES,
}

const ACCOUNT = {
  scope: SCOPE,
  asOf: '2026-09-21',
  riskWindowWeeks: 12,
  facts: {
    employerRef: 'EMP-1001',
    name: 'Cedar Point Workforce Partners',
    region: 'Orange County',
    industry: 'Staffing & Recruitment',
    brokerRef: 'BRK-02',
    enrolled: 315,
    // No premium recorded. Must never render as $0.
    annualPremium: null,
    renewalMonth: 'Jan',
    annualFee: 0,
  },
  contactRate: { windowWeeks: 12, figure: WITHHELD },
  repeatRate: { windowWeeks: 12, figure: WITHHELD },
  // A band with nobody publishable in it.
  peers: { band: '200+ lives', peers: 0, peerMedian: null, difference: null },
  risk: ASSESSED,
  profile: {
    calls: 6,
    unresolved: 2,
    repeatContacts: 1,
    escalationsMissed: 0,
    uncategorised: 1,
    topics: [
      { category: 'Claims & EOB', calls: 3 },
      { category: 'Billing & Premium', calls: 2 },
    ],
  },
  // Insight 7 with nothing wrong: a clean book is a finding, not a blank.
  drift: {
    flagged: false,
    checked: 2,
    mismatches: [],
    unresolved: [],
    finding: 'No drift: all 2 broker mention(s) matched the broker of record.',
  },
}

const HIERARCHY = {
  scope: SCOPE,
  asOf: '2026-09-21',
  windowWeeks: 12,
  systemic: [],
  matrix: [
    { region: 'Bay Area', counts: { 'Claims & EOB': 3, 'Billing & Premium': 0 } },
    { region: 'Orange County', counts: { 'Claims & EOB': 0, 'Billing & Premium': 1 } },
  ],
  rankedBrokers: [
    {
      brokerRef: 'BRK-02',
      adverseCalls: [],
      byTouchpoint: [],
      pattern: {
        fires: false,
        adverseMentions: 1,
        distinctEmployers: 1,
        reached: 'Below: 1 adverse mention(s) from 1 employer(s)',
        callIds: ['C-4'],
      },
      // No rate published for this broker at all.
      ratePerHundredLives: null,
    },
  ],
  tree: [
    {
      region: 'Bay Area',
      calls: 3,
      brokers: [
        {
          brokerRef: 'BRK-02',
          calls: 3,
          employers: [
            { employerRef: 'EMP-1001', name: 'Cedar Point Workforce Partners', calls: 3 },
          ],
        },
      ],
    },
  ],
}

function callRow(reference: string, over: Record<string, unknown> = {}) {
  return {
    reference,
    occurredOn: '2026-09-14',
    employerRef: 'EMP-1001',
    employerName: 'Cedar Point Workforce Partners',
    brokerRef: 'BRK-02',
    brokerAgency: 'Whitfield Benefits',
    region: 'Orange County',
    agentRef: 'AG-03',
    category: 'Claims & EOB',
    productLines: ['dental'],
    touchpoint: null,
    outcome: 'RESOLVED',
    // Null is not zero: a call with no score recorded did not score nothing.
    qualityScore: null,
    ahtSeconds: 400,
    complaint: false,
    complaintAgainst: null,
    signals: [],
    escalationTriggered: false,
    escalationHandled: false,
    controlExceptions: [],
    knowledgeFailure: false,
    intents: [],
    ...over,
  }
}

const CALLS = {
  scope: SCOPE,
  rows: [callRow('C-0001'), callRow('C-0002', { qualityScore: 78 })],
  total: 2,
  page: 1,
  perPage: 25,
  pages: 1,
  considered: 120,
  omittedColumns: [
    'Handling (archetype) — not one of the sixteen schema fields (C8a).',
  ],
}

const OPTIONS = {
  regions: ['Bay Area'],
  brokers: [{ ref: 'BRK-02', agency: 'Whitfield Benefits' }],
  employers: [
    { ref: 'EMP-1001', name: 'Cedar Point Workforce Partners', region: 'Bay Area' },
    { ref: 'EMP-1002', name: 'Park Mechanical', region: 'Bay Area' },
  ],
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

const AGENTS = {
  scope: SCOPE,
  asOf: '2026-09-21',
  windowWeeks: 12,
  qualityWindowWeeks: null,
  agents: [
    {
      agentRef: 'AGT-01',
      calls: ['C-1', 'C-2', 'C-3'],
      knowledgeErrors: ['C-1'],
      escalationsMissed: [],
      controlExceptions: [
        { exceptionType: { code: 'NO_RECORDING_DISCLOSURE', label: 'No recording disclosure' }, calls: 2 },
      ],
      knowledgeErrorRate: WITHHELD,
      quality: {
        scoredCalls: ['C-1'],
        medianScore: null,
        lowest: null,
        highest: null,
        caveat: 'Too few scored calls to publish a median for this agent.',
      },
    },
    {
      agentRef: 'AGT-02',
      calls: ['C-4'],
      knowledgeErrors: [],
      escalationsMissed: [],
      controlExceptions: [],
      knowledgeErrorRate: WITHHELD,
      quality: {
        scoredCalls: ['C-4'],
        medianScore: 88,
        lowest: 88,
        highest: 88,
        caveat: '',
      },
    },
  ],
}

/** The shape a deployment with no model configured serves (U2). */
const NO_INSIGHTS = {
  status: { code: 'UNAVAILABLE', label: 'Unavailable' },
  insights: [],
  reason: { code: 'NO_PROVIDER', label: 'No model is configured' },
  provider: null,
  model: null,
}

function routeFor(url: string): unknown {
  if (url.includes('/insights/filters')) return OPTIONS
  // Checked before `/insights/exec`: the generated surface takes the screen
  // as a query parameter, so both URLs carry the word.
  if (url.includes('/insights/generated')) return NO_INSIGHTS
  if (url.includes('/insights/agents')) return AGENTS
  if (url.includes('/insights/exec')) return EXEC
  if (url.includes('/insights/risk')) return RISK
  if (url.includes('/insights/actions/board')) return ACTION_BOARD
  if (url.includes('/insights/hierarchy')) return HIERARCHY
  if (url.includes('/insights/accounts/')) return ACCOUNT
  if (url.includes('/insights/calls')) return CALLS
  return {}
}

function serve(): void {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: string) =>
      Promise.resolve(
        new Response(JSON.stringify(routeFor(input)), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    ),
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
  serve()
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('the shared screen frame', () => {
  it("renders every one of the server's caveats, not just the first", async () => {
    renderAt('/exec')

    await waitFor(() => {
      expect(screen.getByText(/wider than the period asked for/i)).toBeInTheDocument()
    })
  })

  it('reports an API failure in its own words rather than a friendly substitute', async () => {
    // A 404 rather than a dropped connection, on purpose: `shouldRetry`
    // refuses to repeat a 4xx, so the query settles at once. A network
    // error retries twice with backoff and outlives the test timeout, which
    // would look like a missing error state rather than a slow one.
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              title: 'No such employer in this corpus.',
              status: 404,
              code: 'not_found',
              correlation_id: null,
              detail: null,
            }),
            { status: 404, headers: { 'Content-Type': 'application/problem+json' } },
          ),
        ),
      ),
    )

    renderAt('/exec')

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/no such employer in this corpus/i)
    })
  })
})

describe('/exec', () => {
  it('never renders a withheld figure as a number', async () => {
    renderAt('/exec')

    await waitFor(() => {
      expect(screen.getAllByText(/too few calls to publish/i).length).toBeGreaterThan(0)
    })
    // The one thing this screen must never do. A withheld rate shown as 0%
    // reads as perfect performance where the truth is no evidence.
    expect(screen.queryByText('0%')).not.toBeInTheDocument()
  })

  it('says a movement is within noise instead of hiding or asserting it', async () => {
    renderAt('/exec')

    await waitFor(() => {
      expect(screen.getByText(/within noise/i)).toBeInTheDocument()
    })
    // Both halves matter: the movement is still listed (not hidden), and it
    // is not dressed up as a finding.
    expect(screen.getByText('Complaints')).toBeInTheDocument()
    expect(screen.queryByText('worse')).not.toBeInTheDocument()
  })
})

function observationsWithNObserved(n: number) {
  return Array.from({ length: 10 }, (_, i) => ({
    code: `family_${String(i)}`,
    label: `Family ${String(i)}`,
    observed: i < n,
    hits: i < n ? 2 : 0,
    employerCalls: 9,
    rate: 0.2,
    available: true,
    unavailableBecause: '',
  }))
}

function bucket(hits: number) {
  return { start: '2026-09-01', end: '2026-09-07', calls: 10, hits }
}

const EXEC_RICH = {
  scope: SCOPE,
  asOf: '2026-09-28',
  calls: 100,
  metrics: EXEC.metrics,
  escalation: [
    {
      label: 'Handled, of escalations that were warranted',
      figure: {
        value: 0.6,
        published: true,
        n: 5,
        callIds: ['C-1', 'C-2', 'C-3', 'C-4', 'C-5'],
        basis: { code: 'OBSERVED', label: 'Observed' },
        withheldReason: null,
        caveats: [],
      },
    },
    {
      label: 'Escalations warranted, of all calls',
      figure: {
        value: 0.05,
        published: true,
        n: 100,
        callIds: [],
        basis: { code: 'OBSERVED', label: 'Observed' },
        withheldReason: null,
        caveats: [],
      },
    },
  ],
  intentRouted: WITHHELD,
  areaOfConcern: {
    category: 'Coverage & Benefits',
    calls: 5,
    unresolved: 3,
    escalationsTriggered: 2,
    escalationsHandled: 0,
  },
  trends: {
    windowStart: '2026-08-31',
    windowEnd: '2026-09-28',
    windowWeeks: 4,
    priorStart: '2026-08-03',
    priorEnd: '2026-08-30',
    weeks: [{ start: '2026-09-22', end: '2026-09-28', calls: 25 }],
    movements: [
      {
        label: 'Repeat contacts',
        now: 2,
        prior: 6,
        callsNow: 40,
        callsPrior: 40,
        expected: 6,
        z: -2.4,
        beyondNoise: true,
        worse: false,
      },
      {
        label: 'Unresolved calls',
        now: 12,
        prior: 10,
        callsNow: 40,
        callsPrior: 40,
        expected: 10,
        z: 2.1,
        beyondNoise: true,
        worse: true,
      },
    ],
    emerging: [
      {
        kind: 'category',
        key: 'Coverage & Benefits',
        buckets: [bucket(1), bucket(2), bucket(5)],
        delta: 4,
        rising: true,
      },
      {
        kind: 'signal',
        key: 'retention_risk',
        buckets: [bucket(0), bucket(1), bucket(3)],
        delta: 3,
        rising: true,
      },
      {
        kind: 'touchpoint',
        key: 'denial_letter_eob',
        buckets: [bucket(1), bucket(1), bucket(2)],
        delta: 1,
        rising: true,
      },
      {
        kind: 'product_line',
        key: 'dental',
        buckets: [bucket(5), bucket(3), bucket(1)],
        delta: -4,
        rising: false,
      },
      {
        kind: 'category',
        key: 'Broker Conduct',
        buckets: [bucket(3), bucket(2), bucket(1)],
        delta: -2,
        rising: false,
      },
    ],
  },
}

const RISK_RICH = {
  scope: SCOPE,
  asOf: '2026-09-28',
  windowWeeks: 12,
  assessed: [
    {
      employerRef: 'EMP-1001',
      calls: 12,
      eligible: true,
      flagged: true,
      quotable: true,
      state: 'Flagged: 5 of 4 conditions met.',
      conditionsMet: 3,
      conditions: [],
      evidence: [],
      observations: observationsWithNObserved(5),
      renewalMonth: 'November',
      monthsToRenewal: 2,
    },
    {
      employerRef: 'EMP-1002',
      calls: 9,
      eligible: true,
      flagged: true,
      quotable: true,
      state: 'Flagged: 3 of 4 conditions met.',
      conditionsMet: 2,
      conditions: [],
      evidence: [],
      observations: observationsWithNObserved(3),
      renewalMonth: 'March',
      monthsToRenewal: 6,
    },
    {
      employerRef: 'EMP-1003',
      calls: 4,
      eligible: true,
      flagged: false,
      quotable: false,
      state: 'Not flagged: 1 of 4 conditions met.',
      conditionsMet: 1,
      conditions: [],
      evidence: [],
      observations: observationsWithNObserved(1),
      renewalMonth: 'January',
      monthsToRenewal: 1,
    },
  ],
  assessedCount: 3,
  ineligible: [],
  ineligibleCount: 0,
  flaggedShare: {
    value: 2 / 3,
    published: true,
    n: 3,
    callIds: ['C-1', 'C-2', 'C-3'],
    basis: { code: 'OBSERVED', label: 'Observed' },
    withheldReason: null,
    caveats: [],
  },
  exposure: {
    employers: ['EMP-1001', 'EMP-1002'],
    lives: 250,
    annualPremium: 0,
    premiumIncomplete: true,
    caveat: 'Exposure across 2 flagged account(s): 250 lives. Exposure, not expected loss.',
  },
  bandCalibration: RISK.bandCalibration,
}

const ACTION_BOARD_RICH = {
  lanes: [
    { code: 'needs_action', label: 'Needs action', open: true, requires: [] },
    { code: 'in_progress', label: 'In progress', open: true, requires: [] },
    { code: 'completed', label: 'Completed', open: false, requires: [] },
  ],
  actions: [
    { id: 1, status: 'needs_action', pastDue: true, outcome: null },
    { id: 2, status: 'needs_action', pastDue: false, outcome: null },
    { id: 3, status: 'in_progress', pastDue: false, outcome: null },
    { id: 4, status: 'in_progress', pastDue: true, outcome: null },
    { id: 5, status: 'completed', pastDue: false, outcome: 'Fixed the billing rule.' },
  ],
  trustNote: 'There is no sign-in; anyone who can reach this can edit it.',
}

describe('/exec, with accounts, escalations and an action board', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: string) =>
        Promise.resolve(
          new Response(
            JSON.stringify(
              input.includes('/insights/exec')
                ? EXEC_RICH
                : input.includes('/insights/risk')
                  ? RISK_RICH
                  : input.includes('/insights/actions/board')
                    ? ACTION_BOARD_RICH
                    : routeFor(input),
            ),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
        ),
      ),
    )
  })

  it('lists the flagged accounts in the needs-attention panel, most indicators first', async () => {
    renderAt('/exec')

    await waitFor(() => {
      expect(screen.getByText('Needs attention now')).toBeInTheDocument()
    })
    // Two of three assessed accounts are flagged; the unflagged EMP-1003
    // never appears here even though it was assessed.
    expect(screen.getByText(/2 of 3 accounts are flagged/i)).toBeInTheDocument()
    // Each name also appears in the filter bar's employer dropdown, so this
    // counts rather than insisting on a single match.
    expect(screen.getAllByText('Cedar Point Workforce Partners').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Park Mechanical').length).toBeGreaterThan(0)
    expect(screen.getByText('5 of 10 indicators')).toBeInTheDocument()
    expect(screen.getByText('renews in 2 months')).toBeInTheDocument()
  })

  it('gets the four-tile row right, including a gauge with a rendered value', async () => {
    renderAt('/exec')

    await waitFor(() => {
      expect(screen.getByText('Risk and follow-through, at a glance')).toBeInTheDocument()
    })
    expect(screen.getByText('Accounts flagged')).toBeInTheDocument()
    // Two flagged accounts, out of three assessed.
    const tiles = screen.getByText('Accounts flagged').closest('.nv-big')
    expect(tiles).not.toBeNull()
    expect(within(tiles as HTMLElement).getByText('2')).toBeInTheDocument()
    // Both renewing within four months: EMP-1001 (2) and EMP-1002 is not
    // (6 months out), so only one flagged account is renewing soon.
    const renewTile = screen.getByText('Flagged & renewing soon').closest('.nv-big')
    expect(within(renewTile as HTMLElement).getByText('1')).toBeInTheDocument()
    // The gauge: 3 of 5 triggered escalations handled is 60%.
    expect(screen.getByText('60%')).toBeInTheDocument()
    expect(screen.getByText('3 of 5 handled')).toBeInTheDocument()
    // Two actions are past due.
    const overdueTile = screen.getByText('Overdue actions').closest('.nv-big')
    expect(within(overdueTile as HTMLElement).getByText('2')).toBeInTheDocument()
  })

  it('computes What went well and Area of concern from the fixture, not literal prototype text', async () => {
    renderAt('/exec')

    await waitFor(() => {
      expect(screen.getByText('What went well')).toBeInTheDocument()
    })
    const wellPanel = screen.getByText('What went well').closest('.nv-panel') as HTMLElement
    expect(wellPanel.textContent).toMatch(/Repeat contacts fell from 6 to 2 in the last 4 weeks/)

    const concernPanel = screen.getByText('Area of concern').closest('.nv-panel') as HTMLElement
    expect(concernPanel.textContent).toMatch(/Coverage & Benefits carries the most unresolved calls \(3\)/)
    expect(concernPanel.textContent).toMatch(/only 0 of 2 escalations there were handled/)
  })

  it('shows only the top three rising items as cards, plus an Easing sidebar', async () => {
    renderAt('/exec')

    await waitFor(() => {
      expect(screen.getByText('Emerging issues')).toBeInTheDocument()
    })
    // The three risen furthest: Coverage & Benefits (+4), retention_risk
    // (+3), denial_letter_eob (+1). The fourth-largest rise does not exist
    // in this fixture — the two falling items must not appear as cards.
    const panel = screen.getByText('Emerging issues').closest('.nv-panel') as HTMLElement
    expect(within(panel).getByText('Coverage & Benefits')).toBeInTheDocument()
    expect(within(panel).getByText('retention_risk')).toBeInTheDocument()
    expect(within(panel).getByText('denial_letter_eob')).toBeInTheDocument()
    // Each rising card carries its own chart.
    expect(within(panel).getAllByRole('img').length).toBeGreaterThanOrEqual(3)
    // Easing: the two falling items, dental first (furthest fallen).
    expect(within(panel).getByText('Easing')).toBeInTheDocument()
    expect(within(panel).getByText('dental')).toBeInTheDocument()
    expect(within(panel).getByText('Broker Conduct')).toBeInTheDocument()
  })

  it("matches the action-status bar's counts to the fixture action board", async () => {
    renderAt('/exec')

    await waitFor(() => {
      expect(screen.getByText('What is being done')).toBeInTheDocument()
    })
    // 4 of 5 actions sit in an open lane (needs_action x2, in_progress x2);
    // 2 are past due; 1 carries a measured outcome.
    expect(screen.getByText(/4 of 5 actions open, 2 overdue, 1 with a measured outcome/)).toBeInTheDocument()
    const key = screen.getByText('Needs action').closest('li') as HTMLElement
    expect(within(key).getByText('2')).toBeInTheDocument()
    const progressKey = screen.getByText('In progress').closest('li') as HTMLElement
    expect(within(progressKey).getByText('2')).toBeInTheDocument()
    const doneKey = screen.getByText('Completed').closest('li') as HTMLElement
    expect(within(doneKey).getByText('1')).toBeInTheDocument()
  })
})

describe('/risk', () => {
  it('keeps unassessable accounts out of "not flagged"', async () => {
    renderAt('/risk')

    // `getAllBy`: the phrase is deliberately in two places — the withheld
    // reason on the share, and the tile counting what could not be assessed.
    // A `getBy` here fails on the ambiguity rather than on the behaviour.
    await waitFor(() => {
      expect(screen.getAllByText(/not enough calls to assess/i).length).toBeGreaterThan(0)
    })
    // Two employers could not be assessed. Neither may appear as an account
    // that was assessed and found unflagged — that would be two clean bills
    // of health nobody can support.
    expect(screen.getByText(/no employer reached the eligibility floor/i)).toBeInTheDocument()
  })

  it('shows employer names, never the references they are keyed by', async () => {
    renderAt('/risk')

    // The name is in the filter bar's employer list as well as the
    // ineligible panel, so this counts rather than insisting on one.
    await waitFor(() => {
      expect(screen.getAllByText('Cedar Point Workforce Partners').length).toBeGreaterThan(0)
    })
    // The assertion that matters: the reference appears nowhere on screen.
    expect(screen.queryByText('EMP-1001')).not.toBeInTheDocument()
  })

  it('renders insight 9 withheld unconditionally, not as an empty panel', async () => {
    renderAt('/risk')

    await waitFor(() => {
      expect(
        screen.getByText('Whether the risk bands actually predict who leaves'),
      ).toBeInTheDocument()
    })
    expect(screen.getByText(/no termination or renewal outcome exists/i)).toBeInTheDocument()
  })

  it('says the share is over every assessed account, not the filtered rows', async () => {
    renderAt('/risk')

    await waitFor(() => {
      expect(screen.getByText(/whatever is filtered here/i)).toBeInTheDocument()
    })
  })
})

describe('/risk, with an account it could assess', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: string) =>
        Promise.resolve(
          new Response(
            JSON.stringify(
              input.includes('/insights/risk')
                ? { ...RISK, assessed: [ASSESSED], assessedCount: 1 }
                : routeFor(input),
            ),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
        ),
      ),
    )
  })

  it('renders the indicator count as a count, never as a level', async () => {
    renderAt('/risk')

    await waitFor(() => {
      expect(screen.getByText('1 of 10')).toBeInTheDocument()
    })
    // D12: no band survived. These four words must not appear on the screen
    // that decision was made for.
    for (const band of ['High', 'Elevated', 'Watch', 'None']) {
      expect(screen.queryByText(band)).not.toBeInTheDocument()
    }
  })

  it('names the families that fired rather than only counting them', async () => {
    renderAt('/risk')

    await waitFor(() => {
      expect(screen.getByText('Unresolved outcome')).toBeInTheDocument()
    })
    // A family that did not fire is not named in the row — the count says
    // how many of ten, so absence is already legible without listing eight.
    expect(screen.queryByText('High member effort')).not.toBeInTheDocument()
  })
})

describe('/risk, the headline tile row', () => {
  const FLAGGED_SOON = { ...ASSESSED, flagged: true, monthsToRenewal: 2 }

  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: string) =>
        Promise.resolve(
          new Response(
            JSON.stringify(
              input.includes('/insights/risk')
                ? {
                    ...RISK,
                    assessed: [FLAGGED_SOON],
                    assessedCount: 1,
                    escalationsTriggered: 11,
                    escalationsMissed: 4,
                    exitLanguageCalls: 4,
                  }
                : routeFor(input),
            ),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
        ),
      ),
    )
  })

  it('counts flagged accounts, not a share, in the headline tile', async () => {
    renderAt('/risk')

    await waitFor(() => {
      expect(screen.getByText('Accounts flagged')).toBeInTheDocument()
    })
    const tile = screen.getByText('Accounts flagged').closest('div')
    expect(tile).not.toBeNull()
    expect(within(tile as HTMLElement).getByText('1')).toBeInTheDocument()
  })

  it('counts flagged accounts renewing within the shared soon-window', async () => {
    renderAt('/risk')

    await waitFor(() => {
      expect(screen.getByText('Flagged & renewing soon')).toBeInTheDocument()
    })
    const tile = screen.getByText('Flagged & renewing soon').closest('div')
    expect(within(tile as HTMLElement).getByText('1')).toBeInTheDocument()
  })

  it('shows escalations missed against how many were triggered', async () => {
    renderAt('/risk')

    await waitFor(() => {
      expect(screen.getByText('Escalations missed')).toBeInTheDocument()
    })
    expect(screen.getByText('7 of 11 handled')).toBeInTheDocument()
  })

  it('links each nonzero headline tile to what to do about it', async () => {
    renderAt('/risk')

    await waitFor(() => {
      expect(screen.getByText('Exit language')).toBeInTheDocument()
    })
    const links = screen.getAllByRole('link')
    const focuses = links
      .map((link) => link.getAttribute('href'))
      .filter((href): href is string => href !== null && href.includes('/actions?focus='))
    for (const key of ['flagged', 'renew_soon', 'escalation_missed', 'exit_language']) {
      expect(focuses.some((href) => href.includes(`focus=${key}`))).toBe(true)
    }
  })
})

describe('/accounts/:ref', () => {
  it('shows a missing premium as unrecorded, never as zero', async () => {
    renderAt('/accounts/EMP-1001')

    await waitFor(() => {
      expect(screen.getByText('Not recorded')).toBeInTheDocument()
    })
    // The failure this guards: an account with no premium on file rendering
    // as an account worth nothing.
    expect(screen.queryByText('$0')).not.toBeInTheDocument()
  })

  it('keeps an unavailable indicator family out of "not observed"', async () => {
    renderAt('/accounts/EMP-1001')

    await waitFor(() => {
      expect(screen.getByText(/our composite and is not built yet/i)).toBeInTheDocument()
    })
    // Three different sentences for three different things: fired, checked
    // and did not fire, and cannot be checked at all.
    expect(screen.getByText('3 of 9 calls')).toBeInTheDocument()
    expect(screen.getByText('not observed')).toBeInTheDocument()
  })

  it('renders the conditions that did not fire, not only the ones that did', async () => {
    renderAt('/accounts/EMP-1001')

    await waitFor(() => {
      expect(
        screen.getByText('Market-test language, quoted from the call'),
      ).toBeInTheDocument()
    })
    expect(
      screen.getByText('A call we failed to resolve, that the caller came back about'),
    ).toBeInTheDocument()
    expect(screen.getByText('not met')).toBeInTheDocument()
  })

  it('says a peer band has nobody publishable rather than showing no difference', async () => {
    renderAt('/accounts/EMP-1001')

    await waitFor(() => {
      expect(screen.getByText(/no peer in this band has a rate we can publish/i)).toBeInTheDocument()
    })
  })

  it('resolves the broker of record to its agency name', async () => {
    renderAt('/accounts/EMP-1001')

    await waitFor(() => {
      expect(screen.getAllByText('Whitfield Benefits').length).toBeGreaterThan(0)
    })
    expect(screen.queryByText('BRK-02')).not.toBeInTheDocument()
  })
})

describe('/hierarchy', () => {
  it('publishes no rate for a broker the server sent none for', async () => {
    renderAt('/hierarchy')

    await waitFor(() => {
      expect(screen.getByText('Not published')).toBeInTheDocument()
    })
    // Null is not a rate of zero, and this is the one screen where a real
    // zero does render — so the two must stay distinguishable.
    expect(screen.queryByText('0.00')).not.toBeInTheDocument()
  })

  it('says what a pattern test reached when it did not fire', async () => {
    renderAt('/hierarchy')

    await waitFor(() => {
      expect(screen.getByText(/below: 1 adverse mention/i)).toBeInTheDocument()
    })
    expect(screen.queryByText('Fires')).not.toBeInTheDocument()
  })

  it('draws the heatmap over the union of categories, so rows line up', async () => {
    renderAt('/hierarchy')

    await waitFor(() => {
      expect(screen.getByLabelText('Calls by region and category')).toBeInTheDocument()
    })
    // Both regions, both categories — a ragged matrix would break the
    // dark-column reading the panel tells the reader to use.
    expect(screen.getAllByText('Bay Area').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Orange County').length).toBeGreaterThan(0)
  })
})

describe('/calls', () => {
  it('shows a missing quality score as unrecorded, never as zero', async () => {
    renderAt('/calls')

    await waitFor(() => {
      expect(screen.getByText('Not recorded')).toBeInTheDocument()
    })
    expect(screen.getByText('78')).toBeInTheDocument()
    // The failure this guards: an unscored call reading as the worst call
    // in the corpus.
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })

  it('says what the export does not carry, where the export is offered', async () => {
    renderAt('/calls')

    await waitFor(() => {
      expect(screen.getByText(/not one of the sixteen schema fields/i)).toBeInTheDocument()
    })
  })

  it('points download at the server rather than building a file here', async () => {
    // Checkpoint I2: the column projection is the server's. A file built in
    // the browser would be a second column list, and the file a reader
    // mails out would come from different code than the table on screen.
    renderAt('/calls')

    await waitFor(() => {
      expect(screen.getByRole('link', { name: /download 2 matching calls/i })).toBeInTheDocument()
    })
    const link = screen.getByRole('link', { name: /download 2 matching calls/i })
    expect(link).toHaveAttribute('href', expect.stringContaining('/insights/calls.csv'))
  })

  it('offers download-selected only once something is selected', async () => {
    const user = userEvent.setup()
    renderAt('/calls')

    await waitFor(() => {
      expect(screen.getByLabelText('Select call C-0001')).toBeInTheDocument()
    })
    expect(screen.queryByRole('link', { name: /download 1 selected/i })).not.toBeInTheDocument()

    await user.click(screen.getByLabelText('Select call C-0001'))

    const selected = screen.getByRole('link', { name: /download 1 selected/i })
    // The reference rides on the URL, so the server does the narrowing and
    // the export stays one projection.
    expect(selected).toHaveAttribute('href', expect.stringContaining('ref=C-0001'))
  })

  it('selects a page at a time, never rows the reader has not seen', async () => {
    const user = userEvent.setup()
    renderAt('/calls')

    await waitFor(() => {
      expect(screen.getByLabelText('Select every call on this page')).toBeInTheDocument()
    })

    await user.click(screen.getByLabelText('Select every call on this page'))

    expect(screen.getByRole('link', { name: /download 2 selected/i })).toBeInTheDocument()
  })
})

describe('insight 7 on /accounts/:ref', () => {
  it('renders a clean book as a finding rather than a blank panel', async () => {
    // The sheet's own instruction: "Zero mismatches renders as a finding."
    // An empty panel would throw away the one case where the answer is
    // "we checked, and it is fine".
    renderAt('/accounts/EMP-1001')

    await waitFor(() => {
      expect(screen.getByText(/no drift: all 2 broker mention/i)).toBeInTheDocument()
    })
    // Nothing is wrong, so nothing asks the reader to act.
    expect(
      screen.queryByRole('link', { name: /what to do about the drift/i }),
    ).not.toBeInTheDocument()
  })
})

describe('acting on a figure', () => {
  it('links a flagged account to what to do about it', async () => {
    serveWithAssessed()
    renderAt('/risk')

    await waitFor(() => {
      expect(screen.getByText('1 of 10')).toBeInTheDocument()
    })
    const links = screen.getAllByRole('link')
    const acts = links.filter((link) => link.getAttribute('href')?.includes('/actions?focus='))
    // The indicator that fired is `unresolved`, which has a playbook.
    expect(acts.some((link) => link.getAttribute('href')?.includes('focus=unresolved'))).toBe(
      true,
    )
  })
})

function serveWithAssessed(): void {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: string) =>
      Promise.resolve(
        new Response(
          JSON.stringify(
            input.includes('/insights/risk')
              ? { ...RISK, assessed: [ASSESSED], assessedCount: 1 }
              : routeFor(input),
          ),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    ),
  )
}


describe('/accounts — the picker', () => {
  it('lists every account, not only the assessable ones', async () => {
    // Both fixture employers are ineligible. A picker that showed only
    // assessed accounts would render an empty book and read as "nothing
    // here" rather than "nothing could be assessed".
    renderAt('/accounts')

    const picker = await screen.findByLabelText('Accounts')

    expect(within(picker).getByText('Cedar Point Workforce Partners')).toBeInTheDocument()
    expect(within(picker).getByText('Park Mechanical')).toBeInTheDocument()
  })

  it('says an unassessable account was not assessed, never that it is unflagged', async () => {
    renderAt('/accounts')

    const picker = await screen.findByLabelText('Accounts')

    expect(within(picker).getAllByText('Not assessed')).toHaveLength(2)
    expect(within(picker).queryByText('Not flagged')).not.toBeInTheDocument()
  })

  it('shows no risk band anywhere, because D12 removed it', async () => {
    renderAt('/accounts')

    const picker = await screen.findByLabelText('Accounts')

    for (const band of ['High', 'Elevated', 'Watch', 'Low']) {
      expect(within(picker).queryByText(band)).not.toBeInTheDocument()
    }
  })

  it('opens the first account without being asked', async () => {
    renderAt('/accounts')

    expect(await screen.findByText('The account')).toBeInTheDocument()
  })

  it('narrows the list as the reader types, and says when nothing matches', async () => {
    renderAt('/accounts')
    const picker = await screen.findByLabelText('Accounts')
    const search = within(picker).getByLabelText('Search accounts')

    await userEvent.type(search, 'Cedar')
    expect(within(picker).queryByText('Park Mechanical')).not.toBeInTheDocument()

    await userEvent.clear(search)
    await userEvent.type(search, 'nothing matches this')
    expect(within(picker).getByText('No match')).toBeInTheDocument()
  })

  it('selects an account into the URL, so the view can be linked', async () => {
    renderAt('/accounts')
    const picker = await screen.findByLabelText('Accounts')

    await userEvent.click(within(picker).getByRole('button', { name: /Park Mechanical/ }))

    await waitFor(() => {
      expect(
        within(picker).getByRole('button', { name: /Park Mechanical/ }),
      ).toHaveAttribute('aria-current', 'true')
    })
  })

  it('keeps the picker beside a deep-linked account', async () => {
    // The old `/accounts/:ref` route had no picker at all, so arriving from
    // the risk table left the reader with no way to reach the next account.
    renderAt('/accounts/EMP-1001')

    expect(await screen.findByLabelText('Accounts')).toBeInTheDocument()
    expect(screen.getByText('The account')).toBeInTheDocument()
  })
})


describe('/agents', () => {
  it('counts an event against a person at any volume', async () => {
    // The page's whole premise: a compliance exception is a breach on that
    // call whatever the sample, so it is attributed; an average is not.
    renderAt('/agents')
    await screen.findByText('Issues by agent')

    const issues = screen.getByText('Issues by agent').closest('section')

    expect(issues).not.toBeNull()
    expect(within(issues as HTMLElement).getByText('AGT-01')).toBeInTheDocument()
  })

  it('leaves an agent with no events out of the issues table', async () => {
    renderAt('/agents')
    await screen.findByText('Issues by agent')

    const issues = screen.getByText('Issues by agent').closest('section')

    expect(issues).not.toBeNull()
    expect(within(issues as HTMLElement).queryByText('AGT-02')).not.toBeInTheDocument()
  })

  it('withholds a median instead of printing a dash that reads as zero', async () => {
    renderAt('/agents')
    await screen.findByText('The roster')

    const roster = screen.getByText('The roster').closest('section')

    expect(roster).not.toBeNull()
    expect(
      within(roster as HTMLElement).getByText(/Too few scored calls/),
    ).toBeInTheDocument()
    expect(within(roster as HTMLElement).getByText('88')).toBeInTheDocument()
  })

  it('says how many agents could be scored, not just who was', async () => {
    renderAt('/agents')

    expect(await screen.findByText('1 of 2')).toBeInTheDocument()
  })

  it('points the rule question at /rules rather than answering it here', async () => {
    // "Coach the agent or fix the rule?" needs the rule behind each error;
    // this endpoint carries calls. C5 gives that question its own page.
    renderAt('/agents')

    const link = await screen.findByRole('link', { name: /rules we fail to explain/i })

    expect(link).toHaveAttribute('href', '/rules')
  })
})

describe('the account tiles and topics', () => {
  it('counts the account’s own calls without suppressing a zero', async () => {
    // A count of things that happened has no minimum: zero escalations
    // missed out of six calls is a true statement, where a zero *rate*
    // over six would not be.
    renderAt('/accounts/EMP-1001')

    expect(await screen.findByText(/This account.s calls/)).toBeInTheDocument()
    const tiles = screen.getByText(/This account.s calls/).closest('section')

    expect(tiles).not.toBeNull()
    expect(within(tiles as HTMLElement).getByText('Escalations missed')).toBeInTheDocument()
    expect(within(tiles as HTMLElement).getByText('0')).toBeInTheDocument()
  })

  it('never shows an average call quality for an account', async () => {
    // Metric 12 is per agent. Rolling it up to an employer is forbidden by
    // the Metrics sheet, so the prototype's fifth tile is carried as a
    // conflict rather than served. This is the assertion that keeps it out.
    renderAt('/accounts/EMP-1001')
    await screen.findByText(/This account.s calls/)

    expect(screen.queryByText(/average call quality/i)).not.toBeInTheDocument()
  })

  it('ranks what they call about, most first', async () => {
    renderAt('/accounts/EMP-1001')
    await screen.findByText('What they call about')

    const topics = screen.getByText('What they call about').closest('section')

    expect(topics).not.toBeNull()
    const labels = within(topics as HTMLElement)
      .getAllByRole('listitem')
      .map((item) => item.textContent ?? '')

    expect(labels[0]).toContain('Claims & EOB')
    expect(labels[1]).toContain('Billing & Premium')
  })

  it('says how many calls the bars do not account for', async () => {
    // The bars plus this number reconcile with the call count. Without it a
    // reader would silently be shown five of six calls.
    renderAt('/accounts/EMP-1001')

    expect(await screen.findByText(/carried no category/)).toBeInTheDocument()
  })
})
