import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import * as authApi from '../api/auth'
import { ApiError, setCsrfToken } from '../api/client'
import type { User } from '../api/auth'

type AuthState = {
  user: User | null
  loading: boolean
  initialized: boolean | null
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  bootstrap: (username: string, password: string) => Promise<void>
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [initialized, setInitialized] = useState<boolean | null>(null)

  const refresh = useCallback(async () => {
    try {
      const boot = await authApi.getBootstrap()
      setInitialized(boot.initialized)
      if (!boot.initialized) {
        setUser(null)
        setCsrfToken(null)
        return
      }
      try {
        const me = await authApi.me()
        setUser(me)
      } catch (err) {
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          setUser(null)
          setCsrfToken(null)
        } else {
          setUser(null)
        }
      }
    } catch {
      setInitialized(null)
      setUser(null)
    }
  }, [])

  useEffect(() => {
    void (async () => {
      setLoading(true)
      await refresh()
      setLoading(false)
    })()
  }, [refresh])

  const login = useCallback(async (username: string, password: string) => {
    const data = await authApi.login(username, password)
    setUser(data.user)
    setInitialized(true)
  }, [])

  const logout = useCallback(async () => {
    await authApi.logout()
    setUser(null)
  }, [])

  const bootstrap = useCallback(async (username: string, password: string) => {
    const data = await authApi.bootstrapInit(username, password)
    setUser(data.user)
    setInitialized(true)
  }, [])

  const value = useMemo(
    () => ({ user, loading, initialized, login, logout, bootstrap, refresh }),
    [user, loading, initialized, login, logout, bootstrap, refresh],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return ctx
}
