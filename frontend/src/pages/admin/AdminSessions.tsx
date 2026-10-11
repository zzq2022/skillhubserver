import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import * as adminApi from '../../api/admin'
import type { ChatSessionAuditItem, ChatSessionDetail } from '../../api/admin'
import { ApiError } from '../../api/client'

export function AdminSessions() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialClientId = searchParams.get('clientId') || ''

  const [sessions, setSessions] = useState<ChatSessionAuditItem[]>([])
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState('')
  const [clientIdFilter, setClientIdFilter] = useState(initialClientId)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [sessionDetail, setSessionDetail] = useState<ChatSessionDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [syncMsg, setSyncMsg] = useState<string | null>(null)

  const handleSyncPull = async () => {
    setSyncing(true)
    setError(null)
    setSyncMsg(null)
    try {
      const res = await adminApi.probeClients()
      setSyncMsg(`拉取完成：探测在线 ${res.onlineCount} 台，拉取同步 ${res.syncedSessionsCount} 条会话`)
      await fetchSessions(search, clientIdFilter)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '拉取客户端会话失败')
    } finally {
      setSyncing(false)
    }
  }

  const fetchSessions = async (q = '', clientId = '') => {
    setLoading(true)
    setError(null)
    try {
      const res = await adminApi.listChatSessions({
        q: q || undefined,
        clientId: clientId || undefined,
        limit: 100,
      })
      setSessions(res.items || [])
      setTotal(res.total || 0)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '获取会话审计列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void fetchSessions(search, clientIdFilter)
  }, [clientIdFilter])

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    void fetchSessions(search, clientIdFilter)
  }

  const handleOpenDetail = async (id: string) => {
    setActiveSessionId(id)
    setSessionDetail(null)
    setLoadingDetail(true)
    try {
      const detail = await adminApi.getChatSessionDetail(id)
      setSessionDetail(detail)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '加载会话详情失败')
    } finally {
      setLoadingDetail(false)
    }
  }

  const handleCloseDetail = () => {
    setActiveSessionId(null)
    setSessionDetail(null)
  }

  const formatTime = (isoStr: string | null) => {
    if (!isoStr) return '-'
    return new Date(isoStr).toLocaleString()
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            会话审计
            <span className="text-xs font-normal text-[var(--text-muted)] bg-[var(--bg-elevated)] px-2 py-0.5 rounded-full border border-[var(--border)]">
              共 {total} 条
            </span>
          </h1>
          <p className="text-xs text-[var(--text-muted)] mt-1">
            查看由各客户端上报的会话轨迹记录、统计指标与问答详情
          </p>
        </div>
        <div className="flex items-center gap-2">
          {clientIdFilter && (
            <button
              onClick={() => {
                setClientIdFilter('')
                searchParams.delete('clientId')
                setSearchParams(searchParams)
              }}
              className="px-3 py-1.5 rounded-lg border border-indigo-500/30 bg-indigo-500/10 text-xs text-indigo-300 hover:bg-indigo-500/20 transition"
            >
              清除设备筛选（全部会话）
            </button>
          )}
          <button
            onClick={handleSyncPull}
            disabled={syncing}
            className="px-3.5 py-1.5 rounded-lg border border-indigo-500/40 bg-indigo-600 hover:bg-indigo-500 text-xs text-white font-medium transition flex items-center gap-1.5 shadow-sm disabled:opacity-50"
          >
            {syncing ? (
              <>
                <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                正在拉取...
              </>
            ) : (
              <>
                <span>🔄</span>
                刷新并从客户端拉取会话
              </>
            )}
          </button>
        </div>
      </div>

            {syncMsg && (
        <p className="text-sm text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 rounded-xl px-4 py-3">
          {syncMsg}
        </p>
      )}

      {error && (
        <p className="text-sm text-rose-400 bg-rose-500/10 border border-rose-500/30 rounded-xl px-4 py-3">
          {error}
        </p>
      )}

      <form onSubmit={handleSearchSubmit} className="flex gap-2">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="搜索会话标题、工作区、用户账号..."
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
                <th className="py-3 px-4">会话标题</th>
                <th className="py-3 px-4">工作区</th>
                <th className="py-3 px-4">来源设备</th>
                <th className="py-3 px-4">用户</th>
                <th className="py-3 px-4">Token / 消息数</th>
                <th className="py-3 px-4">更新时间</th>
                <th className="py-3 px-4">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {loading && sessions.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-xs text-[var(--text-muted)]">加载中...</td>
                </tr>
              ) : sessions.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-xs text-[var(--text-muted)]">暂无会话同步记录</td>
                </tr>
              ) : (
                sessions.map((s) => (
                  <tr key={s.id} className="hover:bg-[var(--bg-hover)]/50 transition">
                    <td className="py-3 px-4 font-medium text-slate-100 max-w-[220px] truncate">
                      <span title={s.title}>{s.title}</span>
                    </td>
                    <td className="py-3 px-4 text-xs text-[var(--text-muted)] max-w-[160px] truncate">
                      <span title={s.workspacePath}>{s.workspaceName}</span>
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-300">
                      <div>{s.machineName}</div>
                      <div className="font-mono text-[10px] text-[var(--text-muted)]">
                        {s.instanceId.substring(0, 12)}...
                      </div>
                    </td>
                    <td className="py-3 px-4 text-xs">
                      {s.username && s.username !== '未登录' ? (
                        <span className="text-indigo-300 font-medium">{s.username}</span>
                      ) : (
                        <span className="text-slate-500">未登录</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-300">
                      <div>{s.totalTokens.toLocaleString()} tokens</div>
                      <div className="text-[10px] text-[var(--text-muted)]">{s.messageCount} 条交互</div>
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-300">
                      {formatTime(s.sessionUpdatedAt || s.updatedAt)}
                    </td>
                    <td className="py-3 px-4">
                      <button
                        type="button"
                        onClick={() => void handleOpenDetail(s.id)}
                        className="text-xs text-indigo-400 hover:text-indigo-300 font-medium transition"
                      >
                        查看内容
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {activeSessionId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="bg-[var(--bg-elevated)] border border-[var(--border)] rounded-2xl w-full max-w-3xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden">
            <div className="p-4 border-b border-[var(--border)] flex items-center justify-between gap-4 bg-[var(--bg-card)]">
              <div>
                <h3 className="text-base font-semibold text-slate-100">
                  {sessionDetail?.title || '会话详情'}
                </h3>
                <div className="text-xs text-[var(--text-muted)] mt-0.5">
                  设备：{sessionDetail?.machineName} · 用户：{sessionDetail?.username} · 工作区：{sessionDetail?.workspaceName}
                </div>
              </div>
              <button
                type="button"
                onClick={handleCloseDetail}
                className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:text-white hover:bg-[var(--bg-hover)] transition"
              >
                ✕
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {loadingDetail ? (
                <div className="py-12 text-center text-xs text-[var(--text-muted)]">
                  正在加载会话消息...
                </div>
              ) : !sessionDetail?.messages || sessionDetail.messages.length === 0 ? (
                <div className="py-12 text-center text-xs text-[var(--text-muted)]">
                  该会话暂无详细问答消息记录（仅元数据已同步）
                </div>
              ) : (
                sessionDetail.messages.map((m, idx) => {
                  const isUser = m.role === 'user'
                  return (
                    <div
                      key={idx}
                      className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}
                    >
                      <div className="text-[10px] text-[var(--text-muted)] mb-1 px-1">
                        {isUser ? '用户 Prompt' : 'Assistant 回答'}
                      </div>
                      <div
                        className={`rounded-2xl px-4 py-2.5 max-w-[85%] text-sm whitespace-pre-wrap break-words ${
                          isUser
                            ? 'bg-indigo-600/30 text-indigo-100 border border-indigo-500/40'
                            : 'bg-[var(--bg-card)] text-slate-200 border border-[var(--border)]'
                        }`}
                      >
                        {m.content}
                      </div>
                    </div>
                  )
                })
              )}
            </div>

            <div className="p-3 border-t border-[var(--border)] bg-[var(--bg-card)] text-right">
              <button
                type="button"
                onClick={handleCloseDetail}
                className="px-4 py-1.5 rounded-lg border border-[var(--border)] text-xs text-slate-300 hover:bg-[var(--bg-hover)] transition"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
