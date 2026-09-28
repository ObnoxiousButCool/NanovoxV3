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

  it('says so when there is nothing, rather than disappearing', () => {
    // U2: an explicit unavailable state, never a silently hidden panel.
    show(<InsightStrip data={UNAVAILABLE} />)

    expect(screen.getByLabelText('Generated insights')).toBeInTheDocument()
    expect(screen.getByText(/No model is configured/)).toBeInTheDocument()
  })

  it('names no figure it could not write about', () => {
    show(<InsightStrip data={UNAVAILABLE} />)

    expect(screen.queryByText(/%/)).not.toBeInTheDocument()
  })

  it('carries the badge in both states', () => {
    const { unmount } = render(
      <MemoryRouter>
        <InsightStrip data={GENERATED} />
      </MemoryRouter>,
    )
    expect(screen.getByText('AI')).toBeInTheDocument()
    unmount()

    show(<InsightStrip data={UNAVAILABLE} />)
    expect(screen.getByText('AI')).toBeInTheDocument()
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
    show(<InsightFeed data={GENERATED} />)

    expect(screen.queryByText(/first_contact_resolution/)).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /What this insight read/ }))

    expect(screen.getByText(/first_contact_resolution/)).toBeInTheDocument()
  })

  it('offers a what-to-do link for a playbook this build ships', async () => {
    show(<InsightFeed data={{ ...GENERATED, insights: [insight({ issueKey: 'unresolved' })] }} />)

    await userEvent.click(screen.getByRole('button', { name: /What this insight read/ }))

    expect(screen.getByRole('link', { name: /What to do/ })).toBeInTheDocument()
  })

  it('drops the link for a key this build holds back', async () => {
    // `brush_off` is held back with archetype (D14/C8a). A link to it would
    // focus the actions page on something it cannot show.
    show(<InsightFeed data={{ ...GENERATED, insights: [insight({ issueKey: 'brush_off' })] }} />)

    await userEvent.click(screen.getByRole('button', { name: /What this insight read/ }))

    expect(screen.queryByRole('link', { name: /What to do/ })).not.toBeInTheDocument()
    expect(screen.getByText(/Resolution held at 74%/)).toBeInTheDocument()
  })

  it('says who wrote it', () => {
    show(<InsightFeed data={GENERATED} />)

    expect(screen.getByText(/Written by openai/)).toBeInTheDocument()
  })

  it('names no author when nothing was written', () => {
    show(<InsightFeed data={UNAVAILABLE} />)

    expect(screen.queryByText(/Written by/)).not.toBeInTheDocument()
    expect(screen.getByText(/No model is configured/)).toBeInTheDocument()
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

  it('still carries the badge and the promise when the model is down', () => {
    show(<InsightLenses data={UNAVAILABLE} />)

    expect(screen.getByText('AI')).toBeInTheDocument()
    expect(screen.getByText(/No model is configured/)).toBeInTheDocument()
    // The grid does not vanish with the sentences.
    expect(screen.getByRole('heading', { name: 'Payer & carrier' })).toBeInTheDocument()
  })
})
