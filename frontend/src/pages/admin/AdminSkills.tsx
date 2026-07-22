import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import * as adminApi from '../../api/admin'
import type { AdminSkill, Review } from '../../api/admin'
import { ApiError } from '../../api/client'

/** Simple top filters — detail status is shown as a badge per row. */
type StatusFilter = 'all' | 'public' | 'unpublished' | 'pending'

const FILTERS: Array<{ key: StatusFilter; labelKey: string }> = [
  { key: 'all', labelKey: 'admin.skillFilter.all' },
  { key: 'pending', labelKey: 'admin.skillFilter.pending' },
  { key: 'public', labelKey: 'admin.skillFilter.public' },
  { key: 'unpublished', labelKey: 'admin.skillFilter.unpublished' },
]

const VALID_FILTERS = new Set<string>(FILTERS.map((f) => f.key))

function parseFilter(raw: string | null): StatusFilter {
  if (raw && VALID_FILTERS.has(raw)) return raw as StatusFilter
  // Legacy deep-links from dashboard / old review page
  if (raw === 'private' || raw === 'draft' || raw === 'rejected') return 'unpublished'
  return 'all'
}

function statusBadge(skill: AdminSkill, t: (k: string) => string): string {
  if (skill.isPublic) return t('admin.skillStatus.public')
  if (skill.publishStatus === 'pending_review') return t('admin.skillStatus.pending')
  if (skill.publishStatus === 'rejected') return t('admin.skillStatus.rejected')
  if (skill.publishStatus === 'draft') return t('admin.skillStatus.draft')
  return t('admin.skillStatus.unpublished')
}

function badgeClass(skill: AdminSkill): string {
  if (skill.isPublic) return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
  if (skill.publishStatus === 'pending_review')
    return 'bg-amber-500/15 text-amber-300 border-amber-500/30'
  if (skill.publishStatus === 'rejected') return 'bg-rose-500/15 text-rose-300 border-rose-500/30'
  return 'bg-slate-500/15 text-slate-300 border-slate-500/30'
}

/**
 * Unified skill management.
 * Filters stay coarse (all / pending / on-market / off-market).
 * Per-row actions: approve+reject | unpublish | publish.
 */
export function AdminSkills() {
  const { t } = useTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const filter = parseFilter(searchParams.get('status'))

  const [skills, setSkills] = useState<AdminSkill[]>([])
  const [total, setTotal] = useState(0)
  const [reviewsBySkill, setReviewsBySkill] = useState<Record<string, Review>>({})
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

  const setFilter = (next: StatusFilter) => {
    if (next === 'all') {
      setSearchParams({}, { replace: true })
    } else {
      setSearchParams({ status: next }, { replace: true })
    }
  }

  const load = useCallback(async () => {
    const [skillResult, reviewResult] = await Promise.all([
      adminApi.listAdminSkills({
        status: filter === 'all' ? undefined : filter,
        limit: 100,
      }),
      adminApi.listPendingReviews(),
    ])
    setSkills(skillResult.items)
    setTotal(skillResult.total)
    const map: Record<string, Review> = {}
    for (const r of reviewResult.data) {
      map[r.skillId] = r
    }
    setReviewsBySkill(map)
  }, [filter])

  useEffect(() => {
    void load().catch((err) =>
      setError(err instanceof ApiError ? err.message : t('errors.generic')),
    )
  }, [load, t])

  const pendingCount = useMemo(() => Object.keys(reviewsBySkill).length, [reviewsBySkill])

  const run = async (skillId: string, action: () => Promise<unknown>) => {
    setBusyId(skillId)
    setError(null)
    try {
      await action()
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('errors.generic'))
    } finally {
      setBusyId(null)
    }
  }

  const onApprove = (skill: AdminSkill) => {
    const review = reviewsBySkill[skill.id]
    if (!review) {
      setError(t('admin.reviewMissing'))
      return
    }
    if (!window.confirm(t('admin.confirmApprove'))) return
    void run(skill.id, () => adminApi.approveReview(review.id))
  }

  const onReject = (skill: AdminSkill) => {
    const review = reviewsBySkill[skill.id]
    if (!review) {
      setError(t('admin.reviewMissing'))
      return
    }
    if (!window.confirm(t('admin.confirmReject'))) return
    void run(skill.id, () => adminApi.rejectReview(review.id, t('admin.rejectComment')))
  }

  const onUnpublish = (id: string) => {
    if (!window.confirm(t('admin.confirmUnpublish'))) return
    void run(id, () => adminApi.unpublishSkill(id))
  }

  const onPublish = (id: string) => {
    if (!window.confirm(t('admin.confirmPublish'))) return
    void run(id, () => adminApi.publishSkill(id))
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="text-xl font-bold text-slate-100">{t('admin.nav.skills')}</h1>
        <span className="text-xs text-[var(--text-muted)]">
          {t('admin.skillCount', { count: total })}
          {pendingCount > 0 && filter !== 'pending' && (
            <span className="ml-2 text-amber-300/90">
              · {t('admin.pendingHint', { count: pendingCount })}
            </span>
          )}
        </span>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            onClick={() => setFilter(f.key)}
            className={
              'px-3 py-1 rounded-lg text-xs font-medium border transition ' +
              (filter === f.key
                ? 'bg-indigo-600 border-indigo-500 text-white'
                : 'border-[var(--border)] text-[var(--text-muted)] hover:bg-[var(--bg-hover)]')
            }
          >
            {t(f.labelKey)}
            {f.key === 'pending' && pendingCount > 0 ? ` (${pendingCount})` : ''}
          </button>
        ))}
      </div>

      {error && (
        <p className="text-sm text-rose-400 bg-rose-500/10 border border-rose-500/30 rounded-xl px-4 py-3">
          {error}
        </p>
      )}

      <ul className="divide-y divide-[var(--border)] rounded-2xl border border-[var(--border)] bg-[var(--bg-card)]">
        {skills.map((s) => {
          const isPending = s.publishStatus === 'pending_review'
          const review = reviewsBySkill[s.id]
          const busy = busyId === s.id
          return (
            <li
              key={s.id}
              className="px-4 py-3 flex flex-wrap items-center justify-between gap-3"
            >
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-slate-100 truncate">{s.name}</span>
                  <span
                    className={
                      'text-[10px] px-1.5 py-0.5 rounded border font-medium ' + badgeClass(s)
                    }
                  >
                    {statusBadge(s, t)}
                  </span>
                </div>
                <div className="text-xs text-[var(--text-muted)] mt-0.5">
                  {s.ownerUsername ? `${s.ownerUsername}/` : ''}
                  {s.slug}
                  {s.category ? ` · ${s.category}` : ''}
                  {` · ★ ${s.starCount} · ↓ ${s.downloadCount}`}
                  {isPending && review?.submittedAt ? ` · ${review.submittedAt}` : ''}
                </div>
                {s.description && (
                  <div className="text-xs text-[var(--text-muted)] mt-1 line-clamp-1">
                    {s.description}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {isPending ? (
                  <>
                    <button
                      type="button"
                      disabled={busy || !review}
                      onClick={() => onApprove(s)}
                      className="rounded-lg bg-emerald-600/90 hover:bg-emerald-500 px-3 py-1.5 text-sm text-white disabled:opacity-50"
                    >
                      {t('admin.approve')}
                    </button>
                    <button
                      type="button"
                      disabled={busy || !review}
                      onClick={() => onReject(s)}
                      className="rounded-lg border border-rose-500/40 text-rose-300 hover:bg-rose-500/10 px-3 py-1.5 text-sm disabled:opacity-50"
                    >
                      {t('admin.reject')}
                    </button>
                  </>
                ) : s.isPublic ? (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => onUnpublish(s.id)}
                    className="rounded-lg border border-amber-500/40 text-amber-300 hover:bg-amber-500/10 px-3 py-1.5 text-sm disabled:opacity-50"
                  >
                    {t('admin.unpublish')}
                  </button>
                ) : (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => onPublish(s.id)}
                    className="rounded-lg border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10 px-3 py-1.5 text-sm disabled:opacity-50"
                  >
                    {t('admin.publish')}
                  </button>
                )}
              </div>
            </li>
          )
        })}
        {skills.length === 0 && (
          <li className="px-4 py-8 text-center text-sm text-[var(--text-muted)]">
            {filter === 'pending' ? t('admin.noReviews') : t('admin.noSkills')}
          </li>
        )}
      </ul>
    </div>
  )
}
