import { NavLink, Outlet, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useAuth } from '../../contexts/AuthContext'

const NAV = [
  { to: '/admin', end: true, labelKey: 'admin.nav.dashboard' },
  { to: '/admin/skills', end: false, labelKey: 'admin.nav.skills' },
  { to: '/admin/users', end: false, labelKey: 'admin.nav.users' },
] as const

export function AdminLayout() {
  const { t } = useTranslation()
  const { user, logout } = useAuth()

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--text)] flex flex-col">
      <header className="border-b border-[var(--border)] bg-[var(--bg-elevated)]">
        <div className="mx-auto max-w-6xl px-4 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <Link
              to="/"
              className="text-sm font-bold bg-gradient-to-r from-indigo-300 to-violet-300 bg-clip-text text-transparent"
            >
              {t('app.title')}
            </Link>
            <span className="text-xs text-amber-300/90 font-semibold uppercase tracking-wide">
              {t('admin.title')}
            </span>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <Link
              to="/"
              className="text-[var(--text-muted)] hover:text-indigo-300 transition"
            >
              {t('nav.hub')}
            </Link>
            <span className="text-[var(--text-muted)]">{user?.username}</span>
            <button
              type="button"
              onClick={() => void logout()}
              className="px-3 py-1 rounded-lg border border-[var(--border)] text-[var(--text-muted)] hover:bg-[var(--bg-hover)] text-xs"
            >
              {t('auth.logout')}
            </button>
          </div>
        </div>
      </header>

      <div className="flex-1 mx-auto max-w-6xl w-full px-4 py-6 flex flex-col md:flex-row gap-6">
        <aside className="md:w-48 shrink-0">
          <nav className="flex md:flex-col gap-1 overflow-x-auto">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  'px-3 py-2 rounded-lg text-sm whitespace-nowrap transition ' +
                  (isActive
                    ? 'bg-indigo-500/15 text-indigo-300 border border-indigo-500/30'
                    : 'text-[var(--text-muted)] hover:bg-[var(--bg-hover)] border border-transparent')
                }
              >
                {t(item.labelKey)}
              </NavLink>
            ))}
          </nav>
        </aside>
        <main className="flex-1 min-w-0">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
