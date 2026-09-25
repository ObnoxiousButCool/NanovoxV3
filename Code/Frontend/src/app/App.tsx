/**
 * Application shell and routes.
 *
 * The seven screens the v2 prototype defines each have a route and a rail
 * entry. Their contents arrive in Phase 2; until then each renders a
 * placeholder that says so, because an empty screen would read as "no data".
 *
 * `/rules` and `/demand` are deliberately absent from the rail. Both
 * endpoints are built and both serve insights that render nowhere else, but
 * the v2 prototype dropped the first and never had the second — conflicts C5
 * and C6 in the revised plan. Routing to a screen nobody has agreed to show
 * would decide that question by accident.
 */

import { Navigate, Route, Routes } from 'react-router-dom'

import { DesignGallery } from '@/app/DesignGallery'
import { ExecScreen } from '@/app/screens/ExecScreen'
import { AccountScreen } from '@/app/screens/AccountScreen'
import { HierarchyScreen } from '@/app/screens/HierarchyScreen'
import { RiskScreen } from '@/app/screens/RiskScreen'
import { ScreenPlaceholder } from '@/app/ScreenPlaceholder'
import { StatusPage } from '@/app/StatusPage'
import { Shell } from '@/shared/design/Shell'

const PHASE_2 = 'Phase 2'
const PHASE_3 = 'Phase 3'
const PHASE_4 = 'Phase 4'

export function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Navigate to="/exec" replace />} />
        <Route path="/exec" element={<ExecScreen />} />
        <Route path="/risk" element={<RiskScreen />} />
        <Route path="/accounts" element={<ScreenPlaceholder phase={PHASE_2} />} />
        <Route path="/accounts/:employerRef" element={<AccountScreen />} />
        <Route path="/hierarchy" element={<HierarchyScreen />} />
        <Route path="/agents" element={<ScreenPlaceholder phase={PHASE_2} />} />
        <Route path="/calls" element={<ScreenPlaceholder phase={PHASE_3} />} />
        <Route path="/actions" element={<ScreenPlaceholder phase={PHASE_4} />} />
        <Route path="/design" element={<DesignGallery />} />
        <Route path="/status" element={<StatusPage />} />
        <Route path="*" element={<Navigate to="/exec" replace />} />
      </Routes>
    </Shell>
  )
}
