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
import { unrunAnalysis } from '@/shared/design/drawer/analysisFixture'
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
  drivers: [
    {
      code: 'unresolved',
      label: 'Unresolved outcome',
      calls: 4,
      callIds: ['C-1', 'C-2', 'C-3', 'C-4'],
      topCategory: 'Claims & EOB',
      topTouchpoint: 'denial_letter_eob',
      available: true,
      unavailableBecause: '',
      change: { now: 3, prior: 1, expected: 1.2, beyondNoise: false, worse: true },
    },
    {
      code: 'exit_language',
      label: 'Exit or market-test language, verbatim',
      calls: 0,
      callIds: [],
      topCategory: null,
      topTouchpoint: null,
      available: true,
      unavailableBecause: '',
      change: null,
    },
    // v9 carries no field for this one: reported with its reason, not as a zero.
    {
      code: 'high_effort',
      label: 'High member effort',
      calls: 0,
      callIds: [],
      topCategory: null,
      topTouchpoint: null,
      available: false,
      unavailableBecause: 'Member effort is a derived composite, not a v9 field.',
      change: null,
    },
  ],
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
    assessable: true,
    unavailableBecause: '',
    callIds: ['C-1', 'C-2', 'C-3'],
  },
  {
    code: 'broker_adverse',
    label: 'Broker named adversely by the caller',
    observed: false,
    hits: 0,
    employerCalls: 9,
    rate: 0,
    available: true,
    assessable: true,
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
    // Assessable, and still unavailable. The two are independent: this
    // account has the calls, and v9 has no field.
    assessable: true,
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
    eligible: 420,
    // Below rule P-18's 70%, which is what puts a stake on this account.
    participation: 0.75,
    linesHeld: 'dental',
    cobraRegime: 'federal',
    dentalSponsorship: 'ER',
    plannedCalls: 24,
    renewalInMonths: 4,
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
  stakes: [
    {
      code: 'high_contact_rate',
      label: 'Planned contact rate above the book median',
      detail:
        '40.0 planned calls per 100 lives, against a book median of 12.0. A plan, not a count — the measured contact rate is the figure above.',
    },
  ],
  // Wider than the risk window the tiles count, so the page has to say
  // which calls its counts leave out.
  callsInPeriod: 9,
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
  complaints: { ours: 3, total: 5 },
  regions: [
    { region: 'Bay Area', accounts: 16, flagged: 2, calls: 3, unresolved: 1 },
    { region: 'Orange County', accounts: 16, flagged: 0, calls: 1, unresolved: 0 },
  ],
  brokers: [
    {
      brokerRef: 'BRK-02',
      agency: 'Marsh & Vale',
      name: 'Dana Vale',
      region: 'Bay Area',
      groupsInBook: 12,
      calls: 3,
      adverseMentions: 1,
      adverseEmployers: 1,
      patternFires: false,
      patternReached: 'Below: 1 adverse mention(s) from 1 employer(s); needs 3 from 2.',
      flaggedAccounts: 2,
    },
    {
      brokerRef: 'BRK-09',
      agency: 'Trent & Associates',
      name: 'Ray Trent',
      region: 'Orange County',
      groupsInBook: 4,
      calls: 1,
      adverseMentions: 0,
      adverseEmployers: 0,
      patternFires: false,
      patternReached: 'Below: 0 adverse mention(s) from 0 employer(s); needs 3 from 2.',
      flaggedAccounts: 0,
    },
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
  agents: [],
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
  roster: [
    { agentRef: 'AGT-01', name: 'Sarah Whitlock', band: 'Senior', expectedScore: 88, scoreVariance: 7 },
    { agentRef: 'AGT-02', name: 'Ryan Castellano', band: 'Developing', expectedScore: 61, scoreVariance: 14 },
  ],
  bands: [
    {
      band: 'Senior',
      agents: 1,
      calls: 3,
      events: 3,
      scoredCalls: 1,
      medianScore: null,
      hardCallShare: null,
    },
    {
      band: 'Developing',
      agents: 1,
      calls: 1,
      events: 0,
      scoredCalls: 1,
      medianScore: 88,
      hardCallShare: null,
    },
  ],
  escalationsRefused: ['C-9'],
  minCallsForARate: 30,
  complexityUnavailable:
    'Call complexity is a derived composite, not a v9 field, so the share of harder calls cannot be observed.',
}

/** The shape a deployment with no model configured serves (U2). */
const NO_INSIGHTS = {
  status: { code: 'UNAVAILABLE', label: 'Unavailable' },
  lenses: [
    { code: 'EMPLOYERS', label: 'Employers' },
    { code: 'CHURN_AND_RETENTION', label: 'Churn & retention' },
    { code: 'PRODUCT_AND_SERVICE', label: 'Product & service' },
    { code: 'PAYER_AND_CARRIER', label: 'Payer & carrier' },
  ],
  insights: [],
  reason: { code: 'NO_PROVIDER', label: 'No model is configured' },
  provider: null,
  model: null,
}

/** One call's evidence, as the drawer asks for it. */
const EVIDENCE = {
  reference: 'C-1',
  callerRef: 'CB-7700001',
  callerType: 'member',
  agentRef: 'AGT-01',
  employerRef: 'EMP-1001',
  resolutionStatus: 'RESOLVED',
  resolutionReason: null,
  transcriptMissing: false,
  analysis: unrunAnalysis('CB-7700001'),
  turns: [{ seq: 0, speaker: 'AGENT', text: 'Choice Administrators, how can I help?' }],
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
  // Before the list: `/insights/calls/C-1` contains `/insights/calls`, and
  // serving the page shape for one call's evidence breaks the drawer.
  if (/\/insights\/calls\/[^?]+/.test(url)) return EVIDENCE
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
    assessable: true,
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

    // Scoped to the accounts table: the drivers panel below it names the
    // same ten families book-wide, so an unscoped query matches both.
    const assessed = await screen.findByText('Accounts assessed')
    const panel = assessed.closest('section')

    expect(panel).not.toBeNull()
    await waitFor(() => {
      expect(within(panel as HTMLElement).getByText('Unresolved outcome')).toBeInTheDocument()
    })
    // A family that did not fire is not named in the row — the count says
    // how many of ten, so absence is already legible without listing eight.
    expect(
      within(panel as HTMLElement).queryByText('High member effort'),
    ).not.toBeInTheDocument()
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

  it('resolves the broker of record to its agency name', async () => {
    renderAt('/accounts/EMP-1001')

    await waitFor(() => {
      expect(screen.getAllByText('Whitfield Benefits').length).toBeGreaterThan(0)
    })
    expect(screen.queryByText('BRK-02')).not.toBeInTheDocument()
  })
})

describe('/hierarchy', () => {
  it('asks the page question from the prototype, not the rail label', async () => {
    // The rail says "Isolated or systemic?" and the page asks "Is it
    // isolated or systemic?". Both are the prototype's, and the App test
    // no longer assumes they are the same string.
    renderAt('/hierarchy')

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { level: 1, name: 'Is it isolated or systemic?' }),
      ).toBeInTheDocument()
    })
  })

  it('says what a pattern test reached when it did not fire', async () => {
    // §9 asks for the test shown fired and unfired with what it reached.
    // The two numbers the test takes are in the cell, the threshold is in
    // the panel's (i), and the sentence is the cell's title — down thirty
    // rows it would be the page's longest text and the same words each
    // time, which is what the prototype avoids by not printing it.
    renderAt('/hierarchy')

    await waitFor(() => {
      expect(screen.getByText('Marsh & Vale')).toBeInTheDocument()
    })
    const cell = [...document.querySelectorAll('td[title]')].find((td) =>
      td.getAttribute('title')?.includes('adverse mention'),
    )
    expect(cell?.getAttribute('title')).toMatch(/below: 1 adverse mention/i)
    expect(cell?.textContent).toContain('1 employer')
    expect(screen.queryByText('Fires')).not.toBeInTheDocument()
  })

  it('shows no per-broker rate at all', async () => {
    // A three-group broker has about ten calls. The prototype says plainly
    // why it divides by nothing, and a rate appearing here would be the
    // one number this table exists to refuse.
    renderAt('/hierarchy')

    await waitFor(() => {
      expect(screen.getByText('Marsh & Vale')).toBeInTheDocument()
    })
    const headers = [...document.querySelectorAll('table th[scope="col"]')].map(
      (cell) => cell.textContent,
    )
    expect(headers).not.toContain('Per 100 lives')
    expect(screen.queryByText('Not published')).not.toBeInTheDocument()
  })

  it('counts every account in a region, not every account that called', async () => {
    // A region where two of sixteen accounts rang is not a two-account
    // region, and a table that said so would make the quiet ones vanish.
    renderAt('/hierarchy')

    await waitFor(() => {
      expect(screen.getByText('By region')).toBeInTheDocument()
    })
    const row = [...document.querySelectorAll('tbody tr')].find((tr) =>
      tr.textContent?.startsWith('Bay Area'),
    )
    expect([...(row?.querySelectorAll('td') ?? [])].map((cell) => cell.textContent)).toEqual([
      '16',
      '2',
      '3',
      '1',
    ])
  })

  it('narrows every page from a region row rather than navigating away', async () => {
    const user = userEvent.setup()
    renderAt('/hierarchy')

    await waitFor(() => {
      expect(screen.getByText('By region')).toBeInTheDocument()
    })
    const row = [...document.querySelectorAll('tbody tr')].find((tr) =>
      tr.textContent?.startsWith('Bay Area'),
    )
    await user.click(row as HTMLElement)

    // Re-queried rather than re-read: React replaces the node, so the
    // reference above can be detached by the time the filter lands.
    await waitFor(() => {
      const pressed = [...document.querySelectorAll('tbody tr[aria-pressed="true"]')].map(
        (tr) => tr.textContent,
      )
      expect(pressed.some((text) => text?.startsWith('Bay Area'))).toBe(true)
    })
    // Still on the same screen: this writes a filter, it does not route.
    expect(screen.getByText('By region')).toBeInTheDocument()
  })

  it('draws the heatmap over the union of categories, so rows line up', async () => {
    renderAt('/hierarchy')

    await waitFor(() => {
      expect(screen.getByLabelText('Calls by region and topic')).toBeInTheDocument()
    })
    // Both regions, both categories — a ragged matrix would break the
    // dark-column reading the panel tells the reader to use.
    expect(screen.getAllByText('Bay Area').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Orange County').length).toBeGreaterThan(0)
  })

  it('reads the complaint tile against complaints, not against calls', async () => {
    // A different figure from the complaint rate, which divides by
    // everyone who rang. Reading one as the other overstates or
    // understates the load by the size of the quiet majority.
    renderAt('/hierarchy')

    await waitFor(() => {
      expect(screen.getByText('Complaints about us')).toBeInTheDocument()
    })
    expect(screen.getByText('of 5 complaints')).toBeInTheDocument()
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

    expect(await screen.findByText('Cedar Point Workforce Partners', { selector: 'h2' })).toBeInTheDocument()
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
    expect(screen.getByText('Cedar Point Workforce Partners', { selector: 'h2' })).toBeInTheDocument()
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
    expect(within(issues as HTMLElement).getByText('Sarah Whitlock')).toBeInTheDocument()
  })

  it('names the agent and their band rather than a reference', async () => {
    // The roster carries the name. A page about conduct that can only say
    // AGT-01 is one nobody can act on.
    renderAt('/agents')
    await screen.findByText('Issues by agent')

    const issues = screen.getByText('Issues by agent').closest('section')

    expect(within(issues as HTMLElement).getByText('Senior')).toBeInTheDocument()
    expect(within(issues as HTMLElement).queryByText('AGT-01')).not.toBeInTheDocument()
  })

  it('leaves an agent with no events out of the issues table', async () => {
    renderAt('/agents')
    await screen.findByText('Issues by agent')

    const issues = screen.getByText('Issues by agent').closest('section')

    expect(issues).not.toBeNull()
    expect(within(issues as HTMLElement).queryByText('Ryan Castellano')).not.toBeInTheDocument()
  })

  it('counts the agents who cleared the bar, not the ones with any scored call', async () => {
    // Counting scored calls produced a tile reading "2 of 2 have a score"
    // over a meta line saying the busiest agent had 3 of 30 — a tile
    // disagreeing with itself.
    renderAt('/agents')

    expect(await screen.findByText('0 of 2')).toBeInTheDocument()
    expect(screen.getByText('busiest has 3 of 30 calls')).toBeInTheDocument()
  })

  it('shows every agent on the roster, including one with nothing against them', async () => {
    // A coverage bar counts towards a minimum, so an agent with nothing in
    // the window is a row at nought of thirty rather than a row missing.
    renderAt('/agents')
    await screen.findByText(/Full roster/)

    const roster = screen.getByText(/Full roster/).closest('section')

    expect(within(roster as HTMLElement).getByText('Ryan Castellano')).toBeInTheDocument()
    expect(within(roster as HTMLElement).getByText('1/30')).toBeInTheDocument()
  })

  it('labels the expected score as what the roster set beforehand', async () => {
    // The corpus was generated from it, so an agent matching it is the
    // data agreeing with itself.
    renderAt('/agents')
    await screen.findByText(/Full roster/)

    expect(screen.getByText(/written before the calls/i)).toBeInTheDocument()
    expect(screen.getByText('88 ± 7')).toBeInTheDocument()
  })

  it('leaves the difficulty column unmeasured rather than at zero', async () => {
    // A share of high-complexity calls computed from a field that does not
    // exist would read as "this band handles easy work".
    renderAt('/agents')
    await screen.findByText('By experience level')

    const bands = screen.getByText('By experience level').closest('section')

    expect(within(bands as HTMLElement).getAllByText('not measured').length).toBe(2)
    expect(within(bands as HTMLElement).queryByText('0%')).not.toBeInTheDocument()
  })

  it('publishes a band median only where the band cleared the floor', async () => {
    renderAt('/agents')
    await screen.findByText('By experience level')

    const bands = screen.getByText('By experience level').closest('section')
    const rows = [...(bands as HTMLElement).querySelectorAll('tbody tr')]

    expect(rows[0]?.textContent).toContain('Senior')
    expect(rows[0]?.querySelector('td:last-child')?.textContent).toBe('–')
    expect(rows[1]?.querySelector('td:last-child')?.textContent).toBe('88')
  })

  it('points the rule question at /rules rather than answering it here', async () => {
    // "Coach the agent or fix the rule?" needs schema field 8 joined to the
    // agent who took the call, which D7 forbids. It is not a plumbing gap.
    renderAt('/agents')

    const link = await screen.findByRole('link', { name: /rules we fail to explain/i })

    expect(link).toHaveAttribute('href', '/rules')
    // The panel body names the decision, so a reader sees why the answer
    // is absent without opening the tooltip — which also names it, hence
    // scoping this to the panel rather than the page.
    const panel = screen.getByText('Coach the agent, or fix the rule?').closest('section')
    expect(within(panel as HTMLElement).getByText(/D7 is open/)).toBeInTheDocument()
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

  it('gives every panel on the detail a column span', async () => {
    // The detail is a twelve-column grid. A child without a span class
    // takes one column of twelve and its contents spill over the panel
    // beside it — which is exactly what a nested `nv-grid` wrapper did
    // here, and what no screenshot-free test would otherwise catch.
    renderAt('/accounts/EMP-1001')
    await screen.findByText(/This account.s calls/)

    const detail = document.querySelector('.nv-acctdetail')

    expect(detail).not.toBeNull()
    for (const child of Array.from((detail as HTMLElement).children)) {
      expect(Array.from(child.classList).some((name) => /^nv-c[0-9]+$/.test(name))).toBe(true)
    }
  })

  it('tints a tile that carries an issue and offers its playbook', async () => {
    // `NV.tile` does three things to a tile with an issue: links the value,
    // tints the tile, and puts "What to do →" underneath. We were doing the
    // first only, so a strip of flat tiles gave the reader nothing to look
    // at first — which is the job of a tile strip.
    renderAt('/accounts/EMP-1001')
    await screen.findByText(/This account.s calls/)

    const unresolved = screen.getByText('Unresolved').closest('.nv-big')

    expect(unresolved).not.toBeNull()
    expect((unresolved as HTMLElement).className).toContain('nv-warm')
    expect(within(unresolved as HTMLElement).getByText(/What to do/)).toBeInTheDocument()
  })

  it('leaves a tile at zero untinted and offers it no playbook', async () => {
    // Zero missed escalations is a good outcome, not a muted warning, and a
    // playbook for a problem nobody has is noise.
    renderAt('/accounts/EMP-1001')
    await screen.findByText(/This account.s calls/)

    const missed = screen.getByText('Escalations missed').closest('.nv-big')

    expect(missed).not.toBeNull()
    expect((missed as HTMLElement).className).not.toContain('nv-hot')
    expect(within(missed as HTMLElement).queryByText(/What to do/)).not.toBeInTheDocument()
  })

  it('states that average call quality is not published, rather than omitting it', async () => {
    // Metric 12 is per agent; rolling it up to an employer is forbidden by
    // the Metrics sheet. The tile is still rendered, because a silently
    // missing figure and a figure we decline to publish read the same to
    // a reader and are not the same thing.
    renderAt('/accounts/EMP-1001')
    await screen.findByText(/This account.s calls/)
    const tiles = screen.getByText(/This account.s calls/).closest('section')

    expect(tiles).not.toBeNull()
    expect(
      within(tiles as HTMLElement).getByText('Average call quality', {
        // The tooltip repeats the phrase; the tile's own label is the one
        // that must be on screen.
        selector: '.nv-k',
      }),
    ).toBeInTheDocument()
    expect(within(tiles as HTMLElement).getByText('Not published')).toBeInTheDocument()
  })

  it('puts no number where the account-level quality average would be', async () => {
    // The assertion that actually keeps the rollup out. The tile's value
    // must never become a score: `scoredCalls` is coverage and lives in the
    // meta line, so the value itself carries no digit at all.
    renderAt('/accounts/EMP-1001')
    await screen.findByText(/This account.s calls/)

    const label = screen.getByText('Average call quality', { selector: '.nv-k' })
    const tile = label.closest('.nv-big')

    expect(tile).not.toBeNull()
    const value = (tile as HTMLElement).querySelector('.nv-v')

    expect(value).not.toBeNull()
    expect(value?.textContent ?? '').not.toMatch(/[0-9]/)
  })

  it('shows the account facts that raise the stakes, as reference not event', async () => {
    // employer.html's structural notes. They are true whether or not
    // anybody called, so the panel says where they came from — a reader who
    // took one for a recent event would respond to the wrong thing.
    renderAt('/accounts/EMP-1001')

    expect(
      await screen.findByText('Account facts that raise the stakes'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Planned contact rate above the book median'),
    ).toBeInTheDocument()
    expect(screen.getByText(/From the workbook, not from these calls/)).toBeInTheDocument()
  })

  it('reconciles the tile counts against the calls the period holds', async () => {
    // The tiles count the risk window; the calls panel lists the selected
    // period. Where they differ the page must say so, or it reads as two
    // numbers contradicting each other. Filters slice, never hide.
    renderAt('/accounts/EMP-1001')

    expect(
      await screen.findByText(/3 of this account.s 9 calls in the selected period/),
    ).toBeInTheDocument()
  })

  it('counts enrolled against eligible, and says how long to the renewal', async () => {
    renderAt('/accounts/EMP-1001')
    await screen.findByText('Cedar Point Workforce Partners', { selector: 'h2' })

    expect(screen.getByText('315 of 420')).toBeInTheDocument()
    expect(screen.getByText('75%')).toBeInTheDocument()
    expect(screen.getByText('in 4 months')).toBeInTheDocument()
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

describe('which problems drive the risk', () => {
  it('ranks the families by the calls they account for', async () => {
    renderAt('/risk')

    expect(await screen.findByText('Which problems drive the risk')).toBeInTheDocument()
    expect(screen.getByText('Unresolved outcome')).toBeInTheDocument()
  })

  it('reports a move inside the noise as counts, never as a change', async () => {
    // Two calls becoming four is "+100%" and also a coin flip. The server
    // sends `beyondNoise`; the panel says nothing moved unless it is true.
    renderAt('/risk')
    await screen.findByText('Which problems drive the risk')

    expect(screen.getByText(/1 → 3, within noise/)).toBeInTheDocument()
  })

  it('keeps a family nobody raised, at zero', async () => {
    // These ten are the flag's own inputs, so "nobody raised this" is a
    // finding about the book rather than a long tail to trim.
    renderAt('/risk')
    await screen.findByText('Which problems drive the risk')

    expect(
      screen.getByText('Exit or market-test language, verbatim'),
    ).toBeInTheDocument()
  })

  it('says a family v9 cannot compute is unavailable, never zero', async () => {
    renderAt('/risk')
    await screen.findByText('Which problems drive the risk')

    expect(screen.getByText('Not available on v9 data')).toBeInTheDocument()
    expect(screen.getByText(/derived composite, not a v9 field/)).toBeInTheDocument()
  })
})

describe('an indicator on the account page', () => {
  it('names the calls it was observed on', async () => {
    // The envelope's rule applies to an indicator as much as to a rate: a
    // family reported on three calls that names none of them cannot be
    // argued with.
    renderAt('/accounts/EMP-1001')

    expect(await screen.findByRole('button', { name: 'C-1' })).toBeInTheDocument()
  })

  it('opens the evidence drawer from a call reference', async () => {
    renderAt('/accounts/EMP-1001')

    await userEvent.click(await screen.findByRole('button', { name: 'C-1' }))

    expect(await screen.findByText('Call C-1')).toBeInTheDocument()
  })

  it('offers what to do about the family, scoped to this account', async () => {
    renderAt('/accounts/EMP-1001')
    await screen.findByRole('button', { name: 'C-1' })

    const links = screen.getAllByRole('link', { name: /What to do/ })

    expect(links.length).toBeGreaterThan(0)
    expect(links.some((link) => link.getAttribute('href')?.includes('EMP-1001'))).toBe(true)
  })
})

describe('the insight strip on an account', () => {
  const generatedCalls = () =>
    (globalThis.fetch as unknown as { mock: { calls: string[][] } }).mock.calls
      .map((call) => String(call[0]))
      .filter((url) => url.includes('screen=account'))

  it('reads the account on sight, keyed to the account on screen', async () => {
    // Back on load by decision: `employer.html` has the strip as part of
    // the page. It costs a model call per account opened, which is why it
    // had been a button — the query is keyed by reference so a second look
    // at the same account is served from cache rather than billed again.
    renderAt('/accounts/EMP-1001')

    await waitFor(() => {
      expect(generatedCalls().length).toBeGreaterThan(0)
    })
    expect(generatedCalls().every((url) => url.includes('employerRef=EMP-1001'))).toBe(true)
  })

  it('renders the unavailable state rather than hiding it', async () => {
    // U2: an explicit state, never a hidden panel — and the figures below
    // are unaffected either way.
    renderAt('/accounts/EMP-1001')

    expect(await screen.findByText(/No model is configured/)).toBeInTheDocument()
    expect(
      screen.getByText('Cedar Point Workforce Partners', { selector: 'h2' }),
    ).toBeInTheDocument()
  })
})

/**
 * An account flagged on metric 10 whose indicator families could not be
 * tested — Junipero Restaurant Group in the real corpus.
 *
 * Three calls: over metric 10's eligibility floor of three, under the
 * indicator floor of five. So the flag is real and evidenced, and every one
 * of the ten families comes back `observed: false` without having been
 * looked at. Two of the three calls carry a complaint, which is what makes
 * the bare nought a false statement rather than an unhelpful one.
 */
const UNASSESSED_FAMILY_REASON =
  'This account has 3 calls in the window and the ten families are assessed from 5. ' +
  'They were not checked, which is not the same as none being present.'

const THIN_FAMILIES = [
  {
    code: 'complaint_choice',
    label: 'Complaint attributed to Choice',
    observed: false,
    hits: 2,
    employerCalls: 3,
    rate: 0.67,
    available: true,
    assessable: false,
    unavailableBecause: '',
    unassessableBecause: UNASSESSED_FAMILY_REASON,
    callIds: ['C-0067', 'C-0068'],
  },
  {
    code: 'exit_language',
    label: 'Exit or market-test language, verbatim',
    observed: false,
    hits: 0,
    employerCalls: 3,
    rate: 0,
    available: true,
    assessable: false,
    unavailableBecause: '',
    unassessableBecause: UNASSESSED_FAMILY_REASON,
    callIds: [],
  },
]

const RISK_THIN = {
  ...RISK,
  assessed: [
    {
      ...ASSESSED,
      calls: 3,
      flagged: true,
      state: 'Flagged: 2 of 4 conditions met. Too few calls to quote this as a figure.',
      conditionsMet: 2,
      observations: THIN_FAMILIES,
    },
  ],
  assessedCount: 1,
  ineligible: ['EMP-1002'],
  ineligibleCount: 1,
}

describe('an account flagged below the indicator floor', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: string) =>
        Promise.resolve(
          new Response(
            JSON.stringify(
              input.includes('/insights/risk')
                ? RISK_THIN
                : input.includes('/insights/accounts/')
                  ? { ...ACCOUNT, risk: { ...ACCOUNT.risk, observations: THIN_FAMILIES } }
                  : routeFor(input),
            ),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
        ),
      ),
    )
  })

  it('does not put a nought beside the flag when nothing could be counted', async () => {
    // The defect this exists to stop. "Flagged 0" reads as a flag with
    // nothing behind it, when the truth is that the families were never
    // tested — and two of this account's three calls carry a complaint.
    renderAt('/accounts')

    const picker = await screen.findByLabelText('Accounts')
    const flagged = within(picker).getByText('Flagged').closest('span')

    expect(flagged).not.toBeNull()
    expect(within(flagged as HTMLElement).queryByText('0')).not.toBeInTheDocument()
  })

  it('says the families were not assessed, rather than counting them', async () => {
    renderAt('/accounts/EMP-1001')

    expect(await screen.findByText(/Other conditions observed — not assessed/)).toBeInTheDocument()
    expect(screen.getByText(UNASSESSED_FAMILY_REASON)).toBeInTheDocument()
  })

  it('never calls a family with hits "not observed"', async () => {
    // A complaint attributed to Choice on two of three calls was observed.
    // What did not happen is that it cleared a gate nobody could apply.
    renderAt('/accounts/EMP-1001')

    expect(await screen.findByText('2 of 3 calls, not assessed')).toBeInTheDocument()
    expect(screen.queryByText('not observed')).not.toBeInTheDocument()
  })
})

describe('actions for one account', () => {
  it('asks the server for that account’s actions rather than filtering the board', async () => {
    // The panel used to fetch the whole board and filter it against
    // `risk.evidence` — the calls behind metric 10's *fired conditions*.
    // Every seeded action leaves `employerRef` null and reaches an account
    // only through its calls, so an account with nothing flagged matched
    // nothing and the panel said none of its calls had needed an action.
    const seen: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn((input: string) => {
        seen.push(input)
        return Promise.resolve(
          new Response(JSON.stringify(routeFor(input)), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        )
      }),
    )

    renderAt('/accounts/EMP-1001')

    await waitFor(() => {
      expect(seen.some((url) => url.includes('/insights/actions/board'))).toBe(true)
    })
    const board = seen.filter((url) => url.includes('/insights/actions/board'))
    expect(board.every((url) => url.includes('employer=EMP-1001'))).toBe(true)
  })
})

describe('a book-wide action on an account page', () => {
  /** One card whose figures are the corpus's, on an account holding 2 of its calls. */
  const SHARED = {
    ...ACTION_BOARD,
    actions: [
      {
        id: 1,
        reference: 'ACT-1',
        title: 'Member communication gap — 179 calls',
        sourceKind: 'signal',
        issueKey: 'member_communication_gap',
        evidence: 'Calls raising the signal are rising across the quarter.',
        ownerTeam: 'Service',
        owner: null,
        priority: 'medium',
        status: 'needs_action',
        statusLabel: 'Needs action',
        pastDue: false,
        employerRef: null,
        callIds: ['C-1', 'C-2', 'C-3'],
        callsOnAccount: 2,
        label: 'Member communication gap',
        steps: [],
        log: [],
        createdAt: '2026-09-01T00:00:00Z',
        assignedOn: null,
        due: null,
        actionTaken: null,
        outcome: null,
        measurementWindow: null,
        sourceDetail: null,
        recommendation: null,
      },
    ],
  }

  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: string) =>
        Promise.resolve(
          new Response(
            JSON.stringify(
              input.includes('/insights/actions/board') ? SHARED : routeFor(input),
            ),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
        ),
      ),
    )
  })

  it('shows the account’s share beside the card’s own corpus-wide figure', async () => {
    // "179 calls" under a heading reading "Actions for this account", on an
    // account with far fewer than that, is out by an order of magnitude.
    // Both numbers belong on the card; only one of them is this account's.
    renderAt('/accounts/EMP-1001')

    expect(await screen.findByText('Member communication gap — 2 / 3 calls')).toBeInTheDocument()
    // The stored title, with the book's count in it, is not what an account
    // page shows: 179 under "Actions for this account" reads as this
    // account's and is out by an order of magnitude.
    expect(screen.queryByText(/179 calls/)).not.toBeInTheDocument()
  })

  it('says once, not on every row, that the cards count the whole book', async () => {
    // The evidence line is a trend claim about the corpus — "rising across
    // the quarter". Labelling every row with that repeated the panel's own
    // subtitle once per card; the ratio above already separates the two
    // numbers, which is what a reader can actually misread.
    renderAt('/accounts/EMP-1001')

    expect(await screen.findByText(/Book-wide actions touching this account/)).toBeInTheDocument()
    expect(screen.queryByText(/Across the book:/)).not.toBeInTheDocument()
  })
})
