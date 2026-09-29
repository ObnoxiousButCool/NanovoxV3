/**
 * The primitives, tested for the failures that would be silent.
 *
 * A component that renders the wrong font is caught by looking at it. A
 * component that renders a withheld figure as `0`, or lets a seventh column
 * onto a table, looks entirely correct and is wrong. Those are what this
 * file is for.
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { DataTable, Delta, Empty, EpistemicChip, FigureValue, KpiTile, MAX_COLUMNS, Named, Quote, RiskPill, Tooltip, Withheld, basisFromApi } from '@/shared/design/primitives'
import type { Column, Figure, Row } from '@/shared/design/primitives'

function figure(over: Partial<Figure> = {}): Figure {
  return {
    value: 42,
    published: true,
    n: 30,
    basis: { code: 'OBSERVED', label: 'Observed' },
    withheldReason: null,
    caveats: [],
    callIds: [],
    ...over,
  }
}

describe('FigureValue', () => {
  it('renders a published value through its formatter', () => {
    render(<FigureValue figure={figure({ value: 0.42 })} format={(v) => `${String(Math.round(v * 100))}%`} />)

    expect(screen.getByText('42%')).toBeInTheDocument()
  })

  it('never renders a withheld figure as a zero', () => {
    // The single most important assertion in the design system. Zero reads
    // as good news where the truth is absence of evidence.
    render(
      <FigureValue
        figure={figure({
          published: false,
          value: null,
          withheldReason: { code: 'BELOW_MIN_N', label: 'Too few calls to publish' },
        })}
        format={() => 'should never be called'}
      />,
    )

    expect(screen.queryByText('0')).not.toBeInTheDocument()
    expect(screen.queryByText('0%')).not.toBeInTheDocument()
    expect(screen.getByText('Too few calls to publish')).toBeInTheDocument()
  })

  it('does not call the formatter for a withheld figure', () => {
    const format = vi.fn()
    render(<FigureValue figure={figure({ published: false, value: null })} format={format} />)

    expect(format).not.toHaveBeenCalled()
  })

  it('withholds a figure marked published but carrying no value', () => {
    // Belt and braces: the backend should never send this, and if it ever
    // does, rendering `null` as text is worse than withholding it.
    render(<FigureValue figure={figure({ published: true, value: null })} />)

    expect(screen.queryByText('null')).not.toBeInTheDocument()
  })

  it('distinguishes the reasons, because they mean different things', () => {
    // More calls fixes one; only a schema change fixes the other.
    const { rerender } = render(
      <Withheld reason={{ code: 'BELOW_MIN_N', label: 'Too few calls to publish' }} />,
    )
    expect(screen.getByText('Too few calls to publish')).toBeInTheDocument()

    rerender(<Withheld reason={{ code: 'NO_FIELD', label: 'Not a field in the v9 schema' }} />)
    expect(screen.getByText('Not a field in the v9 schema')).toBeInTheDocument()
  })
})

describe('EpistemicChip', () => {
  it("maps a figure's basis onto the vocabulary the screens use", () => {
    expect(basisFromApi('OBSERVED')).toBe('observed')
    expect(basisFromApi('DERIVED')).toBe('derived')
    expect(basisFromApi('REFERENCE')).toBe('reference')
  })

  it('says nothing when the figure names no origin', () => {
    // D13: `basis` is null on a withheld figure the v9 schema has no field
    // for. There is nothing to name, so the chip is absent rather than
    // guessed. Suppression itself is rendered by `Withheld`, which carries
    // the reason — two places claiming it and neither holding the reason
    // is how a reader ends up unable to tell why a figure is missing.
    expect(basisFromApi(null)).toBeNull()
    expect(basisFromApi(undefined)).toBeNull()
  })

  it('drops an unknown code rather than rendering it', () => {
    // A code this build does not know is deployment skew, not a fact about
    // the number. WITHHELD is the concrete case: it was a class before D13
    // and is not one now.
    expect(basisFromApi('WITHHELD')).toBeNull()
    expect(basisFromApi('MEASURED')).toBeNull()
  })

  it('explains itself rather than relying on the word alone', () => {
    render(<EpistemicChip kind="inference" />)

    expect(screen.getByText('inference')).toHaveAttribute(
      'title',
      expect.stringContaining('beyond the data'),
    )
  })
})

describe('RiskPill', () => {
  it('never calls an unassessable account clean', () => {
    // "Not flagged" and "we could not look" are different claims, and at
    // batch-1 volume most of the book is the second.
    render(<RiskPill eligible={false} flagged={false} />)

    expect(screen.getByText('Not enough calls to assess')).toBeInTheDocument()
    expect(screen.queryByText('Not flagged')).not.toBeInTheDocument()
  })

  it('separates the states by shape class, not only colour', () => {
    const { rerender, container } = render(<RiskPill eligible flagged />)
    const flagged = container.querySelector('.nv-pill')?.className

    rerender(<RiskPill eligible flagged={false} />)
    const notFlagged = container.querySelector('.nv-pill')?.className

    expect(flagged).not.toBe(notFlagged)
  })
})

describe('Delta', () => {
  it('colours by meaning, not by direction', () => {
    // Unresolved calls rising is bad; resolved calls rising is good.
    const { container, rerender } = render(<Delta now={12} prior={10} badWhenUp />)
    expect(container.querySelector('.nv-up')).toBeInTheDocument()

    rerender(<Delta now={12} prior={10} badWhenUp={false} />)
    expect(container.querySelector('.nv-down')).toBeInTheDocument()
  })

  it('refuses to invent a percentage change from zero', () => {
    render(<Delta now={5} prior={0} />)

    expect(screen.getByText('new')).toBeInTheDocument()
    expect(screen.queryByText(/%/)).not.toBeInTheDocument()
  })
})

describe('DataTable', () => {
  const columns: Column[] = [
    { key: 'a', header: 'Account' },
    { key: 'b', header: 'Calls', numeric: true },
  ]
  const rows: Row[] = [{ key: '1', cells: ['Acme', 4] }]

  it('renders headers and cells', () => {
    render(
      <MemoryRouter>
        <DataTable columns={columns} rows={rows} />
      </MemoryRouter>,
    )

    expect(screen.getByRole('columnheader', { name: 'Account' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'Acme' })).toBeInTheDocument()
  })

  it('refuses a seventh column rather than letting the rule erode', () => {
    const tooMany: Column[] = Array.from({ length: MAX_COLUMNS + 1 }, (_, i) => ({
      key: String(i),
      header: `c${String(i)}`,
    }))
    // React logs the thrown error; the assertion is that it throws at all.
    const quiet = vi.spyOn(console, 'error').mockImplementation(() => {})

    expect(() =>
      render(
        <MemoryRouter>
          <DataTable columns={tooMany} rows={[]} />
        </MemoryRouter>,
      ),
    ).toThrow(/at most 6 columns/)

    quiet.mockRestore()
  })

  it('shows the empty state rather than a bare header row', () => {
    render(
      <MemoryRouter>
        <DataTable columns={columns} rows={[]} empty={<Empty />} />
      </MemoryRouter>,
    )

    expect(screen.getByText('Nothing in scope')).toBeInTheDocument()
  })

  it('navigates a row by keyboard, not only by click', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route
            path="/"
            element={
              <DataTable columns={columns} rows={[{ key: '1', cells: ['Acme', 4], href: '/there' }]} />
            }
          />
          <Route path="/there" element={<p>arrived</p>} />
        </Routes>
      </MemoryRouter>,
    )

    await user.tab()
    await user.keyboard('{Enter}')

    expect(screen.getByText('arrived')).toBeInTheDocument()
  })
})

describe('Tooltip', () => {
  it('is reachable and readable by keyboard', async () => {
    // An explanation only a mouse can reach is an explanation half the
    // readers never get.
    const user = userEvent.setup()
    render(<Tooltip>Escalations handled ÷ escalations warranted.</Tooltip>)

    await user.tab()

    expect(screen.getByRole('tooltip')).toBeVisible()
  })

  it('stays hidden until asked for', () => {
    render(<Tooltip>Explanation</Tooltip>)

    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })
})

describe('KpiTile', () => {
  it('marks a withheld headline as deliberate rather than broken', () => {
    const { container } = render(
      <KpiTile label="Contact rate" value={<Withheld />} tone="withheld" />,
    )

    expect(container.querySelector('.nv-big.nv-withheld')).toBeInTheDocument()
  })
})

describe('Quote', () => {
  it('requires attribution', () => {
    render(<Quote source="C-0042">I might look elsewhere at renewal.</Quote>)

    expect(screen.getByText('C-0042')).toBeInTheDocument()
  })
})

describe('Named', () => {
  it('puts the name in front and the reference in brackets', () => {
    render(<Named name="Jerome Arellano" reference="CB-7700205" />)

    expect(screen.getByText(/Jerome Arellano/)).toBeInTheDocument()
    expect(screen.getByText('(CB-7700205)')).toBeInTheDocument()
  })

  it('keeps the reference when the sheets do not know the person', () => {
    // Not a blank and not "Unknown": a name-shaped placeholder would say we
    // could not identify the caller, where the truth is that reference data
    // does not carry them. The reference still identifies the call.
    render(<Named name={null} reference="CB-9999999" />)

    expect(screen.getByText('CB-9999999')).toBeInTheDocument()
  })

  it('never drops the reference in favour of the name', () => {
    // The reference is what a ticket quotes and a filter takes, and two
    // members can share a name.
    const { container } = render(<Named name="Jerome Arellano" reference="CB-7700205" />)

    expect(container.textContent).toContain('CB-7700205')
  })

  it('says so when there is neither', () => {
    render(<Named name={null} reference={null} fallback="Not resolved" />)

    expect(screen.getByText('Not resolved')).toBeInTheDocument()
  })
})
