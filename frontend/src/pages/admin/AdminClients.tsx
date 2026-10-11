import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import * as adminApi from '../../api/admin'
import type { ClientInstance } from '../../api/admin'
import { ApiError } from '../../api/client'

export function AdminClients() {
  const [clients, setClients] = useState<ClientInstance[]>([])
  const [onlineCount, setOnlineCount] = useState(0)
  const [totalCount, setTotalCount] = useState(0)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchClients = async (query = '') => {
    setLoading(true)
    setError(null)
    try {
      const res = await adminApi.listClients({ q: query || undefined, limit: 100 })
      setClients(res.items || [])
      setOnlineCount(res.onlineCount || 0)
      setTotalCount(res.totalCount || 0)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '获取客户端监控数据失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void fetchClients()
    const timer = setInterval(() => void fetchClients(search), 30000)
    return () => clearInterval(timer)
  }, [])

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    void fetchClients(search)
  }

  const formatTime = (isoStr: string | null) => {
    if (!isoStr) return '-'
    return new Date(isoStr).toLocaleString()
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-100">客户端监控</h1>
          <p className="text-xs text-[var(--text-muted)] mt-1">
            监控所有已安装并连接本服务的客户端设备运行状态与在线心跳
          </p>
        </div>
        <button
          onClick={() => void fetchClients(search)}
          className="px-3 py-1.5 rounded-lg border border-[var(--border)] text-xs text-[var(--text-muted)] hover:bg-[var(--bg-hover)] transition"
        >
          刷新状态
        </button>
      </div>

      {error && (
        <p className="text-sm text-rose-400 bg-rose-500/10 border border-rose-500/30 rounded-xl px-4 py-3">
          {error}
        </p>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--bg-card)] p-5">
          <div className="text-xs text-[var(--text-muted)]">当前在线客户端</div>
          <div className="text-3xl font-semibold mt-1 text-emerald-400 flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-emerald-500 animate-pulse inline-block" />
            {onlineCount}
          </div>
        </div>
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--bg-card)] p-5">
          <div className="text-xs text-[var(--text-muted)]">累计安装实例</div>
          <div className="text-3xl font-semibold mt-1 text-slate-100">{totalCount}</div>
        </div>
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--bg-card)] p-5 col-span-2 sm:col-span-1">
          <div className="text-xs text-[var(--text-muted)]">离线客户端数</div>
          <div className="text-3xl font-semibold mt-1 text-slate-400">
            {Math.max(0, totalCount - onlineCount)}
          </div>
        </div>
      </div>

      <form onSubmit={handleSearchSubmit} className="flex gap-2">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="搜索设备名、实例ID、系统、绑定用户名..."
          className="flex-1 bg-[var(--bg-card)] border border-[var(--border)] rounded-xl px-4 py-2 text-sm text-[var(--text)] placeholder-[var(--text-muted)] focus:outline-none focus:border-indigo-500"
        />
        <button
          type="submit"
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-medium transition"
        >
          搜索
        </button>
      </form>

      <div className="rounded-2xl border border-[var(--border)] bg-[var(--bg-card)] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-[var(--border)] bg-[var(--bg-elevated)]/50 text-xs text-[var(--text-muted)]">
              <tr>
                <th className="py-3 px-4">状态</th>
                <th className="py-3 px-4">设备与系统</th>
                <th className="py-3 px-4">实例 ID</th>
                <th className="py-3 px-4">绑定用户</th>
                <th className="py-3 px-4">版本信息</th>
                <th className="py-3 px-4">最近心跳时间</th>
                <th className="py-3 px-4">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {loading && clients.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-xs text-[var(--text-muted)]">加载中...</td>
                </tr>
              ) : clients.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-xs text-[var(--text-muted)]">暂无客户端连接记录</td>
                </tr>
              ) : (
                clients.map((c) => (
                  <tr key={c.id} className="hover:bg-[var(--bg-hover)]/50 transition">
                    <td className="py-3 px-4">
                      {c.isOnline ? (
                        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                          在线
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-slate-500/10 text-slate-400 border border-slate-500/20">
                          <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                          离线
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 font-medium text-slate-100">
                      <div>{c.machineName}</div>
                      <div className="text-xs text-[var(--text-muted)] font-normal">{c.osPlatform}</div>
                    </td>
                    <td className="py-3 px-4 font-mono text-xs text-slate-300">
                      <span title={c.id}>{c.id.length > 18 ? `${c.id.substring(0, 18)}...` : c.id}</span>
                    </td>
                    <td className="py-3 px-4">
                      {c.username && c.username !== '未登录' ? (
                        <span className="text-indigo-300 font-medium">{c.username}</span>
                      ) : (
                        <span className="text-slate-500 text-xs">未登录</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-xs text-[var(--text-muted)]">
                      <div>插件 v{c.appVersion}</div>
                      {c.hostVersion && <div className="text-slate-400">{c.hostVersion}</div>}
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-300">
                      {formatTime(c.lastHeartbeatAt)}
                    </td>
                    <td className="py-3 px-4">
                      <Link
                        to={`/admin/sessions?clientId=${encodeURIComponent(c.id)}`}
                        className="text-xs text-indigo-400 hover:text-indigo-300 transition"
                      >
                        会话记录 ({c.sessionCount})
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
