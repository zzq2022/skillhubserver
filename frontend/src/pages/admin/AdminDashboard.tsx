import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import * as adminApi from '../../api/admin'
import type { InstanceStats, ClientInstance } from '../../api/admin'
import { ApiError } from '../../api/client'

export function AdminDashboard() {
  const { t } = useTranslation()
  const [stats, setStats] = useState<InstanceStats | null>(null)
  const [clients, setClients] = useState<ClientInstance[]>([])
  const [loading, setLoading] = useState(true)
  const [probing, setProbing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [probeMsg, setProbeMsg] = useState<string | null>(null)

  const loadData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [s, c] = await Promise.all([
        adminApi.getStats(),
        adminApi.listClients({ limit: 50 }),
      ])
      setStats(s)
      setClients(c.items || [])
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('errors.generic'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, [])

  const handleProbe = async () => {
    setProbing(true)
    setProbeMsg(null)
    setError(null)
    try {
      const res = await adminApi.probeClients()
      setProbeMsg(
        `探活完成：探测 ${res.probedCount} 台客户端，在线 ${res.onlineCount} 台，拉取同步 ${res.syncedSessionsCount} 条会话`
      )
      await loadData()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '探活探测失败')
    } finally {
      setProbing(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-100">{t('admin.nav.dashboard')}</h1>
          <p className="text-xs text-[var(--text-muted)] mt-1">
            监控系统整体运行概况、在线客户端与会话审计状态
          </p>
        </div>
        <button
          onClick={handleProbe}
          disabled={probing}
          className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-2 shadow-sm transition disabled:opacity-50"
        >
          {probing ? (
            <>
              <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              正在探测客户端...
            </>
          ) : (
            <>
              <span>🔄</span>
              主动探活客户端并同步会话
            </>
          )}
        </button>
      </div>

      {error && (
        <p className="text-sm text-rose-400 bg-rose-500/10 border border-rose-500/30 rounded-xl px-4 py-3">
          {error}
        </p>
      )}

      {probeMsg && (
        <p className="text-sm text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 rounded-xl px-4 py-3">
          {probeMsg}
        </p>
      )}

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <Link
            to="/admin/users"
            className="rounded-2xl border border-[var(--border)] bg-[var(--bg-card)] p-4 hover:border-indigo-500/40 transition"
          >
            <div className="text-xs text-[var(--text-muted)]">注册用户</div>
            <div className="text-2xl font-bold mt-1 text-slate-50">{stats.users}</div>
          </Link>
          <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/5 p-4">
            <div className="text-xs text-emerald-400 font-medium flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              当前在线用户
            </div>
            <div className="text-2xl font-bold mt-1 text-emerald-300">
              {stats.onlineUsers ?? 0}
            </div>
          </div>
          <Link
            to="/admin/clients"
            className="rounded-2xl border border-[var(--border)] bg-[var(--bg-card)] p-4 hover:border-indigo-500/40 transition"
          >
            <div className="text-xs text-[var(--text-muted)]">在线客户端</div>
            <div className="text-2xl font-bold mt-1 text-indigo-400">
              {stats.onlineClients ?? 0}
              <span className="text-xs font-normal text-[var(--text-muted)] ml-1">
                / {stats.totalClients ?? 0}
              </span>
            </div>
          </Link>
          <Link
            to="/admin/sessions"
            className="rounded-2xl border border-[var(--border)] bg-[var(--bg-card)] p-4 hover:border-indigo-500/40 transition"
          >
            <div className="text-xs text-[var(--text-muted)]">会话审计记录</div>
            <div className="text-2xl font-bold mt-1 text-slate-50">
              {stats.chatSessions ?? 0}
            </div>
          </Link>
          <Link
            to="/admin/skills"
            className="rounded-2xl border border-[var(--border)] bg-[var(--bg-card)] p-4 hover:border-indigo-500/40 transition"
          >
            <div className="text-xs text-[var(--text-muted)]">技能总数</div>
            <div className="text-2xl font-bold mt-1 text-slate-50">{stats.skills}</div>
          </Link>
          <Link
            to="/admin/skills?status=pending"
            className="rounded-2xl border border-[var(--border)] bg-[var(--bg-card)] p-4 hover:border-indigo-500/40 transition"
          >
            <div className="text-xs text-[var(--text-muted)]">待审技能</div>
            <div className="text-2xl font-bold mt-1 text-amber-400">
              {stats.pendingReviews}
            </div>
          </Link>
        </div>
      )}

      {/* Online clients & users overview */}
      <div className="rounded-2xl border border-[var(--border)] bg-[var(--bg-card)] overflow-hidden">
        <div className="px-5 py-4 border-b border-[var(--border)] flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
              客户端与用户在线状态
              <span className="text-xs font-normal px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                在线: {clients.filter((c) => c.isOnline).length} 台
              </span>
            </h2>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              由管理端主动探测各接入客户端连接状态与同步进度
            </p>
          </div>
          <Link
            to="/admin/clients"
            className="text-xs text-indigo-400 hover:text-indigo-300 font-medium"
          >
            查看全部客户端 →
          </Link>
        </div>

        {clients.length === 0 ? (
          <div className="p-8 text-center text-xs text-[var(--text-muted)]">
            暂无已接入的客户端记录
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[var(--bg-elevated)] text-[var(--text-muted)] border-b border-[var(--border)]">
                <tr>
                  <th className="py-2.5 px-4 font-medium">状态</th>
                  <th className="py-2.5 px-4 font-medium">在线用户</th>
                  <th className="py-2.5 px-4 font-medium">设备 / 客户端</th>
                  <th className="py-2.5 px-4 font-medium">平台系统</th>
                  <th className="py-2.5 px-4 font-medium">会话数</th>
                  <th className="py-2.5 px-4 font-medium">最后活跃</th>
                  <th className="py-2.5 px-4 font-medium text-right">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {clients.map((c) => (
                  <tr key={c.id} className="hover:bg-slate-800/20 transition">
                    <td className="py-3 px-4">
                      {c.isOnline ? (
                        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                          在线
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-slate-500/10 text-slate-400 border border-slate-500/20">
                          离线
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 font-medium text-slate-200">
                      {c.username && c.username !== '未登录' ? (
                        <span className="text-indigo-300 font-semibold">{c.username}</span>
                      ) : (
                        <span className="text-[var(--text-muted)]">未绑定账号</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-slate-300">
                      <div>{c.machineName}</div>
                      <div className="text-[10px] text-[var(--text-muted)] font-mono">
                        {c.id.slice(0, 12)}...
                      </div>
                    </td>
                    <td className="py-3 px-4 text-[var(--text-muted)]">
                      {c.osPlatform} ({c.appVersion})
                    </td>
                    <td className="py-3 px-4 text-slate-200 font-medium">
                      <Link
                        to={`/admin/sessions?clientId=${c.id}`}
                        className="hover:text-indigo-400 underline decoration-dotted"
                      >
                        {c.sessionCount} 条
                      </Link>
                    </td>
                    <td className="py-3 px-4 text-[var(--text-muted)]">
                      {c.lastHeartbeatAt ? new Date(c.lastHeartbeatAt).toLocaleTimeString() : '-'}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Link
                        to={`/admin/sessions?clientId=${c.id}`}
                        className="px-2.5 py-1 rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] hover:bg-indigo-600 hover:text-white transition text-[11px]"
                      >
                        查看会话
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
