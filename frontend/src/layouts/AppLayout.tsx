import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { useAuth } from '../contexts/AuthContext'

export type Tab = 'skills' | 'hub' | 'admin'

type Props = {
  tab: Tab
  onTab: (tab: Tab) => void
  children: ReactNode
}

export function AppLayout({ tab, onTab, children }: Props) {
  const { t } = useTranslation()
  const { user, logout } = useAuth()

  const tabs: { id: Tab; label: string; adminOnly?: boolean }[] = [
    { id: 'skills', label: t('nav.skills') },
    { id: 'hub', label: t('nav.hub') },
    { id: 'admin', label: t('nav.admin'), adminOnly: true },
  ]

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-5xl px-4 py-3 flex flex-wrap items-center gap-4 justify-between">
          <div className="flex items-center gap-4">
            <span className="font-bold text-lg">{t('app.title')}</span>
            <nav className="flex gap-1">
              {tabs
                .filter((x) => !x.adminOnly || user?.role === 'admin')
                .map((x) => (
                  <button
                    key={x.id}
                    type="button"
                    onClick={() => onTab(x.id)}
                    className={
                      'px-3 py-1.5 rounded text-sm ' +
                      (tab === x.id
                        ? 'bg-slate-900 text-white'
                        : 'text-slate-700 hover:bg-slate-100')
                    }
                  >
                    {x.label}
                  </button>
                ))}
            </nav>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="text-slate-600">{user?.username}</span>
            <button
              type="button"
              className="rounded border border-slate-300 px-2 py-1"
              onClick={() => void logout()}
            >
              {t('auth.logout')}
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">{children}</main>
    </div>
  )
}
