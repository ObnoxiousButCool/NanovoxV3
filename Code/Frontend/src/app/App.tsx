/**
 * Application shell and routes.
 *
 * The seven screens the v2 prototype defines each have a route and a rail
 * entry. Their contents arrive in Phase 2; until then each renders a
 * placeholder that says so, because an empty screen would read as "no data".
 *
 * `/rules` and `/demand` are both absent from the rail, for two different
 * reasons now. **C5 closed on 2026-09-25 (D14): `/rules` ships, reachable
 * from `/agents`** — so it has a route here and no rail entry, which is the
 * decision rather than an oversight. `/demand` is still conflict C6: its
 * endpoint is built and serves insights that render nowhere else, but
 * routing to a screen nobody has agreed to show would decide that question
 * by accident.
 */

import { Navigate, Route, Routes } from 'react-router-dom'

import { DesignGallery } from '@/app/DesignGallery'
import { LoginScreen } from '@/app/LoginScreen'
import { ActionsScreen } from '@/app/screens/ActionsScreen'
import { ExecScreen } from '@/app/screens/ExecScreen'
import { AccountsScreen } from '@/app/screens/AccountsScreen'
import { AgentsScreen } from '@/app/screens/AgentsScreen'
import { CallsScreen } from '@/app/screens/CallsScreen'
import { HierarchyScreen } from '@/app/screens/HierarchyScreen'
import { RiskScreen } from '@/app/screens/RiskScreen'
import { RulesScreen } from '@/app/screens/RulesScreen'
import { StatusPage } from '@/app/StatusPage'
import { useAuth } from '@/shared/auth/authContext'
import { Shell } from '@/shared/design/Shell'

export function App() {
  // Email-OTP login (feature/email-otp-login, not on main): the whole app
  // sits behind one gate rather than each route guarding itself, since
  // nothing here is meant to be reachable signed out.
  const { isAuthenticated } = useAuth()

  if (!isAuthenticated) {
    return (
      <Routes>
        <Route path="/login" element={<LoginScreen />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    )
  }

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
        <Route path="/rules" element={<RulesScreen />} />
        <Route path="/calls" element={<CallsScreen />} />
        <Route path="/actions" element={<ActionsScreen />} />
        <Route path="/design" element={<DesignGallery />} />
        <Route path="/status" element={<StatusPage />} />
        {/* A signed-in reader landing on /login (a stale tab, a bookmark)
            goes to the app rather than seeing a form with nothing to do. */}
        <Route path="/login" element={<Navigate to="/exec" replace />} />
        <Route path="*" element={<Navigate to="/exec" replace />} />
      </Routes>
    </Shell>
  )
}
