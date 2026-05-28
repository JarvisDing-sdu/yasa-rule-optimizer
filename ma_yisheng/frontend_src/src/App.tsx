import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthGuard } from './components/AuthGuard'
import { AppLayout } from './components/layout/AppLayout'
import LoginPage          from './pages/LoginPage'
import DashboardPage      from './pages/DashboardPage'
import ReportsPage        from './pages/ReportsPage'
import ReportDetailPage   from './pages/ReportDetailPage'
import ChatPage           from './pages/ChatPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<AuthGuard />}>
          <Route element={<AppLayout />}>
            <Route path="/"              element={<DashboardPage />} />
            <Route path="/reports"       element={<ReportsPage />} />
            <Route path="/report/*"      element={<ReportDetailPage />} />
            <Route path="/chat"         element={<ChatPage />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
