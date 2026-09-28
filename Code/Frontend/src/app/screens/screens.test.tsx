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
