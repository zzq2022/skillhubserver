import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import {
  downloadSkillZip,
  fetchFeaturedSkills,
  fetchMarketplaceStats,
  fetchPublicSkillDetail,
  fetchPublicSkills,
  reportSkillView,
  searchPublicSkills,
  toggleSkillStar,
  type SkillDetail,
  type SkillPublicSummary,
  type SkillSortType,
  type SkillStats,
} from '../api/marketplace'
import { SimpleMarkdown } from '../components/SimpleMarkdown'
import { useAuth } from '../contexts/AuthContext'

const CATEGORIES = [
  { key: 'all', labelKey: 'hub.cat.all' },
  { key: 'general', labelKey: 'hub.cat.general' },
  { key: 'office', labelKey: 'hub.cat.office' },
  { key: 'dev', labelKey: 'hub.cat.dev' },
  { key: 'ai', labelKey: 'hub.cat.ai' },
  { key: 'data', labelKey: 'hub.cat.data' },
  { key: 'management', labelKey: 'hub.cat.management' },
  { key: 'deploy', labelKey: 'hub.cat.deploy' },
  { key: 'design', labelKey: 'hub.cat.design' },
  { key: 'security', labelKey: 'hub.cat.security' },
  { key: 'meta', labelKey: 'hub.cat.meta' },
] as const

const SORT_TABS: Array<{ key: SkillSortType; labelKey: string }> = [
  { key: 'trending', labelKey: 'hub.sort.trending' },
  { key: 'top', labelKey: 'hub.sort.top' },
  { key: 'new', labelKey: 'hub.sort.new' },
  { key: 'most_starred', labelKey: 'hub.sort.mostStarred' },
  { key: 'featured', labelKey: 'hub.sort.featured' },
]

function formatCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

function timeAgo(iso?: string, justNow = 'just now'): string {
  if (!iso) return ''
  const ts = new Date(iso).getTime()
  if (Number.isNaN(ts)) return ''
  const diff = Math.floor((Date.now() - ts) / 1000)
  if (diff < 60) return justNow
  if (diff < 3600) return `${Math.floor(diff / 60)}m`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`
  if (diff < 2_592_000) return `${Math.floor(diff / 86400)}d`
  return `${Math.floor(diff / 2_592_000)}mo`
}

function pageNumbers(current: number, total: number): number[] {
  const windowSize = Math.min(5, total)
  const maxStart = Math.max(1, total - windowSize + 1)
  const start = Math.min(Math.max(1, current - Math.floor(windowSize / 2)), maxStart)
  return Array.from({ length: windowSize }, (_, i) => start + i)
}

export function HubPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { user, logout, loading: authLoading } = useAuth()

  const [skills, setSkills] = useState<SkillPublicSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [pageSize, setPageSize] = useState(20)
  const [activeSort, setActiveSort] = useState<SkillSortType>('trending')
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [activeSearch, setActiveSearch] = useState('')
  const [stats, setStats] = useState<SkillStats | null>(null)
  const [featured, setFeatured] = useState<SkillPublicSummary[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<SkillDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)

  const loadSkills = useCallback(
    async (nextPage: number, q: string, sort: SkillSortType, category: string) => {
      setLoading(true)
      setError(null)
      try {
        const categoryFilter = category === 'all' ? undefined : category
        const result = q.trim()
          ? await searchPublicSkills(q, nextPage, sort, categoryFilter)
          : await fetchPublicSkills(nextPage, sort, categoryFilter)
        setSkills(result.items)
        setTotal(result.total)
        setPage(result.page)
        setPageSize(result.pageSize)
      } catch (err) {
        setError(err instanceof Error ? err.message : t('errors.generic'))
        setSkills([])
        setTotal(0)
      } finally {
        setLoading(false)
      }
    },
    [t],
  )

  useEffect(() => {
    void fetchMarketplaceStats()
      .then(setStats)
      .catch(() => {})
    void fetchFeaturedSkills(6)
      .then(setFeatured)
      .catch(() => {})
  }, [])

  useEffect(() => {
    void loadSkills(1, activeSearch, activeSort, selectedCategory)
  }, [activeSearch, activeSort, selectedCategory, loadSkills])

  useEffect(() => {
    if (!selectedId) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeDetail()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [selectedId])

  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const pages = pageNumbers(page, totalPages)

  const handleSearchSubmit = (e: FormEvent) => {
    e.preventDefault()
    setActiveSearch(searchQuery)
  }

  const openDetail = async (id: string) => {
    setSelectedId(id)
    setDetail(null)
    setDetailLoading(true)
    setDetailError(null)
    setActionError(null)
    try {
      const p = fetchPublicSkillDetail(id)
      void reportSkillView(id).catch(() => {})
      setDetail(await p)
    } catch (err) {
      setDetailError(err instanceof Error ? err.message : t('errors.generic'))
    } finally {
      setDetailLoading(false)
    }
  }

  const closeDetail = () => {
    setSelectedId(null)
    setDetail(null)
    setActionError(null)
  }

  const handleStarToggle = async () => {
    if (!user || !selectedId) {
      navigate('/login')
      return
    }
    try {
      const result = await toggleSkillStar(selectedId)
      setDetail((prev) =>
        prev
          ? {
              ...prev,
              isStarred: result.starred,
              starCount: result.starred
                ? (prev.starCount ?? 0) + 1
                : Math.max(0, (prev.starCount ?? 1) - 1),
            }
          : prev,
      )
      setSkills((prev) =>
        prev.map((s) =>
          s.id === selectedId
            ? {
                ...s,
                isStarred: result.starred,
                starCount: result.starred
                  ? (s.starCount ?? 0) + 1
                  : Math.max(0, (s.starCount ?? 1) - 1),
              }
            : s,
        ),
      )
    } catch (err) {
      setActionError(err instanceof Error ? err.message : t('errors.generic'))
    }
  }

  const handleDownload = async () => {
    if (!selectedId) return
    setDownloading(true)
    try {
      const blob = await downloadSkillZip(selectedId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${detail?.slug || 'skill'}.zip`
      a.click()
      URL.revokeObjectURL(url)
      setDetail((prev) =>
        prev
          ? { ...prev, downloadCount: (prev.downloadCount ?? 0) + 1 }
          : prev,
      )
    } catch (err) {
      setActionError(err instanceof Error ? err.message : t('errors.generic'))
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <header className="sticky top-0 z-40 border-b border-[var(--border)] bg-[var(--bg)]/85 backdrop-blur-xl">
        <div className="mx-auto max-w-7xl px-4 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="text-lg font-bold tracking-tight bg-gradient-to-r from-indigo-300 to-violet-300 bg-clip-text text-transparent">
              {t('app.title')}
            </span>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            {user?.role === 'admin' && (
              <Link
                to="/admin"
                className="px-3 py-1.5 rounded-lg text-sm font-medium text-amber-300 hover:text-amber-200 hover:bg-amber-500/10 transition"
              >
                {t('nav.admin')}
              </Link>
            )}
            {authLoading ? null : user ? (
              <div className="flex items-center gap-2">
                <span className="text-sm text-[var(--text-muted)] hidden sm:inline">
                  {user.username}
                </span>
                <button
                  type="button"
                  onClick={() => void logout()}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-[var(--border)] text-[var(--text-muted)] hover:bg-[var(--bg-hover)]"
                >
                  {t('auth.logout')}
                </button>
              </div>
            ) : (
              <Link
                to="/login"
                className="px-4 py-1.5 rounded-lg text-sm font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-900/40"
              >
                {t('auth.login')}
              </Link>
            )}
          </div>
        </div>
      </header>

      <section className="relative overflow-hidden py-14 border-b border-[var(--border)]">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(99,102,241,0.18),_transparent_55%)]" />
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b22_1px,transparent_1px),linear-gradient(to_bottom,#1e293b22_1px,transparent_1px)] bg-[size:3.5rem_3.5rem]" />
        <div className="relative max-w-7xl mx-auto px-4 text-center">
          <h1 className="text-4xl md:text-5xl font-bold mb-3 bg-gradient-to-r from-slate-100 via-indigo-200 to-violet-200 bg-clip-text text-transparent">
            {t('hub.heroTitle')}
          </h1>
          <p className="text-base md:text-lg text-[var(--text-muted)] mb-8 max-w-xl mx-auto">
            {t('hub.heroSubtitle')}
          </p>

          {stats && (
            <div className="flex items-center justify-center gap-6 sm:gap-10 mb-8">
              <div className="text-center">
                <div className="text-2xl font-bold text-slate-100">
                  {formatCount(stats.totalSkills)}
                </div>
                <div className="text-xs text-[var(--text-muted)] mt-0.5">
                  {t('hub.stats.skills')}
                </div>
              </div>
              <div className="w-px h-8 bg-[var(--border)]" />
              <div className="text-center">
                <div className="text-2xl font-bold text-amber-300">
                  {formatCount(stats.totalStars)}
                </div>
                <div className="text-xs text-[var(--text-muted)] mt-0.5">
                  {t('hub.stats.stars')}
                </div>
              </div>
              <div className="w-px h-8 bg-[var(--border)]" />
              <div className="text-center">
                <div className="text-2xl font-bold text-indigo-300">
                  {formatCount(stats.totalDownloads)}
                </div>
                <div className="text-xs text-[var(--text-muted)] mt-0.5">
                  {t('hub.stats.downloads')}
                </div>
              </div>
            </div>
          )}

          <form onSubmit={handleSearchSubmit} className="max-w-2xl mx-auto relative">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={t('hub.searchPlaceholder')}
              className="w-full px-5 py-3 bg-[var(--bg-card)] border border-[var(--border)] rounded-2xl text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/30 transition shadow-inner"
            />
            <button
              type="submit"
              className="absolute right-3 top-1/2 -translate-y-1/2 px-4 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold"
            >
              {t('common.search')}
            </button>
          </form>
        </div>
      </section>

      {featured.length > 0 && (
        <section className="max-w-7xl mx-auto px-4 pt-10 pb-2">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-4">
            {t('hub.featured')}
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {featured.slice(0, 3).map((skill) => (
              <button
                type="button"
                key={skill.id}
                onClick={() => void openDetail(skill.id)}
                className="text-left bg-gradient-to-br from-[var(--bg-card)] to-[#1a2236] hover:to-indigo-950/40 border border-[var(--border)] hover:border-indigo-500/40 rounded-2xl p-5 transition group"
              >
                <h3 className="text-sm font-bold text-slate-100 truncate group-hover:text-indigo-300">
                  {skill.name}
                </h3>
                <p className="text-xs text-[var(--text-muted)] line-clamp-2 mt-1">
                  {skill.description?.slice(0, 80) || t('hub.noDescription')}
                </p>
              </button>
            ))}
          </div>
        </section>
      )}

      <section className="max-w-7xl mx-auto px-4 pt-8 pb-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-1 overflow-x-auto pb-1">
            {SORT_TABS.map((tab) => (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveSort(tab.key)}
                className={
                  'px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap transition ' +
                  (activeSort === tab.key
                    ? 'bg-indigo-500/15 border border-indigo-500/40 text-indigo-300'
                    : 'text-[var(--text-muted)] hover:bg-[var(--bg-hover)] border border-transparent')
                }
              >
                {t(tab.labelKey)}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">{t('hub.category')}</span>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="px-3 py-1.5 bg-[var(--bg-card)] border border-[var(--border)] rounded-lg text-sm text-slate-300 focus:outline-none focus:border-indigo-500/50"
            >
              {CATEGORIES.map((c) => (
                <option key={c.key} value={c.key}>
                  {t(c.labelKey)}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>

      <main className="max-w-7xl mx-auto px-4 pb-16">
        {error && (
          <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-2xl text-rose-300 text-sm mb-6">
            {error}
          </div>
        )}

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="h-44 bg-[var(--bg-card)] border border-[var(--border)] rounded-2xl animate-pulse"
              />
            ))}
          </div>
        ) : skills.length === 0 ? (
          <div className="text-center py-20 bg-[var(--bg-card)] border border-[var(--border)] rounded-2xl">
            <p className="text-[var(--text-muted)] font-medium">{t('hub.empty')}</p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
              {skills.map((skill) => (
                <button
                  type="button"
                  key={skill.id}
                  onClick={() => void openDetail(skill.id)}
                  className="text-left bg-[var(--bg-card)] hover:bg-[var(--bg-hover)] border border-[var(--border)] hover:border-indigo-500/40 rounded-2xl p-5 transition group flex flex-col justify-between min-h-[190px]"
                >
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <div className="w-10 h-10 rounded-xl bg-indigo-500/10 text-indigo-300 flex items-center justify-center text-xs font-semibold">
                        {(skill.category || 'gen').slice(0, 3).toUpperCase()}
                      </div>
                      {skill.category && skill.category !== 'all' && (
                        <span className="text-[10px] font-medium bg-indigo-500/10 text-indigo-300 px-2 py-0.5 rounded-full border border-indigo-500/20">
                          {t(`hub.cat.${skill.category}`, { defaultValue: skill.category })}
                        </span>
                      )}
                    </div>
                    <h3 className="text-base font-bold text-slate-100 truncate group-hover:text-indigo-300 mb-1">
                      {skill.registrySlug || skill.name}
                    </h3>
                    <p className="text-xs text-[var(--text-muted)] line-clamp-2 leading-relaxed">
                      {skill.description?.slice(0, 120) || t('hub.noDescription')}
                    </p>
                  </div>
                  <div className="flex items-center justify-between mt-4 pt-3 border-t border-[var(--border)]">
                    <span className="text-[11px] text-slate-500 truncate max-w-[120px]">
                      {skill.authorName || skill.authorUsername || '—'}
                    </span>
                    <div className="flex items-center gap-3 text-[11px] text-slate-500">
                      <span className={skill.isStarred ? 'text-amber-300' : ''}>
                        {skill.isStarred ? '★' : '☆'}{' '}
                        {formatCount(skill.starCount ?? 0)}
                      </span>
                      <span>↓ {formatCount(skill.downloadCount ?? 0)}</span>
                      {skill.updatedAt && (
                        <span>{timeAgo(skill.updatedAt, t('hub.justNow'))}</span>
                      )}
                    </div>
                  </div>
                </button>
              ))}
            </div>

            <div className="mt-10 flex flex-col items-center gap-3">
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() =>
                    void loadSkills(page - 1, activeSearch, activeSort, selectedCategory)
                  }
                  disabled={loading || page <= 1}
                  className="px-3 py-1.5 bg-[var(--bg-card)] border border-[var(--border)] text-slate-300 text-sm rounded-lg disabled:opacity-40"
                >
                  {t('hub.prev')}
                </button>
                {pages.map((n) => (
                  <button
                    key={n}
                    type="button"
                    onClick={() =>
                      void loadSkills(n, activeSearch, activeSort, selectedCategory)
                    }
                    disabled={loading || n === page}
                    className={
                      'min-w-9 px-3 py-1.5 border text-sm rounded-lg ' +
                      (n === page
                        ? 'bg-indigo-600 border-indigo-600 text-white'
                        : 'bg-[var(--bg-card)] border-[var(--border)] text-slate-300')
                    }
                  >
                    {n}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() =>
                    void loadSkills(page + 1, activeSearch, activeSort, selectedCategory)
                  }
                  disabled={loading || page >= totalPages}
                  className="px-3 py-1.5 bg-[var(--bg-card)] border border-[var(--border)] text-slate-300 text-sm rounded-lg disabled:opacity-40"
                >
                  {t('hub.next')}
                </button>
              </div>
              <p className="text-center text-xs text-slate-500">
                {t('hub.pageInfo', { page, totalPages, total })}
              </p>
            </div>
          </>
        )}
      </main>

      {selectedId && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-md p-4"
          onClick={(e) => {
            if (e.target === e.currentTarget) closeDetail()
          }}
        >
          <div className="bg-[var(--bg-elevated)] border border-[var(--border)] rounded-2xl max-w-2xl w-full max-h-[85vh] overflow-y-auto shadow-2xl">
            {detailLoading ? (
              <div className="p-12 text-center">
                <div className="inline-block w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                <p className="mt-3 text-sm text-[var(--text-muted)]">{t('common.loading')}</p>
              </div>
            ) : detailError ? (
              <div className="p-8 text-center">
                <p className="text-rose-400 text-sm mb-4">{detailError}</p>
                <button
                  type="button"
                  onClick={closeDetail}
                  className="px-4 py-2 bg-[var(--bg-hover)] rounded-xl text-sm border border-[var(--border)]"
                >
                  {t('common.close')}
                </button>
              </div>
            ) : detail ? (
              <>
                <div className="p-6 border-b border-[var(--border)]">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h2 className="text-xl font-bold text-slate-50">
                        {detail.registrySlug || detail.name}
                      </h2>
                      <div className="flex items-center gap-3 mt-1 text-xs text-slate-500">
                        {detail.authorName && <span>by {detail.authorName}</span>}
                        {detail.category && (
                          <span className="bg-indigo-500/10 text-indigo-300 px-2 py-0.5 rounded-full border border-indigo-500/20">
                            {t(`hub.cat.${detail.category}`, {
                              defaultValue: detail.category,
                            })}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => void handleStarToggle()}
                        className={
                          'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border transition ' +
                          (detail.isStarred
                            ? 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                            : 'bg-[var(--bg-hover)] text-slate-400 border-[var(--border)] hover:text-amber-300')
                        }
                      >
                        {detail.isStarred ? '★' : '☆'}{' '}
                        {formatCount(detail.starCount ?? 0)}
                      </button>
                      <button
                        type="button"
                        onClick={closeDetail}
                        className="w-8 h-8 flex items-center justify-center rounded-lg bg-[var(--bg-hover)] text-slate-400 hover:text-white border border-[var(--border)]"
                      >
                        ×
                      </button>
                    </div>
                  </div>
                  <div className="flex items-center gap-6 mt-4 text-xs text-slate-500">
                    <span>
                      ↓ {formatCount(detail.downloadCount ?? 0)} {t('hub.download')}
                    </span>
                    <span>
                      {formatCount(detail.viewCount ?? 0)} {t('hub.views')}
                    </span>
                  </div>
                  {actionError && (
                    <p className="mt-3 text-sm text-rose-400">{actionError}</p>
                  )}
                </div>
                <div className="p-6">
                  <div className="text-sm leading-relaxed text-slate-300 simple-md prose-invert">
                    <SimpleMarkdown
                      content={detail.skillMd || detail.description || ''}
                    />
                  </div>
                  <div className="mt-6 flex gap-3">
                    <button
                      type="button"
                      disabled={downloading}
                      onClick={() => void handleDownload()}
                      className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold disabled:opacity-50"
                    >
                      {downloading ? t('common.working') : t('hub.downloadZip')}
                    </button>
                  </div>
                </div>
              </>
            ) : null}
          </div>
        </div>
      )}

      <style>{`
        .simple-md .md-h1 { font-size: 1.25rem; font-weight: 700; margin: 0.75rem 0 0.5rem; color: #f1f5f9; }
        .simple-md .md-h2 { font-size: 1.1rem; font-weight: 600; margin: 0.75rem 0 0.4rem; color: #e2e8f0; }
        .simple-md .md-h3 { font-size: 1rem; font-weight: 600; margin: 0.6rem 0 0.3rem; color: #e2e8f0; }
        .simple-md .md-p { margin: 0.4rem 0; color: #cbd5e1; }
        .simple-md .md-ul { margin: 0.4rem 0 0.4rem 1.25rem; list-style: disc; color: #cbd5e1; }
        .simple-md .md-pre { background: #0f172a; border: 1px solid #243049; border-radius: 0.75rem; padding: 0.75rem 1rem; overflow-x: auto; margin: 0.75rem 0; font-size: 0.8rem; }
        .simple-md .md-code { background: #1e293b; padding: 0.1rem 0.35rem; border-radius: 0.25rem; font-size: 0.85em; }
        .simple-md .md-link { color: #818cf8; text-decoration: underline; }
      `}</style>
    </div>
  )
}
