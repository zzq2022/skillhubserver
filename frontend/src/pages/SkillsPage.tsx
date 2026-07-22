import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../api/client'
import * as skillsApi from '../api/skills'
import type { Skill } from '../api/skills'

export function SkillsPage() {
  const { t } = useTranslation()
  const [skills, setSkills] = useState<Skill[]>([])
  const [q, setQ] = useState('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [selected, setSelected] = useState<Skill | null>(null)
  const [content, setContent] = useState('')

  const load = useCallback(async (query?: string) => {
    const res = await skillsApi.listSkills(query)
    setSkills(res.data)
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
      await skillsApi.createSkill({ name, description })
      setName('')
      setDescription('')
      await load(q || undefined)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('errors.generic'))
    } finally {
      setBusy(false)
    }
  }

  const openSkill = async (skill: Skill) => {
    setSelected(skill)
    try {
      const md = await skillsApi.getContent(skill.id)
      setContent(md)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('errors.generic'))
    }
  }

  const saveContent = async () => {
    if (!selected) return
    setBusy(true)
    try {
      await skillsApi.updateContent(selected.id, content)
      await load(q || undefined)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('errors.generic'))
    } finally {
      setBusy(false)
    }
  }

  const onSubmitReview = async (id: string) => {
    setBusy(true)
    try {
      await skillsApi.submitSkill(id)
      await load(q || undefined)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('errors.generic'))
    } finally {
      setBusy(false)
    }
  }

  const onExport = async (id: string, slug: string) => {
    try {
      const blob = await skillsApi.exportSkill(id)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${slug}.zip`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('errors.generic'))
    }
  }

  const onImport = async (file: File | null) => {
    if (!file) return
    setBusy(true)
    try {
      await skillsApi.importSkill(file)
      await load(q || undefined)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('errors.generic'))
    } finally {
      setBusy(false)
    }
  }

  const onDelete = async (id: string) => {
    if (!confirm(t('skills.confirmDelete'))) return
    setBusy(true)
    try {
      await skillsApi.deleteSkill(id)
      if (selected?.id === id) setSelected(null)
      await load(q || undefined)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('errors.generic'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm flex-1 min-w-[12rem]">
          <span className="text-slate-600">{t('common.search')}</span>
          <input
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void load(q || undefined)
            }}
          />
        </label>
        <button
          type="button"
          className="rounded border border-slate-300 px-3 py-2 text-sm"
          onClick={() => void load(q || undefined)}
        >
          {t('common.search')}
        </button>
        <label className="rounded border border-slate-300 px-3 py-2 text-sm cursor-pointer">
          {t('skills.import')}
          <input
            type="file"
            accept=".zip,application/zip"
            className="hidden"
            onChange={(e) => void onImport(e.target.files?.[0] ?? null)}
          />
        </label>
      </div>

      <form onSubmit={onCreate} className="rounded-lg border border-slate-200 bg-white p-4 space-y-3">
        <h2 className="font-semibold">{t('skills.create')}</h2>
        <div className="flex flex-wrap gap-3">
          <input
            className="rounded border border-slate-300 px-3 py-2 text-sm"
            placeholder={t('skills.name')}
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <input
            className="flex-1 min-w-[12rem] rounded border border-slate-300 px-3 py-2 text-sm"
            placeholder={t('skills.description')}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <button
            type="submit"
            disabled={busy}
            className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50"
          >
            {t('common.create')}
          </button>
        </div>
      </form>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="grid gap-4 lg:grid-cols-2">
        <ul className="space-y-2">
          {skills.map((s) => (
            <li
              key={s.id}
              className="rounded-lg border border-slate-200 bg-white p-4 flex flex-col gap-2"
            >
              <div className="flex items-start justify-between gap-2">
                <button
                  type="button"
                  className="text-left font-medium text-slate-900 hover:underline"
                  onClick={() => void openSkill(s)}
                >
                  {s.name}
                </button>
                <span className="text-xs rounded bg-slate-100 px-2 py-0.5 text-slate-600">
                  {s.publishStatus}
                </span>
              </div>
              <p className="text-sm text-slate-600 line-clamp-2">{s.description}</p>
              <div className="flex flex-wrap gap-2 text-xs">
                <button
                  type="button"
                  className="rounded border px-2 py-1"
                  onClick={() => void onSubmitReview(s.id)}
                  disabled={s.publishStatus === 'published' || s.publishStatus === 'pending_review'}
                >
                  {t('skills.submit')}
                </button>
                <button
                  type="button"
                  className="rounded border px-2 py-1"
                  onClick={() => void onExport(s.id, s.slug)}
                >
                  {t('skills.export')}
                </button>
                <button
                  type="button"
                  className="rounded border border-red-200 text-red-700 px-2 py-1"
                  onClick={() => void onDelete(s.id)}
                >
                  {t('common.delete')}
                </button>
              </div>
            </li>
          ))}
          {skills.length === 0 && (
            <li className="text-sm text-slate-500">{t('skills.empty')}</li>
          )}
        </ul>

        {selected && (
          <div className="rounded-lg border border-slate-200 bg-white p-4 space-y-3">
            <h3 className="font-semibold">{selected.name}</h3>
            <textarea
              className="w-full h-64 font-mono text-sm rounded border border-slate-300 p-3"
              value={content}
              onChange={(e) => setContent(e.target.value)}
            />
            <button
              type="button"
              disabled={busy}
              className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50"
              onClick={() => void saveContent()}
            >
              {t('common.save')}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
