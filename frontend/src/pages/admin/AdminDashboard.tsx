import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import * as adminApi from '../../api/admin'
import type { InstanceStats } from '../../api/admin'
import { ApiError } from '../../api/client'

export function AdminDashboard() {
  const { t } = useTranslation()
  const [stats, setStats] = useState<InstanceStats | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void adminApi
      .getStats()
      .then(setStats)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : t('errors.generic')),
      )
  }, [t])

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-slate-100">{t('admin.nav.dashboard')}</h1>
      {error && (
        <p className="text-sm text-rose-400 bg-rose-500/10 border border-rose-500/30 rounded-xl px-4 py-3">
          {error}
        </p>
      )}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {(
            [
              ['users', stats.users, '/admin/users'],
              ['skills', stats.skills, '/admin/skills'],
              ['publicSkills', stats.publicSkills, '/admin/skills'],
              ['pendingReviews', stats.pendingReviews, '/admin/skills?status=pending'],
            ] as const
          ).map(([key, val, to]) => (
            <Link
              key={key}
              to={to}
              className="rounded-2xl border border-[var(--border)] bg-[var(--bg-card)] p-5 hover:border-indigo-500/40 transition"
            >
              <div className="text-xs text-[var(--text-muted)]">
                {t(`admin.stats.${key}`)}
              </div>
              <div className="text-3xl font-semibold mt-1 text-slate-50">{val}</div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
