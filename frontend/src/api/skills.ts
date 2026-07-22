import { apiData, apiDataList, apiRequest } from './client'

export type Skill = {
  id: string
  ownerId: string
  name: string
  slug: string
  description: string | null
  visibility: string
  publishStatus: string
  version: number
  tags: string[]
  author: string | null
  model: string | null
  createdAt: string
  updatedAt: string
}

export type HubSkill = {
  id: string
  name: string
  slug: string
  description: string | null
  tags: string[]
  author: string | null
  model: string | null
  version: number
  owner: string
  updatedAt: string
}

export async function listSkills(q?: string) {
  const qs = q ? `?q=${encodeURIComponent(q)}` : ''
  return apiDataList<Skill>(`/skills${qs}`)
}

export async function createSkill(input: {
  name: string
  description?: string
  tags?: string[]
  content?: string
}): Promise<Skill> {
  return apiData<Skill>('/skills', { method: 'POST', body: input })
}

export async function getSkill(id: string): Promise<Skill> {
  return apiData<Skill>(`/skills/${id}`)
}

export async function updateSkill(
  id: string,
  input: Partial<{ name: string; description: string; tags: string[] }>,
): Promise<Skill> {
  return apiData<Skill>(`/skills/${id}`, { method: 'PUT', body: input })
}

export async function deleteSkill(id: string): Promise<void> {
  await apiData(`/skills/${id}`, { method: 'DELETE' })
}

export async function getContent(id: string): Promise<string> {
  const data = await apiData<{ content: string }>(`/skills/${id}/content`)
  return data.content
}

export async function updateContent(id: string, content: string): Promise<string> {
  const data = await apiData<{ content: string }>(`/skills/${id}/content`, {
    method: 'PUT',
    body: { content },
  })
  return data.content
}

export async function submitSkill(id: string) {
  return apiData(`/skills/${id}/submit`, { method: 'POST' })
}

export async function exportSkill(id: string): Promise<Blob> {
  const res = await apiRequest<Response>(`/skills/${id}/export`, { raw: true })
  return res.blob()
}

export async function importSkill(file: File): Promise<Skill> {
  const form = new FormData()
  form.append('file', file)
  return apiData<Skill>('/skills/import', { method: 'POST', formData: form })
}

export async function listHubSkills(q?: string) {
  const qs = q ? `?q=${encodeURIComponent(q)}` : ''
  return apiDataList<HubSkill>(`/hub/skills${qs}`)
}

export async function getHubSkill(owner: string, name: string): Promise<HubSkill> {
  return apiData<HubSkill>(`/hub/skills/${encodeURIComponent(owner)}/${encodeURIComponent(name)}`)
}
