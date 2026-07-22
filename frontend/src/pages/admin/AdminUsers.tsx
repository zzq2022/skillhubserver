import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import * as adminApi from '../../api/admin'
import type { User } from '../../api/auth'
import { ApiError } from '../../api/client'
import { useAuth } from '../../contexts/AuthContext'

export function AdminUsers() {
  const { t } = useTranslation()
  const { user: me } = useAuth()
  const [users, setUsers] = useState<User[]>([])
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<'user' | 'admin'>('user')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    const u = await adminApi.listUsers()
    setUsers(u.data)
  }, [])

  useEffect(() => {
    void load().catch((err) =>
      setError(err instanceof ApiError ? err.message : t('errors.generic')),
    )
  }, [load, t])

  const onCreate = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await adminApi.createUser({ username, password, role })
      setUsername('')
      setPassword('')
      setRole('user')
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('errors.generic'))
    } finally {
      setBusy(false)
    }
  }

  const toggleActive = async (u: User) => {
    if (u.id === me?.id) return
    setBusy(true)
    setError(null)
    try {
      await adminApi.setUserStatus(u.id, !u.isActive)
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('errors.generic'))
    } finally {
      setBusy(false)
    }
  }

  const toggleRole = async (u: User) => {
    if (u.id === me?.id) return
    setBusy(true)
    setError(null)
    try {
      await adminApi.setUserRole(u.id, u.role === 'admin' ? 'user' : 'admin')
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('errors.generic'))
    } finally {
      setBusy(false)
    }
  }

  const onDelete = async (u: User) => {
    if (u.id === me?.id) return
    if (!window.confirm(t('admin.confirmDeleteUser', { name: u.username }))) return
    setBusy(true)
    setError(null)
    try {
      await adminApi.deleteUser(u.id)
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('errors.generic'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-slate-100">{t('admin.nav.users')}</h1>
      {error && (
        <p className="text-sm text-rose-400 bg-rose-500/10 border border-rose-500/30 rounded-xl px-4 py-3">
          {error}
        </p>
      )}

      <form
        onSubmit={onCreate}
        className="flex flex-wrap gap-2 items-end rounded-2xl border border-[var(--border)] bg-[var(--bg-card)] p-4"
      >
        <label className="text-sm">
          <span className="text-[var(--text-muted)] block mb-1">{t('auth.username')}</span>
          <input
            className="rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-slate-100"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </label>
        <label className="text-sm">
          <span className="text-[var(--text-muted)] block mb-1">{t('auth.password')}</span>
          <input
            type="password"
            className="rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-slate-100"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            required
          />
        </label>
        <label className="text-sm">
          <span className="text-[var(--text-muted)] block mb-1">{t('admin.role')}</span>
          <select
            className="rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-slate-100"
            value={role}
            onChange={(e) => setRole(e.target.value as 'user' | 'admin')}
          >
            <option value="user">user</option>
            <option value="admin">admin</option>
          </select>
        </label>
        <button
          type="submit"
          disabled={busy}
          className="rounded-lg bg-indigo-600 hover:bg-indigo-500 px-4 py-2 text-sm text-white font-medium disabled:opacity-50"
        >
          {t('admin.createUser')}
        </button>
      </form>

      <ul className="divide-y divide-[var(--border)] rounded-2xl border border-[var(--border)] bg-[var(--bg-card)]">
        {users.map((u) => (
          <li
            key={u.id}
            className="px-4 py-3 flex flex-wrap items-center justify-between gap-3 text-sm"
          >
            <div>
              <span className="font-medium text-slate-100">{u.username}</span>
              <span className="ml-2 text-[var(--text-muted)]">({u.role})</span>
              <span
                className={
                  'ml-2 text-xs ' +
                  (u.isActive ? 'text-emerald-400' : 'text-rose-400')
                }
              >
                {u.isActive ? t('admin.active') : t('admin.disabled')}
              </span>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={busy || u.id === me?.id}
                onClick={() => void toggleRole(u)}
                className="rounded-lg border border-[var(--border)] px-2 py-1 text-xs text-slate-300 hover:bg-[var(--bg-hover)] disabled:opacity-40"
              >
                {u.role === 'admin' ? t('admin.makeUser') : t('admin.makeAdmin')}
              </button>
              <button
                type="button"
                disabled={busy || u.id === me?.id}
                onClick={() => void toggleActive(u)}
                className="rounded-lg border border-[var(--border)] px-2 py-1 text-xs text-slate-300 hover:bg-[var(--bg-hover)] disabled:opacity-40"
              >
                {u.isActive ? t('admin.disable') : t('admin.enable')}
              </button>
              <button
                type="button"
                disabled={busy || u.id === me?.id}
                onClick={() => void onDelete(u)}
                className="rounded-lg border border-rose-500/40 px-2 py-1 text-xs text-rose-300 hover:bg-rose-500/10 disabled:opacity-40"
              >
                {t('common.delete')}
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
