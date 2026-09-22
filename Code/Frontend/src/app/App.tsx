/**
 * Application shell and routes.
 *
 * Nothing beyond a status page exists yet — the seven screens arrive in
 * Phase 8, on top of the design system built in Phase 7. This proves the
 * router, the query client and the typed API client are wired together
 * end to end before anything is built on top of them.
 */

import { Navigate, Route, Routes } from 'react-router-dom'

import { StatusPage } from '@/app/StatusPage'

export function App() {
  return (
    <Routes>
      <Route path="/" element={<StatusPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
