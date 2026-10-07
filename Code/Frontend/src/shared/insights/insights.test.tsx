/**
 * The AI surface, in the states a reader can land in.
 *
 * What these test is what the surface refuses to do: go missing when there
 * is nothing to say, drop the badge that makes it trustworthy, or link to a
 * playbook this build does not ship.
 */

import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import type { GeneratedInsights, Insight } from '@/shared/api/insights'
import {
  AI_PROMISE,
  InsightFeed,
  InsightLenses,
  InsightStrip,
} from '@/shared/insights/Insights'

function insight(overrides: Partial<Insight> = {}): Insight {
  return {
    key: 'resolution',
    sentence: 'Resolution held at 74% across the period.',
    kind: { code: 'INFERENCE', label: 'What this suggests' },
    severity: { code: 'READ_FIRST', label: 'Read first' },
    lens: { code: 'EMPLOYERS', label: 'Employers' },
    factKeys: ['first_contact_resolution'],
    issueKey: null,
    ...overrides,
  }
}

const GENERATED: GeneratedInsights = {
  status: { code: 'GENERATED', label: 'Generated' },
  lenses: [
    { code: 'EMPLOYERS', label: 'Employers' },
    { code: 'CHURN_AND_RETENTION', label: 'Churn & retention' },
    { code: 'PRODUCT_AND_SERVICE', label: 'Product & service' },
    { code: 'PAYER_AND_CARRIER', label: 'Payer & carrier' },
  ],
  insights: [insight()],
  facts: [
    {
      key: 'first_contact_resolution',
      label: 'First-contact resolution',
      display: '74%',
      n: 141,
      basis: 'OBSERVED',
      withheldReason: null,
    },
    {
      key: 'commercial_intent_capture',
      label: 'Commercial intent capture',
      display: null,
      n: 3,
      basis: 'OBSERVED',
      withheldReason: 'Too few calls to publish',
    },
  ],
  reason: null,
  provider: 'openai',
  model: 'gpt-5',
}

const UNAVAILABLE: GeneratedInsights = {
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

function show(node: React.ReactElement): void {
  render(<MemoryRouter>{node}</MemoryRouter>)
}

describe('the strip', () => {
  it('shows the sentence and how to read it', () => {
    show(<InsightStrip data={GENERATED} />)

    expect(screen.getByText(/Resolution held at 74%/)).toBeInTheDocument()
    expect(screen.getByText('What this suggests')).toBeInTheDocument()
  })

  it('disappears when there is nothing, rather than saying so', () => {
    // U2 revised 2026-10-07: the surface is absent rather than present and
    // empty. The half of U2 that still holds is tested below — nothing
    // templated ever stands in for a generated sentence.
    show(<InsightStrip data={UNAVAILABLE} />)

    expect(screen.queryByLabelText('Generated insights')).not.toBeInTheDocument()
    expect(screen.queryByText(/No model is configured/)).not.toBeInTheDocument()
  })

  it('names no figure it could not write about', () => {
    show(<InsightStrip data={UNAVAILABLE} />)

    expect(screen.queryByText(/%/)).not.toBeInTheDocument()
  })

  it('carries the badge whenever it is on screen at all', () => {
    // There is only one state to carry it in now: a surface with sentences.
    // An empty one is not rendered, so there is no badge to check for.
    const { unmount } = render(
      <MemoryRouter>
        <InsightStrip data={GENERATED} />
      </MemoryRouter>,
    )
    expect(screen.getByText('AI insights')).toBeInTheDocument()
    unmount()

    show(<InsightStrip data={UNAVAILABLE} />)
    expect(screen.queryByText('AI insights')).not.toBeInTheDocument()
  })

  it('renders nothing at all before the query resolves', () => {
    const { container } = render(
      <MemoryRouter>
        <InsightStrip data={undefined} />
      </MemoryRouter>,
    )

    expect(container).toBeEmptyDOMElement()
  })
})

describe('the promise', () => {
  it('states that it never adds a number of its own', () => {
    expect(AI_PROMISE).toMatch(/never calculates, forecasts or adds a number of its own/)
  })

  it('states that the figure wins a disagreement', () => {
    expect(AI_PROMISE).toMatch(/the figure is right/)
  })
})

describe('the feed', () => {
  it('hides what a sentence read until it is asked for', async () => {
    // Asserted on the figure's label, not its key: the card opens to the
    // figures themselves now, and the key is an internal name a reader was
    // never meant to see.
    show(<InsightFeed data={GENERATED} />)

    expect(screen.queryByText('First-contact resolution')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /What this insight read/ }))

    expect(screen.getByText('First-contact resolution')).toBeInTheDocument()
    expect(screen.getByText('74%')).toBeInTheDocument()
  })

  it('keeps the evidence cue’s wording still, and lets the chevron carry the state', async () => {
    // The prototype's `.ai-more`: one label per card that does not change,
    // with `›` and `⌄` supplied by CSS. Ours swapped the word to "Hide
    // evidence" as well, which said the same thing twice and made the cue
    // change width as it opened. `aria-expanded` is what states the toggle,
    // and it is asserted here because it is now the only thing that does.
    show(<InsightFeed data={GENERATED} badgeLabel="Needs attention now" />)

    // The feed opens its first card, as the prototype's first `<details>`
    // carries `open`. So the cue is read on the way closed and back.
    const toggle = screen.getByRole('button', { name: /What this insight read/ })
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Evidence')).toBeInTheDocument()

    await userEvent.click(toggle)

    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.getByText('Evidence')).toBeInTheDocument()
    expect(screen.queryByText(/Hide evidence/)).not.toBeInTheDocument()
  })

  it('opens to the figures themselves, not to their names', () => {
    // The prototype's `.ai-ev` is a row per piece of evidence, the thing on
    // the left and its figure on the right. Ours read
    // "Read from first_contact_resolution" -- which names the evidence
    // without showing it, so the sentence could not be checked against
    // anything without leaving the card.
    show(<InsightFeed data={GENERATED} badgeLabel="Needs attention now" />)

    const rows = screen.getAllByRole('listitem').filter((li) => li.closest('.nv-ai-ev'))

    expect(rows).toHaveLength(1)
    expect(within(rows[0]!).getByText('First-contact resolution')).toBeInTheDocument()
    expect(within(rows[0]!).getByText('74%')).toBeInTheDocument()
    expect(screen.queryByText(/Read from/)).not.toBeInTheDocument()
  })

  it('shows a withheld figure with its reason where the number would be', () => {
    // The model is told about withheld figures and may write about one, so
    // the card has to be able to show it. A row that vanished would make
    // the sentence unverifiable exactly where the reader needs to see why.
    show(
      <InsightFeed
        data={{
          ...GENERATED,
          insights: [insight({ factKeys: ['commercial_intent_capture'] })],
        }}
        badgeLabel="Needs attention now"
      />,
    )

    const row = screen.getAllByRole('listitem').find((li) => li.closest('.nv-ai-ev'))

    expect(within(row!).getByText('Commercial intent capture')).toBeInTheDocument()
    expect(within(row!).getByText('Too few calls to publish')).toBeInTheDocument()
  })

  it('keeps a key the fact set does not carry, rather than dropping the row', () => {
    // The two sides disagreeing should be visible. A silently missing row
    // would read as a sentence with less behind it than it claims.
    show(
      <InsightFeed
        data={{ ...GENERATED, insights: [insight({ factKeys: ['no_such_fact'] })] }}
        badgeLabel="Needs attention now"
      />,
    )

    const row = screen.getAllByRole('listitem').find((li) => li.closest('.nv-ai-ev'))

    expect(within(row!).getByText('no_such_fact')).toBeInTheDocument()
  })

  it('offers a what-to-do link for a playbook this build ships', async () => {
    show(<InsightFeed data={{ ...GENERATED, insights: [insight({ issueKey: 'unresolved' })] }} />)

    await userEvent.click(screen.getByRole('button', { name: /What this insight read/ }))

    expect(screen.getByRole('link', { name: /What to do/ })).toBeInTheDocument()
  })

  it('shows the what-to-do link up front, on a card with no expand of its own to hide it behind', () => {
    // The compact card grid (`/risk`) has no per-card "click to reveal"
    // affordance the way the read-first feed does, so its action cannot
    // wait behind one either — unlike `factKeys`, which still does.
    show(<InsightFeed data={{ ...GENERATED, insights: [insight({ issueKey: 'unresolved' })] }} />)

    expect(screen.getByRole('link', { name: /What to do/ })).toBeInTheDocument()
    expect(screen.queryByText(/first_contact_resolution/)).not.toBeInTheDocument()
  })

  it('drops the link for a key this build holds back', async () => {
    // `brush_off` is held back with archetype (D14/C8a). A link to it would
    // focus the actions page on something it cannot show.
    show(<InsightFeed data={{ ...GENERATED, insights: [insight({ issueKey: 'brush_off' })] }} />)

    await userEvent.click(screen.getByRole('button', { name: /What this insight read/ }))

    expect(screen.queryByRole('link', { name: /What to do/ })).not.toBeInTheDocument()
    expect(screen.getByText(/Resolution held at 74%/)).toBeInTheDocument()
  })

  it('names no provider or model on the page', () => {
    show(<InsightFeed data={GENERATED} />)

    expect(screen.queryByText(/Written by/)).not.toBeInTheDocument()
    expect(screen.queryByText(/openai|gpt/i)).not.toBeInTheDocument()
  })

  it('renders no panel at all when nothing was written', () => {
    const { container } = render(
      <MemoryRouter>
        <InsightFeed data={UNAVAILABLE} />
      </MemoryRouter>,
    )

    expect(container).toBeEmptyDOMElement()
    expect(screen.queryByText(/No model is configured/)).not.toBeInTheDocument()
    // The half of U2 that still holds: nothing templated stood in for it.
    expect(screen.queryByText(/Written by/)).not.toBeInTheDocument()
  })
})

describe('the four lenses', () => {
  it('renders all four even when the model filled only one', () => {
    // U1 makes the lenses a client requirement, so the grid keeps its shape.
    // A reader must be able to tell "nothing to say about churn" from
    // "churn was not considered", and a disappearing column cannot.
    show(<InsightLenses data={GENERATED} />)

    for (const label of [
      'Employers',
      'Churn & retention',
      'Product & service',
      'Payer & carrier',
    ]) {
      expect(screen.getByRole('heading', { name: label })).toBeInTheDocument()
    }
  })

  it('says an empty lens is empty rather than leaving it blank', () => {
    show(<InsightLenses data={GENERATED} />)

    expect(screen.getAllByText(/Nothing in this period/)).toHaveLength(3)
  })

  it('files a sentence under its own lens', () => {
    show(<InsightLenses data={GENERATED} />)

    const employers = screen.getByRole('heading', { name: 'Employers' }).closest('article')

    expect(employers).not.toBeNull()
    expect(within(employers as HTMLElement).getByText(/Resolution held at 74%/)).toBeInTheDocument()
  })

  it('renders nothing when the model is down, grid included', () => {
    // The grid used to survive the sentences, so a reader could tell
    // "nothing to say about churn" from "churn was not considered". With the
    // panel gone there is no grid to hold that distinction, and no claim
    // about churn either — which is the trade U2's revision accepted.
    const { container } = render(
      <MemoryRouter>
        <InsightLenses data={UNAVAILABLE} />
      </MemoryRouter>,
    )

    expect(container).toBeEmptyDOMElement()
    expect(screen.queryByText('AI insights')).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Payer & carrier' })).not.toBeInTheDocument()
  })
})

describe('a strip that must be asked for', () => {
  it('offers to read rather than reading, and says it costs a call', () => {
    show(<InsightStrip data={undefined} onRequest={() => undefined} />)

    expect(screen.getByRole('button', { name: /Read this account/ })).toBeInTheDocument()
    expect(screen.getByText(/costs a call/)).toBeInTheDocument()
  })

  it('carries the badge and the promise before anything is generated', () => {
    show(<InsightStrip data={undefined} onRequest={() => undefined} />)

    expect(screen.getByText('AI insights')).toBeInTheDocument()
  })

  it('says it is reading while the request is in flight', () => {
    show(<InsightStrip data={undefined} onRequest={() => undefined} pending />)

    expect(screen.getByRole('button', { name: 'Reading…' })).toBeDisabled()
  })

  it('still renders nothing where no one is offering to ask', () => {
    // `/exec` and `/risk` load their own surface, so an absent one there is
    // a query in flight rather than an offer.
    const { container } = render(
      <MemoryRouter>
        <InsightStrip data={undefined} />
      </MemoryRouter>,
    )

    expect(container).toBeEmptyDOMElement()
  })
})
