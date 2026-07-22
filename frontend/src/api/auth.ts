import { apiData, apiRequest, setCsrfToken } from './client'

export type User = {
  id: string
  username: string
  role: 'admin' | 'user'
  isActive: boolean
}

export type AuthPayload = {
  user: User
  csrfToken: string
}

export type BootstrapStatus = {
  initialized: boolean
  registrationClosed: boolean
}

export async function getBootstrap(): Promise<BootstrapStatus> {
  return apiData<BootstrapStatus>('/bootstrap')
}

export async function bootstrapInit(
  username: string,
  password: string,
): Promise<AuthPayload> {
  const data = await apiData<AuthPayload>('/bootstrap/init', {
    method: 'POST',
    body: { username, password },
  })
  setCsrfToken(data.csrfToken)
  return data
}

export async function login(username: string, password: string): Promise<AuthPayload> {
  const data = await apiData<AuthPayload>('/auth/login', {
    method: 'POST',
    body: { username, password },
  })
  setCsrfToken(data.csrfToken)
  return data
}

export async function logout(): Promise<void> {
  try {
    await apiRequest('/auth/logout', { method: 'POST' })
  } finally {
    setCsrfToken(null)
  }
}

export async function me(): Promise<User> {
  const data = await apiData<User & { csrfToken?: string }>('/auth/me')
  if (data.csrfToken) {
    setCsrfToken(data.csrfToken)
  }
  const { csrfToken: _c, ...user } = data
  return user as User
}

export async function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<void> {
  await apiData('/auth/password', {
    method: 'PUT',
    body: { currentPassword, newPassword },
  })
}
