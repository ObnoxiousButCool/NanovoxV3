/**
 * The seam that makes a figure actionable.
 *
 * These test the two things a typo would otherwise hide: that the scope
 * reaches the URL, and that an unset field is absent rather than empty.
 */

import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { IssueCue, IssueValue } from '@/shared/actions/IssueLink'
import { ISSUE_KEYS, issueHref } from '@/shared/actions/issueHref'

describe('issueHref', () => {
  it('routes to the focused action view', () => {
    expect(issueHref('flagged')).toBe('/actions?focus=flagged')
  })

  it('carries the scope the figure was about', () => {
    const href = issueHref('unresolved', { employer: 'EMP-1001' })

    expect(href).toContain('focus=unresolved')
    expect(href).toContain('employer=EMP-1001')
  })

  it('leaves an unset field out rather than sending it empty', () => {
    // `?employer=` reads as a filter matching nothing, which would make
    // the action view render an empty list for a real issue.
    expect(issueHref('overdue', { employer: undefined, broker: '' })).toBe(
      '/actions?focus=overdue',
    )
  })

  it('escapes a value rather than trusting it', () => {
    expect(issueHref('flagged', { employer: 'A&B Co' })).toContain('employer=A%26B+Co')
  })

  it('offers no key the prototype has no playbook for', () => {
    // `high` is a risk band and D12 removed bands; `brush_off` and
    // `circular` key off `archetype`, which C8a leaves without a source.
    // Shipping them would put a definition on screen nobody agreed.
    const keys: readonly string[] = ISSUE_KEYS
    expect(keys).not.toContain('high')
    expect(keys).not.toContain('brush_off')
    expect(keys).not.toContain('circular')
  })
})

describe('IssueValue', () => {
  it('makes the figure itself the link, with an accessible name', () => {
    render(
      <MemoryRouter>
        <IssueValue issue="escalation_missed" scope={{ employer: 'EMP-1001' }}>
          3 calls
        </IssueValue>
      </MemoryRouter>,
    )

    const link = screen.getByRole('link', { name: '3 calls' })
    expect(link).toHaveAttribute('href', expect.stringContaining('focus=escalation_missed'))
  })

  it('never relies on colour alone', () => {
    // A reader who cannot tell hot from warm loses the emphasis and
    // nothing else: both carry the same text and the same role.
    render(
      <MemoryRouter>
        <IssueValue issue="unresolved" tone="warm">
          7 calls
        </IssueValue>
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: '7 calls' })).toBeInTheDocument()
  })
})

describe('IssueCue', () => {
  it('reads as an instruction rather than a label', () => {
    render(
      <MemoryRouter>
        <IssueCue issue="flagged" />
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: /what to do/i })).toBeInTheDocument()
  })
})
