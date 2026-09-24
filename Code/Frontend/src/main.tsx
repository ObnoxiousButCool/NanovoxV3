import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import { App } from '@/app/App'
import { AppProviders } from '@/app/providers'
import { getConfig } from '@/shared/config/env'
import '@/shared/design/tokens.css'
import '@/shared/design/primitives/primitives.css'
import '@/shared/design/charts/charts.css'
import '@/shared/design/drawer/drawer.css'
import '@/shared/styles/global.css'

// Validate configuration before rendering: a missing VITE_ variable should
// fail here, with a message naming it, rather than as a failed request later.
document.title = `${getConfig().appName} — Call Intelligence`

const container = document.getElementById('root')
if (!container) {
  throw new Error('Root element #root is missing from index.html.')
}

createRoot(container).render(
  <StrictMode>
    <AppProviders>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </AppProviders>
  </StrictMode>,
)
