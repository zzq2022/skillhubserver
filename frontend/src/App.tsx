import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import type { ReactNode } from 'react'

import { AuthProvider, useAuth } from './contexts/AuthContext'
import { BootstrapPage } from './pages/BootstrapPage'
import { HubPage } from './pages/HubPage'
import { LoginPage } from './pages/LoginPage'
import {
  AdminClients,
  AdminDashboard,
  AdminLayout,
  AdminSessions,
  AdminSkills,
  AdminUsers,
} from './pages/admin'

function LoadingScreen() {
  const { t } = useTranslation()
  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--bg)] text-[var(--text-muted)]">
      {t('common.loading')}
    </div>
  )
}

function AdminRoute({ children }: { children: ReactNode }) {
  const { user, loading, initialized } = useAuth()
  const location = useLocation()

  if (loading || initialized === null) return <LoadingScreen />
  if (initialized === false) return <Navigate to="/setup" replace />
  if (!user) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  }
  if (user.role !== 'admin') {
    return <Navigate to="/" replace />
  }
  return <>{children}</>
}

function SetupRoute({ children }: { children: ReactNode }) {
  const { loading, initialized, user } = useAuth()
  if (loading || initialized === null) return <LoadingScreen />
  if (initialized) {
    return <Navigate to={user ? '/' : '/login'} replace />
  }
  return <>{children}</>
}

function Shell() {
  const { loading, initialized } = useAuth()

  if (loading || initialized === null) {
    return <LoadingScreen />
  }

  return (
    <Routes>
      <Route
        path="/setup"
        element={
          <SetupRoute>
            <BootstrapPage />
          </SetupRoute>
        }
      />
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/admin"
        element={
          <AdminRoute>
            <AdminLayout />
          </AdminRoute>
        }
      >
        <Route index element={<AdminDashboard />} />
        <Route path="clients" element={<AdminClients />} />
        <Route path="sessions" element={<AdminSessions />} />
        <Route
          path="reviews"
          element={<Navigate to="/admin/skills?status=pending" replace />}
        />
        <Route path="skills" element={<AdminSkills />} />
        <Route path="users" element={<AdminUsers />} />
      </Route>
      <Route path="/" element={<HubPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  )
}

export default App
