import { QueryClientProvider } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'

import { createQueryClient } from '@/app/queryClient'
import { AuthProvider } from '@/shared/auth/AuthProvider'
import { DrawerProvider } from '@/shared/design/drawer'
import { ThemeProvider } from '@/shared/design/ThemeProvider'

export function AppProviders({ children }: { children: ReactNode }) {
  const [queryClient] = useState(createQueryClient)

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider>
          <DrawerProvider>{children}</DrawerProvider>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
}
