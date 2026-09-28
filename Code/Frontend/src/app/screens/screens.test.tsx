/**
 * The four read screens, in the states a reader can actually land in.
 *
 * These test what the screens **refuse to say**, not that they render. A
 * screen that draws the right boxes and quietly turns a withheld figure
 * into 0%, or ninety unassessable accounts into ninety unflagged ones, has
 * passed every test worth failing and is still wrong.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
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
    { ref: 'EMP-1001', name: 'Cedar Point Workforce Partners' },
    { ref: 'EMP-1002', name: 'Park Mechanical' },
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
  if (url.includes('/insights/exec')) return EXEC
  if (url.includes('/insights/risk')) return RISK
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

    await waitFor(() => {
      expect(screen.getByText('Unresolved outcome')).toBeInTheDocument()
    })
    // A family that did not fire is not named in the row — the count says
    // how many of ten, so absence is already legible without listing eight.
    expect(screen.queryByText('High member effort')).not.toBeInTheDocument()
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
