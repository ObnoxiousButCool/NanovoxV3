/**
 * `/v2/overview` — the designer's new page, built on the same real queries
 * `/exec` and `/risk` already use.
 *
 * These tests check the one thing that matters for a page built from a
 * mockup: that a figure with no clean backend equivalent is relabelled to
 * what the corpus actually supports, rather than quietly printed under the
 * mockup's own wording over a number that does not mean it.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from '@/app/App'
import { createQueryClient } from '@/app/queryClient'

function observations(n: number) {
  return Array.from({ length: 10 }, (_, i) => ({
    code: `family_${String(i)}`,
    label: `Family ${String(i)}`,
    observed: i < n,
    hits: i < n ? 2 : 0,
    employerCalls: 9,
    rate: 0.2,
    available: true,
  }))
}

const OPTIONS = {
  agents: [],
  brokers: [],
  categories: [],
  complaintTargets: [],
  controlExceptionTypes: [],
  corpusPeriod: null,
  employers: [
    { ref: 'EMP-1001', name: 'Acme Health', region: 'West' },
    { ref: 'EMP-1002', name: 'WellBridge', region: 'East' },
    { ref: 'EMP-1003', name: 'CarePlus Group', region: 'East' },
  ],
  intents: [],
  outcomes: [],
  productLines: [],
  qualityBands: [],
  regions: [],
  ruleConfidences: [],
}

const EXEC = {
  scope: {},
  asOf: '2026-10-05',
  calls: 100,
  metrics: [],
  escalation: [],
  intentRouted: { value: null, published: false, n: 0, callIds: [], basis: null, withheldReason: null, caveats: [] },
  trends: {
    windowStart: '2026-09-07',
    windowEnd: '2026-10-05',
    windowWeeks: 4,
    priorStart: '2026-08-10',
    priorEnd: '2026-09-06',
    weeks: [],
    movements: [],
    emerging: [
      {
        kind: 'category',
        key: 'billing',
        label: 'Billing disputes',
        buckets: [{ start: '2026-09-07', end: '2026-09-13', calls: 20, hits: 2 }],
        delta: 9,
        rising: true,
        receded: false,
      },
      {
        kind: 'signal',
        key: 'minor_wording',
        label: 'Minor wording drift',
        buckets: [{ start: '2026-09-07', end: '2026-09-13', calls: 20, hits: 1 }],
        delta: 2,
        rising: true,
        receded: false,
      },
    ],
  },
}

const RISK = {
  scope: {},
  asOf: '2026-10-05',
  windowWeeks: 12,
  assessed: [
    {
      employerRef: 'EMP-1001',
      calls: 12,
      eligible: true,
      flagged: true,
      quotable: true,
      state: 'Flagged',
      conditionsMet: 3,
      conditions: [],
      evidence: [],
      observations: observations(5),
      renewalMonth: 'March',
      monthsToRenewal: 6,
    },
    {
      employerRef: 'EMP-1002',
      calls: 9,
      eligible: true,
      flagged: true,
      quotable: true,
      state: 'Flagged',
      conditionsMet: 2,
      conditions: [],
      evidence: [],
      observations: observations(2),
      renewalMonth: 'November',
      monthsToRenewal: 1,
    },
    {
      employerRef: 'EMP-1003',
      calls: 4,
      eligible: true,
      flagged: false,
      quotable: false,
      state: 'Not flagged',
      conditionsMet: 0,
      conditions: [],
      evidence: [],
      observations: observations(0),
      renewalMonth: 'January',
      monthsToRenewal: 3,
    },
  ],
  assessedCount: 3,
  ineligible: [],
  ineligibleCount: 0,
  flaggedShare: { value: 2 / 3, published: true, n: 3, callIds: [], basis: null, withheldReason: null, caveats: [] },
  exposure: { employers: ['EMP-1001', 'EMP-1002'], lives: 250, annualPremium: 0, premiumIncomplete: false, caveat: '' },
  bandCalibration: { withheldReason: { code: 'NO_OUTCOMES', label: 'Withheld' }, n: 0, caveats: [] },
  drivers: [
    { code: 'repeat_contact', label: 'Repeat contact', calls: 40, callIds: [], available: true, unavailableBecause: '' },
    { code: 'exit_language', label: 'Exit language', calls: 30, callIds: [], available: true, unavailableBecause: '' },
    { code: 'escalation', label: 'Escalation', calls: 20, callIds: [], available: true, unavailableBecause: '' },
    { code: 'control_gap', label: 'Control gap', calls: 10, callIds: [], available: true, unavailableBecause: '' },
    { code: 'sentiment', label: 'Sentiment', calls: 6, callIds: [], available: true, unavailableBecause: '' },
    { code: 'knowledge_gap', label: 'Knowledge gap', calls: 4, callIds: [], available: true, unavailableBecause: '' },
    { code: 'no_data', label: 'No v9 field', calls: 0, callIds: [], available: false, unavailableBecause: 'no field' },
  ],
}

const ACTION_BOARD = {
  lanes: [
    { code: 'needs_action', label: 'Needs action', open: true, requires: [] },
    { code: 'in_progress', label: 'In progress', open: true, requires: [] },
    { code: 'completed', label: 'Completed', open: false, requires: [] },
  ],
  actions: [
    {
      id: 1,
      reference: 'ACT-001',
      title: 'Follow up on billing complaint — 4 calls',
      label: 'Follow up on billing complaint',
      employerRef: 'EMP-1001',
      brokerRef: null,
      status: 'needs_action',
      statusLabel: 'Needs action',
      pastDue: false,
      priority: 'high',
      ownerTeam: 'Service',
      owner: null,
      createdAt: '2026-10-01T00:00:00Z',
      due: null,
      assignedOn: null,
      actionTaken: null,
      outcome: null,
      log: [],
      steps: [],
      callIds: ['C-1'],
      evidence: '',
      issueKey: null,
      sourceKind: 'manual',
      sourceDetail: null,
      measurementWindow: null,
      recommendation: null,
      callsOnAccount: null,
    },
    {
      id: 2,
      reference: 'ACT-002',
      title: 'Confirm fix with WellBridge — 2 calls',
      label: 'Confirm fix with WellBridge',
      employerRef: 'EMP-1002',
      brokerRef: null,
      status: 'in_progress',
      statusLabel: 'In progress',
      pastDue: false,
      priority: 'medium',
      ownerTeam: 'Service',
      owner: null,
      createdAt: '2026-09-30T00:00:00Z',
      due: null,
      assignedOn: null,
      actionTaken: null,
      outcome: null,
      log: [],
      steps: [],
      callIds: ['C-2'],
      evidence: '',
      issueKey: null,
      sourceKind: 'manual',
      sourceDetail: null,
      measurementWindow: null,
      recommendation: null,
      callsOnAccount: null,
    },
  ],
  trustNote: '',
}

const CALLS = {
  rows: [],
  total: 0,
  page: 1,
  pages: 1,
  perPage: 25,
  scope: {},
  unresolvedCount: 17,
  escalationsMissedCount: 0,
}

function routeFor(url: string): unknown {
  if (url.includes('/insights/filters')) return OPTIONS
  if (url.includes('/insights/exec')) return EXEC
  if (url.includes('/insights/risk')) return RISK
  if (url.includes('/insights/actions/board')) return ACTION_BOARD
  if (url.includes('/insights/calls')) return CALLS
  return {}
}

function renderOverview(): void {
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

  render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter initialEntries={['/v2/overview']}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('/v2/overview', () => {
  it('counts every stat tile from a real query, not a figure typed into the mockup', async () => {
    renderOverview()

    await screen.findByText('Total accounts')
    // 3 employers from /insights/filters.
    expect(screen.getByText('Total accounts').previousSibling).toHaveTextContent('3')
    // 2 flagged accounts from /insights/risk.
    expect(screen.getByText('Flagged accounts').previousSibling).toHaveTextContent('2')
    // unresolvedCount from /insights/calls, not the mockup's own 17 typed in.
    expect(screen.getByText('Unresolved interactions').previousSibling).toHaveTextContent('17')
    // 2 open actions (needs_action + in_progress), 0 completed.
    expect(screen.getByText('Open actions').previousSibling).toHaveTextContent('2')
  })

  it('relabels the per-account figure honestly instead of calling it unresolved interactions', async () => {
    renderOverview()

    const list = await screen.findByRole('list', { name: 'Flagged accounts' })

    // monthsToRenewal, never the mockup's "days".
    expect(screen.getByText('1 month')).toBeInTheDocument()
    expect(screen.getByText('6 months')).toBeInTheDocument()
    expect(screen.getAllByText('Renewal in').length).toBeGreaterThan(0)
    // The account's real indicator count, not a fabricated interaction tally.
    expect(screen.getByText('2 indicators flagged')).toBeInTheDocument()
    expect(screen.getByText('5 indicators flagged')).toBeInTheDocument()
    // Soonest renewal first (WellBridge, 1 month) ahead of Acme Health (6).
    const names = within(list)
      .getAllByRole('listitem')
      .map((item) => item.querySelector('b')?.textContent)
    expect(names.indexOf('WellBridge')).toBeLessThan(names.indexOf('Acme Health'))
  })

  it('breaks the donut down by indicator family, not the mockup\'s illustrative categories', async () => {
    renderOverview()

    await screen.findByText('Risk Overview')

    expect(screen.getByText('Repeat contact')).toBeInTheDocument()
    expect(screen.getByText('Exit language')).toBeInTheDocument()
    // The 5th+ available drivers fold into one "Others" slice rather than a
    // fifth hand-picked hue.
    expect(screen.getByText('Others (2 families)')).toBeInTheDocument()
    // Unavailable families never appear, named or in the fold.
    expect(screen.queryByText(/No v9 field/)).not.toBeInTheDocument()
  })

  it('shows the dot bubble only when a label no longer fits its column, not by word count', async () => {
    // jsdom reports 0 for scrollWidth and clientWidth on everything; stand
    // in with a deterministic per-character width so a short and a long
    // label land on opposite sides of the same measured column.
    vi.spyOn(HTMLElement.prototype, 'scrollWidth', 'get').mockImplementation(function (
      this: HTMLElement,
    ) {
      return (this.textContent?.length ?? 0) * 8
    })
    vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(200)

    vi.stubGlobal(
      'fetch',
      vi.fn((input: string) =>
        Promise.resolve(
          new Response(
            JSON.stringify(
              input.includes('/insights/risk')
                ? {
                    ...RISK,
                    drivers: [
                      // Every real indicators.py label is three words or
                      // fewer today; this is a synthetic one so the
                      // measurement path stays exercised regardless.
                      {
                        code: 'synthetic_family',
                        label: 'Repeat contact from the same caller',
                        calls: 40,
                        callIds: [],
                        available: true,
                        unavailableBecause: '',
                      },
                      // Fits the same column: no bubble.
                      {
                        code: 'high_effort',
                        label: 'High member effort',
                        calls: 10,
                        callIds: [],
                        available: true,
                        unavailableBecause: '',
                      },
                    ],
                  }
                : routeFor(input),
            ),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
        ),
      ),
    )

    render(
      <QueryClientProvider client={createQueryClient()}>
        <MemoryRouter initialEntries={['/v2/overview']}>
          <App />
        </MemoryRouter>
      </QueryClientProvider>,
    )

    await screen.findByText('Risk Overview')

    // Fits the column: the label itself, no dots.
    expect(screen.getByText('High member effort')).toBeInTheDocument()
    // Does not fit: the full text is still in the DOM for an assistive-tech
    // reader — CSS ellipsis clips the render, never the content —
    expect(screen.getByText('Repeat contact from the same caller')).toBeInTheDocument()
    // — and a bubble sits beside it for anyone hovering or tabbing to let it
    // wrap back out in place.
    expect(screen.getByLabelText('Show the full label')).toHaveTextContent('•••')
  })

  it('shows the real call count on a rising issue instead of the mockup\'s percentage', async () => {
    renderOverview()

    await screen.findByText('Emerging issues')

    expect(screen.getByText('Billing disputes')).toBeInTheDocument()
    expect(screen.getByText('+9 calls')).toBeInTheDocument()
    expect(screen.queryByText('+12%')).not.toBeInTheDocument()
  })

  it('colours each recent action by the lane it actually sits in', async () => {
    renderOverview()

    await screen.findByText('Follow up on billing complaint')

    expect(screen.getByText('Needs action')).toBeInTheDocument()
    expect(screen.getByText('In progress')).toBeInTheDocument()
  })
})
