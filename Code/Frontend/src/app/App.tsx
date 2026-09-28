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
import { ActionsScreen } from '@/app/screens/ActionsScreen'
import { ExecScreen } from '@/app/screens/ExecScreen'
import { AccountsScreen } from '@/app/screens/AccountsScreen'
import { AgentsScreen } from '@/app/screens/AgentsScreen'
import { CallsScreen } from '@/app/screens/CallsScreen'
import { HierarchyScreen } from '@/app/screens/HierarchyScreen'
import { RiskScreen } from '@/app/screens/RiskScreen'
import { StatusPage } from '@/app/StatusPage'
import { Shell } from '@/shared/design/Shell'

export function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Navigate to="/exec" replace />} />
        <Route path="/exec" element={<ExecScreen />} />
        <Route path="/risk" element={<RiskScreen />} />
        {/* One screen for both: the picker belongs on the detail page,
            as `employer.html` has it, so `/accounts` is not a separate
            list that navigates away from what it is listing. */}
        <Route path="/accounts" element={<AccountsScreen />} />
        <Route path="/accounts/:employerRef" element={<AccountsScreen />} />
        <Route path="/hierarchy" element={<HierarchyScreen />} />
        <Route path="/agents" element={<AgentsScreen />} />
        <Route path="/calls" element={<CallsScreen />} />
        <Route path="/actions" element={<ActionsScreen />} />
        <Route path="/design" element={<DesignGallery />} />
        <Route path="/status" element={<StatusPage />} />
        <Route path="*" element={<Navigate to="/exec" replace />} />
      </Routes>
    </Shell>
  )
}
