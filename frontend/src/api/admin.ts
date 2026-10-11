import { apiData, apiDataList } from './client'
import type { User } from './auth'

export type Review = {
  id: string
  skillId: string
  submitterId: string
  reviewerId: string | null
  status: string
  comment: string | null
  submittedAt: string
  reviewedAt: string | null
  skill?: {
    id: string
    name: string
    slug: string
    description: string | null
    publishStatus: string
    visibility: string
    ownerId: string
  } | null
}

export type InstanceStats = {
  users: number
  skills: number
  publicSkills: number
  pendingReviews: number
  onlineClients?: number
  onlineUsers?: number
  totalClients?: number
  chatSessions?: number
}

export async function listUsers() {
  return apiDataList<User>('/admin/users')
}

export async function createUser(input: {
  username: string
  password: string
  role: 'admin' | 'user'
}): Promise<User> {
  return apiData<User>('/admin/users', { method: 'POST', body: input })
}

export async function setUserRole(id: string, role: 'admin' | 'user'): Promise<User> {
  return apiData<User>(`/admin/users/${id}/role`, { method: 'PUT', body: { role } })
}

export async function setUserStatus(id: string, isActive: boolean): Promise<User> {
  return apiData<User>(`/admin/users/${id}/status`, {
    method: 'PUT',
    body: { isActive },
  })
}

export async function deleteUser(id: string): Promise<void> {
  await apiData(`/admin/users/${id}`, { method: 'DELETE' })
}

export async function getStats(): Promise<InstanceStats> {
  return apiData<InstanceStats>('/admin/stats')
}

export async function listPendingReviews() {
  return apiDataList<Review>('/admin/reviews')
}

export async function approveReview(id: string): Promise<Review> {
  return apiData<Review>(`/admin/reviews/${id}/approve`, { method: 'POST' })
}

export async function rejectReview(id: string, comment?: string): Promise<Review> {
  return apiData<Review>(`/admin/reviews/${id}/reject`, {
    method: 'POST',
    body: { comment },
  })
}

export type AdminSkill = {
  id: string
  name: string
  slug: string
  description?: string
  category?: string | null
  visibility: string
  publishStatus: string
  isPublic: boolean
  featured?: boolean
  starCount: number
  downloadCount: number
  viewCount: number
  ownerId: string
  ownerUsername?: string | null
  updatedAt?: string | null
}

export async function listAdminSkills(params?: {
  status?: string
  q?: string
  offset?: number
  limit?: number
}): Promise<{ items: AdminSkill[]; total: number }> {
  const sp = new URLSearchParams()
  if (params?.status) sp.set('status', params.status)
  if (params?.q) sp.set('q', params.q)
  if (params?.offset != null) sp.set('offset', String(params.offset))
  if (params?.limit != null) sp.set('limit', String(params.limit))
  const qs = sp.toString()
  const body = await apiDataList<AdminSkill>(`/admin/skills${qs ? `?${qs}` : ''}`)
  return { items: body.data ?? [], total: body.pagination?.total ?? 0 }
}

export async function unpublishSkill(skillId: string) {
  return apiData<AdminSkill>(`/admin/skills/${skillId}/unpublish`, { method: 'POST' })
}

export async function publishSkill(skillId: string) {
  return apiData<AdminSkill>(`/admin/skills/${skillId}/publish`, { method: 'POST' })
}

export type ClientInstance = {
  id: string
  machineName: string
  osPlatform: string
  appVersion: string
  hostVersion: string
  ipAddress: string
  userId: string | null
  username: string
  isOnline: boolean
  status: 'online' | 'offline'
  lastHeartbeatAt: string | null
  createdAt: string | null
  sessionCount: number
}

export async function listClients(params?: {
  q?: string
  offset?: number
  limit?: number
}): Promise<{ items: ClientInstance[]; onlineCount: number; totalCount: number }> {
  const sp = new URLSearchParams()
  if (params?.q) sp.set('q', params.q)
  if (params?.offset != null) sp.set('offset', String(params.offset))
  if (params?.limit != null) sp.set('limit', String(params.limit))
  const qs = sp.toString()
  return apiData<{ onlineCount: number; totalCount: number; items: ClientInstance[] }>(
    `/admin/clients${qs ? `?${qs}` : ''}`
  )
}

export type ChatSessionAuditItem = {
  id: string
  sessionKey: string
  instanceId: string
  machineName: string
  userId: string | null
  username: string
  title: string
  workspaceName: string
  workspacePath: string
  totalTokens: number
  messageCount: number
  sessionCreatedAt: string | null
  sessionUpdatedAt: string | null
  updatedAt: string | null
}

export type ChatMessage = {
  role: string
  content: string
  timestamp?: string
}

export type ChatSessionDetail = ChatSessionAuditItem & {
  messages: ChatMessage[]
}

export async function listChatSessions(params?: {
  clientId?: string
  userId?: string
  q?: string
  offset?: number
  limit?: number
}): Promise<{ items: ChatSessionAuditItem[]; total: number }> {
  const sp = new URLSearchParams()
  if (params?.clientId) sp.set('clientId', params.clientId)
  if (params?.userId) sp.set('userId', params.userId)
  if (params?.q) sp.set('q', params.q)
  if (params?.offset != null) sp.set('offset', String(params.offset))
  if (params?.limit != null) sp.set('limit', String(params.limit))
  const qs = sp.toString()
  const res = await apiDataList<ChatSessionAuditItem>(`/admin/chat-sessions${qs ? `?${qs}` : ''}`)
  return { items: res.data ?? [], total: res.pagination?.total ?? 0 }
}

export async function getChatSessionDetail(sessionId: string): Promise<ChatSessionDetail> {
  return apiData<ChatSessionDetail>(`/admin/chat-sessions/${sessionId}`)
}


export type ProbeResult = {
  probedCount: number
  onlineCount: number
  syncedSessionsCount: number
  details?: Array<{
    instanceId: string
    status: 'online' | 'offline'
    endpoint?: string
    sessionsSynced?: number
  }>
}

export async function probeClients(instanceId?: string): Promise<ProbeResult> {
  const qs = instanceId ? `?instanceId=${encodeURIComponent(instanceId)}` : ''
  return apiData<ProbeResult>(`/admin/clients/probe${qs}`, { method: 'POST' })
}
