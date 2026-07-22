import { useEffect, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../api/client'
import { useAuth } from '../contexts/AuthContext'

export function LoginPage() {
  const { t } = useTranslation()
  const { login, user, initialized, loading } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from || '/'

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!loading && initialized && user) {
      navigate(from, { replace: true })
    }
  }, [loading, initialized, user, from, navigate])

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await login(username, password)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('errors.generic'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--bg)] px-4">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-md rounded-2xl border border-[var(--border)] bg-[var(--bg-card)] p-8 shadow-xl space-y-4"
      >
        <div>
          <Link
            to="/"
            className="text-sm font-bold bg-gradient-to-r from-indigo-300 to-violet-300 bg-clip-text text-transparent"
          >
            {t('app.title')}
          </Link>
          <h1 className="text-2xl font-bold text-slate-50 mt-2">{t('auth.loginTitle')}</h1>
        </div>
        <label className="block text-sm">
          <span className="text-[var(--text-muted)]">{t('auth.username')}</span>
          <input
            className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-slate-100 focus:outline-none focus:border-indigo-500/50"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
        </label>
        <label className="block text-sm">
          <span className="text-[var(--text-muted)]">{t('auth.password')}</span>
          <input
            type="password"
            className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-slate-100 focus:outline-none focus:border-indigo-500/50"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        {error && <p className="text-sm text-rose-400">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-lg bg-indigo-600 hover:bg-indigo-500 px-4 py-2.5 text-white font-medium disabled:opacity-50"
        >
          {busy ? t('common.working') : t('auth.login')}
        </button>
        <p className="text-center text-xs text-[var(--text-muted)]">
          <Link to="/" className="text-indigo-300 hover:underline">
            {t('nav.hub')}
          </Link>
        </p>
      </form>
    </div>
  )
}
