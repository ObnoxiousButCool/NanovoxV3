/**
 * The filter bar, tested for the things that would be wrong but plausible.
 *
 * The URL being the source of truth is the assertion that matters most: a
 * mirrored copy works identically until someone shares a link, and then the
 * colleague sees different figures under the same address.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createQueryClient } from '@/app/queryClient'
import { FilterBar } from '@/shared/filters/FilterBar'

const OPTIONS = {
  regions: ['Midwest', 'West'],
  brokers: [{ ref: 'BRK-01', agency: 'Adler Benefits', name: 'A Adler', region: 'West' }],
  employers: [
    { ref: 'EMP-01', name: 'Northwind Traders', region: 'West', brokerRef: 'BRK-01' },
  ],
  agents: [{ ref: 'AG-01', name: 'Dana Vale', band: 'Senior' }],
  touchpoints: ['enrolment_meeting'],
  categories: ['Coverage & Benefits'],
  signals: [{ code: 'billing_defect', label: 'Billing defect' }],
  signalSeverities: [],
  complaintTargets: [{ code: 'CHOICE', label: 'Choice' }],
  controlExceptionTypes: [],
  ruleLayers: [],
  ruleConfidences: [],
  productLines: [{ code: 'dental', label: 'Dental' }],
  outcomes: [{ code: 'RESOLVED', label: 'Resolved' }],
  intents: [{ code: 'market_test', label: 'Testing the market' }],
  qualityBands: [{ code: 'GOOD', label: 'Good' }],
  unlabelledFilters: ['category'],
}

function stubApi(body: unknown = OPTIONS, status = 200): void {
  // A fresh `Response` per call, not `mockResolvedValue` with one shared
  // instance — a `Response` body can only be read once, and selecting a
  // filter changes `useFilterOptions`'s query key, which refetches.
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation(
      () =>
        new Response(JSON.stringify(body), {
          status,
          headers: { 'Content-Type': 'application/json' },
        }),
    ),
  )
}

function Address() {
  const { search } = useLocation()
  return <output data-testid="address">{search}</output>
}

function setup(at = '/exec') {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter initialEntries={[at]}>
        <FilterBar />
        <Address />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('FilterBar', () => {
  it('writes a selection into the address, not into local state', async () => {
    // A mirrored copy behaves identically until someone shares the link.
    stubApi()
    const user = userEvent.setup()
    setup()

    await screen.findByRole('option', { name: 'West' })
    await user.selectOptions(screen.getByRole('combobox', { name: /region/i }), 'West')

    expect(screen.getByTestId('address')).toHaveTextContent('region=West')
  })

  it('reads its state back out of the address', async () => {
    stubApi()
    setup('/exec?region=West&region=Midwest')

    expect(await screen.findByText(/Region: West/)).toBeInTheDocument()
    expect(screen.getByText(/Region: Midwest/)).toBeInTheDocument()
  })

  it('repeats a parameter rather than joining values with a separator', async () => {
    // Workbook category names contain `&` and spaces, so any separator can
    // appear inside a value.
    stubApi()
    setup('/exec?region=West&region=Midwest')

    const address = await screen.findByTestId('address')
    expect(address).toHaveTextContent('region=West')
    expect(address).toHaveTextContent('region=Midwest')
    expect(address.textContent).not.toContain('West,Midwest')
  })

  it('shows a chip per applied filter, with the label rather than the code', async () => {
    stubApi()
    setup('/exec?broker=BRK-01')

    // BRK-01 is what the API takes; "Adler Benefits" is what a reader knows.
    expect(await screen.findByText(/Broker: Adler Benefits/)).toBeInTheDocument()
  })

  it('removes one value without clearing the rest of that filter', async () => {
    stubApi()
    const user = userEvent.setup()
    setup('/exec?region=West&region=Midwest')

    const chip = await screen.findByRole('button', { name: 'Remove Region filter West' })
    await user.click(chip)

    const address = screen.getByTestId('address')
    expect(address).toHaveTextContent('region=Midwest')
    expect(address.textContent).not.toContain('region=West')
  })

  it('always states the scope, so a narrow screen is not read as an empty one', async () => {
    // plan.md §9: filters slice, never hide.
    stubApi()
    setup('/exec?region=West')

    expect(await screen.findByText('1 filters applied')).toBeInTheDocument()
  })

  it('counts what is hidden behind Advanced', async () => {
    stubApi()
    setup('/exec?signal=billing_defect&escalated=true')

    const advanced = await screen.findByRole('button', { name: /Advanced filters/ })
    expect(advanced).toHaveTextContent('2')
  })

  it('counts an unset flag as unset rather than crashing', async () => {
    // `key in filters.flags` is false for an unset flag, which sent the
    // count down the multi-value branch where flag keys do not exist.
    stubApi()
    setup('/exec')

    expect(await screen.findByRole('button', { name: /Advanced filters/ })).toBeInTheDocument()
  })

  it('reveals the advanced filters on request', async () => {
    stubApi()
    const user = userEvent.setup()
    setup()

    await user.click(await screen.findByRole('button', { name: /Advanced filters/ }))

    expect(screen.getByRole('combobox', { name: /signal/i })).toBeInTheDocument()
  })

  it('offers a real, pickable option for every advanced filter, not just signal', async () => {
    // These five were wired into the Advanced panel with no options behind
    // them: `options` never carried category/productLine/outcome/intent/
    // qualityBand, so each select stayed on "Loading…", permanently
    // disabled, regardless of what `/insights/filters` returned.
    stubApi()
    const user = userEvent.setup()
    setup()

    await user.click(await screen.findByRole('button', { name: /Advanced filters/ }))

    // Each selection changes the URL, which re-keys `useFilterOptions` and
    // refetches — so the next select is briefly back to "Loading…" until
    // that settles. Waiting for the real option before picking it is what a
    // reader effectively does too.
    const pick = async (name: RegExp, value: string) => {
      const select = await screen.findByRole('combobox', { name })
      await waitFor(() => {
        expect(select).not.toBeDisabled()
      })
      await user.selectOptions(select, value)
    }

    await pick(/topic/i, 'Coverage & Benefits')
    await pick(/product line/i, 'dental')
    await pick(/^outcome/i, 'RESOLVED')
    await pick(/^intent/i, 'market_test')
    await pick(/call quality/i, 'GOOD')

    const address = screen.getByTestId('address').textContent ?? ''
    expect(address).toContain('category=Coverage')
    expect(address).toContain('productLine=dental')
    expect(address).toContain('outcome=RESOLVED')
    expect(address).toContain('intent=market_test')
    expect(address).toContain('qualityBand=GOOD')
  })

  it('filters on repeat contact, in words a reader can act on', async () => {
    // The API has carried `repeat` since Phase 1 and nothing offered it, so
    // the one filter the prototype has that this bar did not was simply
    // unreachable.
    //
    // Not labelled Yes/No. "Repeat contact: No" reads as "no repeat was
    // recorded" -- an absence of data -- where what it selects is calls
    // positively known not to be one. That is the withheld-is-not-zero
    // mistake in a dropdown.
    stubApi()
    const user = userEvent.setup()
    setup()

    await user.click(await screen.findByRole('button', { name: /Advanced filters/ }))
    const select = await screen.findByRole('combobox', { name: /repeat contact/i })

    expect(within(select).getByRole('option', { name: 'Repeat only' })).toBeInTheDocument()
    expect(within(select).getByRole('option', { name: 'First contact only' })).toBeInTheDocument()
    expect(within(select).getByRole('option', { name: 'Any' })).toBeInTheDocument()

    await user.selectOptions(select, 'true')

    expect(screen.getByTestId('address').textContent ?? '').toContain('repeat=true')
    // The chip says what the dropdown said, not "yes".
    expect(screen.getByText(/Repeat contact: Repeat only/)).toBeInTheDocument()
  })

  it('keeps first-contact-only distinct from unset', async () => {
    // `false` is a real selection the API honours; absent narrows nothing.
    stubApi()
    const user = userEvent.setup()
    setup()

    await user.click(await screen.findByRole('button', { name: /Advanced filters/ }))
    await user.selectOptions(await screen.findByRole('combobox', { name: /repeat contact/i }), 'false')

    expect(screen.getByTestId('address').textContent ?? '').toContain('repeat=false')
    expect(screen.getByText(/Repeat contact: First contact only/)).toBeInTheDocument()
  })

  it('resets everything at once', async () => {
    stubApi()
    const user = userEvent.setup()
    setup('/exec?region=West&signal=billing_defect')

    await user.click(await screen.findByRole('button', { name: 'Reset all' }))

    expect(screen.getByTestId('address').textContent).not.toContain('region')
    expect(screen.getByTestId('address').textContent).not.toContain('signal')
  })

  it('clears what the screen owns as well as what the bar owns', async () => {
    // The button is called Reset all and left `q`, `sort`, `order` and
    // `perPage` behind, so a reader who pressed it was still looking at a
    // searched, sorted, resized list. `page` goes too: a page number kept
    // across a reset points into a result the reset just resized.
    stubApi()
    const user = userEvent.setup()
    setup('/calls?region=West&q=ironwood&sort=quality&order=asc&page=2&perPage=50')

    await user.click(await screen.findByRole('button', { name: 'Reset all' }))

    const address = screen.getByTestId('address').textContent ?? ''
    expect(address).toBe('')
  })

  it('clears the period and the action board’s own state', async () => {
    // Neither carries a chip, and both narrow what is on screen.
    stubApi()
    const user = userEvent.setup()
    setup('/actions?period=month&from=2026-07-06&to=2026-07-31&stage=needs_action&focus=unresolved')

    await user.click(await screen.findByRole('button', { name: 'Reset all' }))

    expect(screen.getByTestId('address').textContent).toBe('')
  })

  it('is offered while a period alone is set, which carries no chip', async () => {
    // It went grey over a plainly narrowed screen, because it was driven by
    // the chip count and a period shows in its own control instead.
    stubApi()
    setup('/exec?period=month&from=2026-07-06&to=2026-07-31')

    expect(await screen.findByRole('button', { name: 'Reset all' })).toBeEnabled()
  })

  it('is offered while only a search term is set', async () => {
    stubApi()
    setup('/calls?q=ironwood')

    expect(await screen.findByRole('button', { name: 'Reset all' })).toBeEnabled()
  })

  it('offers nothing to reset when nothing is set', async () => {
    stubApi()
    setup()

    expect(await screen.findByRole('button', { name: 'Reset all' })).toBeDisabled()
  })

  it('says so when the options could not be loaded', async () => {
    // Silently showing empty dropdowns would read as "there are no brokers".
    stubApi({ title: 'Bad request' }, 400)
    setup()

    expect(await screen.findByText(/Filter options unavailable/)).toBeInTheDocument()
  })

  it('distinguishes a flag set to no from a flag left unset', async () => {
    stubApi()
    const user = userEvent.setup()
    setup('/exec')

    await user.click(await screen.findByRole('button', { name: /Advanced filters/ }))
    await user.selectOptions(screen.getByRole('combobox', { name: /^escalated$/i }), 'false')

    // Not absent, and not `true`. The API treats the three differently.
    expect(screen.getByTestId('address')).toHaveTextContent('escalated=false')
  })
})

describe('the period control', () => {
  it('keeps the mode when switching, rather than losing it to the date clear', async () => {
    // The bug this pins: switching mode wrote the mode and then cleared the
    // dates as two separate calls. `setSearchParams` navigates from the
    // router's current state, which does not advance between synchronous
    // calls, so the second navigation was computed from the same starting
    // point and silently discarded the first. The mode vanished and the
    // control snapped back to Week.
    stubApi({ ...OPTIONS, corpusPeriod: { from: '2026-07-06', to: '2026-09-25' } })
    const user = userEvent.setup()
    setup('/risk')

    await user.click(await screen.findByRole('button', { name: 'Month' }))

    expect(screen.getByTestId('address')).toHaveTextContent('period=month')
    expect(screen.getByRole('button', { name: 'Month' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('offers real weeks built from the corpus extent', async () => {
    stubApi({ ...OPTIONS, corpusPeriod: { from: '2026-07-06', to: '2026-09-25' } })
    setup('/risk')

    // Seven-day weeks, not the prototype's Monday-to-Friday indices.
    expect(await screen.findByRole('option', { name: 'Wk 1 · 6 Jul – 12 Jul' })).toBeInTheDocument()
  })

  it('offers real calendar months, not four-week blocks', async () => {
    // The prototype's "Aug" is 3–28 August and drops five days silently.
    stubApi({ ...OPTIONS, corpusPeriod: { from: '2026-07-06', to: '2026-09-25' } })
    const user = userEvent.setup()
    setup('/risk')

    await user.click(await screen.findByRole('button', { name: 'Month' }))
    await user.selectOptions(screen.getByRole('combobox', { name: 'Month' }), ['2026-08-01|2026-08-31'])

    expect(screen.getByTestId('address')).toHaveTextContent('from=2026-08-01')
    expect(screen.getByTestId('address')).toHaveTextContent('to=2026-08-31')
  })

  it('does not send interface-only keys to the API', async () => {
    // `period` restores the picker; `stage` narrows the action board in the
    // browser and `focus` chooses a playbook. None is a filter, and none is
    // documented on any endpoint — a request carrying one leaves the next
    // person working out whether it mattered.
    stubApi({ ...OPTIONS, corpusPeriod: { from: '2026-07-06', to: '2026-09-25' } })
    setup('/risk?period=month&stage=needs_action&focus=unresolved&region=West')

    await screen.findByText(/Region: West/)
    const calls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls as [string][]
    for (const key of ['period=', 'stage=', 'focus=']) {
      expect(calls.some(([url]) => url.includes(key))).toBe(false)
    }
    expect(calls.some(([url]) => url.includes('region=West'))).toBe(true)
  })
})
