import { HashRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthGuard } from './components/AuthGuard'
import { ConfigGate } from './components/ConfigGate'
import { AppLayout } from './components/layout/AppLayout'
import LoginPage          from './pages/LoginPage'
import DashboardPage      from './pages/DashboardPage'
import ReportsPage        from './pages/ReportsPage'
import ReportDetailPage   from './pages/ReportDetailPage'
import ChatPage           from './pages/ChatPage'
import SettingsPage       from './pages/SettingsPage'
import SetupPage          from './pages/SetupPage'
import RuleWorkshopPage   from './pages/RuleWorkshopPage'

function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/setup" element={<SetupPage />} />
        <Route element={<ConfigGate />}>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<AuthGuard />}>
            <Route element={<AppLayout />}>
              <Route path="/"              element={<DashboardPage />} />
              <Route path="/reports"       element={<ReportsPage />} />
              <Route path="/report/*"      element={<ReportDetailPage />} />
              <Route path="/chat"         element={<ChatPage />} />
              <Route path="/rule-workshop" element={<RuleWorkshopPage />} />
              <Route path="/settings"      element={<SettingsPage />} />
            </Route>
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </HashRouter>
  )
}

export default App
