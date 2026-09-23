import { useQueryClient } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { AppProviders } from '@/app/providers'

function ShowsClientIsAvailable() {
  // Throws if no QueryClientProvider is above it in the tree, so reaching
  // this line at all is the assertion that AppProviders supplies one.
  useQueryClient()
  return <p>has a query client</p>
}

describe('AppProviders', () => {
  it('makes a query client available to its children', () => {
    render(
      <AppProviders>
        <ShowsClientIsAvailable />
      </AppProviders>,
    )

    expect(screen.getByText('has a query client')).toBeInTheDocument()
  })
})
