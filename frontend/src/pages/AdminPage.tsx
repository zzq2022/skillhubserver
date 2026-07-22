import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import * as adminApi from '../api/admin'
import type { InstanceStats, Review } from '../api/admin'
import type { User } from '../api/auth'
import { ApiError } from '../api/client'

export function AdminPage() {
  const { t } = useTranslation()
  const [users, setUsers] = useState<User[]>([])
  const [reviews, setReviews] = useState<Review[]>([])
  const [stats, setStats] = useState<InstanceStats | null>(null)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    const [u, r, s] = await Promise.all([
      adminApi.listUsers(),
      adminApi.listPendingReviews(),
      adminApi.getStats(),
    ])
    setUsers(u.data)
    setReviews(r.data)
    setStats(s)
  }, [])

  useEffect(() => {
    void load().catch((err) =>
      setError(err instanceof ApiError ? err.message : t('errors.generic')),
    )
  }, [load, t])

  const onCreate = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try {
      await adminApi.createUser({ username, password, role: 'user' })
      setUsername('')
      setPassword('')
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('errors.generic'))
    } finally {
      setBusy(false)
    }
  }

  const onApprove = async (id: string) => {
    setBusy(true)
    try {
      await adminApi.approveReview(id)
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('errors.generic'))
    } finally {
      setBusy(false)
    }
  }

  const onReject = async (id: string) => {
    setBusy(true)
    try {
      await adminApi.rejectReview(id, 'Rejected by admin')
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('errors.generic'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-8">
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {(
            [
              ['users', stats.users],
              ['skills', stats.skills],
              ['publicSkills', stats.publicSkills],
              ['pendingReviews', stats.pendingReviews],
            ] as const
          ).map(([key, val]) => (
            <div key={key} className="rounded-lg border bg-white p-4">
              <div className="text-xs text-slate-500">{t(`admin.stats.${key}`)}</div>
              <div className="text-2xl font-semibold">{val}</div>
            </div>
          ))}
        </div>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      <section className="space-y-3">
        <h2 className="font-semibold text-lg">{t('admin.reviews')}</h2>
        <ul className="space-y-2">
          {reviews.map((r) => (
            <li
              key={r.id}
              className="rounded-lg border bg-white p-4 flex flex-wrap items-center justify-between gap-2"
            >
              <div>
                <div className="font-medium">{r.skill?.name ?? r.skillId}</div>
                <div className="text-xs text-slate-500">{r.submittedAt}</div>
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={busy}
                  className="rounded bg-emerald-700 px-3 py-1 text-sm text-white"
                  onClick={() => void onApprove(r.id)}
                >
                  {t('admin.approve')}
                </button>
                <button
                  type="button"
                  disabled={busy}
                  className="rounded border border-red-300 text-red-700 px-3 py-1 text-sm"
                  onClick={() => void onReject(r.id)}
                >
                  {t('admin.reject')}
                </button>
              </div>
            </li>
          ))}
          {reviews.length === 0 && (
            <li className="text-sm text-slate-500">{t('admin.noReviews')}</li>
          )}
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="font-semibold text-lg">{t('admin.users')}</h2>
        <form onSubmit={onCreate} className="flex flex-wrap gap-2">
          <input
            className="rounded border px-3 py-2 text-sm"
            placeholder={t('auth.username')}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
          <input
            type="password"
            className="rounded border px-3 py-2 text-sm"
            placeholder={t('auth.password')}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            required
          />
          <button
            type="submit"
            disabled={busy}
            className="rounded bg-slate-900 px-4 py-2 text-sm text-white"
          >
            {t('admin.createUser')}
          </button>
        </form>
        <ul className="divide-y rounded-lg border bg-white">
          {users.map((u) => (
            <li key={u.id} className="px-4 py-3 flex justify-between text-sm">
              <span>
                {u.username}{' '}
                <span className="text-slate-500">({u.role})</span>
              </span>
              <span className={u.isActive ? 'text-emerald-700' : 'text-red-600'}>
                {u.isActive ? t('admin.active') : t('admin.disabled')}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
