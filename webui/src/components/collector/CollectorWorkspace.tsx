import { useCallback, useEffect, useMemo, useState } from 'react'
import { Download, Edit3, ListFilter, Pause, Play, Plus, RefreshCw, Search, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  apiErrorMessage,
  collectorApi,
  type CollectionRun,
  type CollectionTask,
  type CollectedComment,
} from '@/lib/collectorApi'
import { TaskFormDialog } from './TaskFormDialog'

type WorkspaceTab = 'tasks' | 'comments'

function formatDate(value: string | null | undefined) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

function taskStateVariant(state: CollectionTask['state']) {
  if (state === 'enabled') return 'success'
  if (state === 'paused') return 'warning'
  return 'idle'
}

function runVariant(status: string) {
  if (status === 'running') return 'running'
  if (status === 'succeeded') return 'success'
  if (status === 'partial') return 'warning'
  if (status === 'failed') return 'destructive'
  return 'secondary'
}

export function CollectorWorkspace({ username, onLogout }: { username: string; onLogout: () => Promise<void> }) {
  const [tab, setTab] = useState<WorkspaceTab>('tasks')
  const [tasks, setTasks] = useState<CollectionTask[]>([])
  const [runs, setRuns] = useState<CollectionRun[]>([])
  const [comments, setComments] = useState<CollectedComment[]>([])
  const [commentTotal, setCommentTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [searchInput, setSearchInput] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const [platformFilter, setPlatformFilter] = useState('')
  const [taskFilter, setTaskFilter] = useState('')
  const [editingTask, setEditingTask] = useState<CollectionTask | null | undefined>(undefined)
  const [loading, setLoading] = useState(false)

  const refreshTasks = useCallback(async () => {
    const [nextTasks, nextRuns] = await Promise.all([collectorApi.tasks(), collectorApi.runs()])
    setTasks(nextTasks)
    setRuns(nextRuns)
  }, [])

  const refreshComments = useCallback(async () => {
    setLoading(true)
    try {
      const page = await collectorApi.comments({
        q: searchTerm || undefined,
        platform: platformFilter || undefined,
        task_id: taskFilter || undefined,
        offset,
      })
      setComments(page.items)
      setCommentTotal(page.total)
    } catch (error) {
      toast.error(apiErrorMessage(error))
    } finally {
      setLoading(false)
    }
  }, [offset, platformFilter, searchTerm, taskFilter])

  useEffect(() => {
    refreshTasks().catch((error) => toast.error(apiErrorMessage(error)))
    const timer = window.setInterval(() => refreshTasks().catch(() => undefined), 4000)
    return () => window.clearInterval(timer)
  }, [refreshTasks])

  useEffect(() => {
    if (tab === 'comments') refreshComments()
  }, [tab, refreshComments])

  const latestRunByTask = useMemo(() => {
    const latest = new Map<string, CollectionRun>()
    runs.forEach((run) => {
      if (!latest.has(run.task_id)) latest.set(run.task_id, run)
    })
    return latest
  }, [runs])

  const executeTaskAction = async (label: string, action: () => Promise<unknown>) => {
    try {
      await action()
      toast.success(label)
      await refreshTasks()
    } catch (error) {
      toast.error(apiErrorMessage(error))
    }
  }

  const searchComments = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setOffset(0)
    setSearchTerm(searchInput.trim())
  }

  const exportComments = async (format: 'csv' | 'xlsx') => {
    try {
      await collectorApi.exportComments(format, {
        q: searchTerm || undefined,
        platform: platformFilter || undefined,
        task_id: taskFilter || undefined,
      })
      toast.success(`已导出 ${format.toUpperCase()} 文件`)
    } catch (error) {
      toast.error(apiErrorMessage(error))
    }
  }

  const enabledCount = tasks.filter((task) => task.state === 'enabled').length
  const runningCount = runs.filter((run) => run.status === 'running' || run.status === 'queued').length

  return (
    <main className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-4 pb-6 lg:px-6">
      <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-4">
        <section className="flex flex-wrap items-end justify-between gap-4 py-1">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-cyber-text-primary">采集工作台</h1>
            <p className="mt-1 text-sm text-cyber-text-muted">管理采集计划、筛选公开评论，并按运行记录追踪变化。</p>
          </div>
          <div className="flex items-center gap-2 text-xs text-cyber-text-muted">
            <span>管理员</span><span className="text-cyber-text-secondary">{username}</span>
            <Button variant="outline" size="sm" onClick={() => onLogout()}>退出</Button>
          </div>
        </section>

        <section className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Card className="p-4">
            <p className="text-xs text-cyber-text-muted">全部任务</p>
            <p className="mt-2 text-2xl font-semibold text-cyber-text-primary">{tasks.length}</p>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-cyber-text-muted">计划已启用</p>
            <p className="mt-2 text-2xl font-semibold text-cyber-neon-cyan">{enabledCount}</p>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-cyber-text-muted">正在排队 / 运行</p>
            <p className="mt-2 text-2xl font-semibold text-cyber-neon-orange">{runningCount}</p>
          </Card>
        </section>

        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-cyber-border-subtle">
          <div className="flex gap-1" role="tablist" aria-label="工作台视图">
            <button role="tab" aria-selected={tab === 'tasks'} onClick={() => setTab('tasks')} className={`border-b-2 px-4 py-3 text-sm ${tab === 'tasks' ? 'border-cyber-neon-cyan text-cyber-neon-cyan' : 'border-transparent text-cyber-text-muted hover:text-cyber-text-primary'}`}>任务管理</button>
            <button role="tab" aria-selected={tab === 'comments'} onClick={() => setTab('comments')} className={`border-b-2 px-4 py-3 text-sm ${tab === 'comments' ? 'border-cyber-neon-cyan text-cyber-neon-cyan' : 'border-transparent text-cyber-text-muted hover:text-cyber-text-primary'}`}>评论结果</button>
          </div>
          {tab === 'tasks' ? (
            <div className="flex gap-2 pb-2">
              <Button variant="outline" size="sm" onClick={() => refreshTasks()}><RefreshCw />刷新</Button>
              <Button size="sm" onClick={() => setEditingTask(null)}><Plus />新建任务</Button>
            </div>
          ) : (
            <div className="flex gap-2 pb-2">
              <Button variant="outline" size="sm" onClick={() => exportComments('csv')}><Download />CSV</Button>
              <Button variant="outline" size="sm" onClick={() => exportComments('xlsx')}><Download />Excel</Button>
            </div>
          )}
        </div>

        {tab === 'tasks' ? (
          <section className="space-y-4">
            <Card className="overflow-hidden">
              <div className="overflow-x-auto">
                <table className="min-w-[980px] w-full text-left text-sm">
                  <thead className="bg-cyber-bg-tertiary text-xs uppercase tracking-wide text-cyber-text-muted">
                    <tr><th className="px-4 py-3 font-medium">任务</th><th className="px-4 py-3 font-medium">来源 / 筛选</th><th className="px-4 py-3 font-medium">计划</th><th className="px-4 py-3 font-medium">最近运行</th><th className="px-4 py-3 font-medium">状态</th><th className="px-4 py-3 font-medium">操作</th></tr>
                  </thead>
                  <tbody className="divide-y divide-cyber-border-subtle">
                    {tasks.map((task) => {
                      const latestRun = latestRunByTask.get(task.id)
                      return <tr key={task.id} className="align-top hover:bg-cyber-bg-tertiary/60">
                        <td className="px-4 py-4">
                          <p className="font-medium text-cyber-text-primary">{task.name}</p>
                          <p className="mt-1 text-xs text-cyber-text-muted">{task.platform === 'xhs' ? '小红书' : '抖音'} · {task.source_mode === 'search' ? '关键词' : '指定内容'}</p>
                          <p className="mt-2 text-xs text-cyber-text-muted">上限 {task.max_contents} 条内容 / 每条 {task.max_comments_per_content} 条评论</p>
                        </td>
                        <td className="max-w-[320px] px-4 py-4">
                          <p className="line-clamp-2 break-all text-xs text-cyber-text-secondary">{task.source_values.join('、')}</p>
                          <div className="mt-2 flex flex-wrap gap-1">{task.include_keywords.map((word) => <Badge key={`i-${word}`}>{word}</Badge>)}{task.exclude_keywords.map((word) => <Badge key={`e-${word}`} variant="destructive">排除 {word}</Badge>)}{!task.include_keywords.length && !task.exclude_keywords.length && <span className="text-xs text-cyber-text-muted">未设置关键词筛选</span>}</div>
                          {task.filter_rule && <p className="mt-2 text-xs leading-5 text-cyber-neon-cyan">AI 语义规则 v{task.filter_rule.version}：{task.filter_rule.definition.summary}</p>}
                        </td>
                        <td className="px-4 py-4 text-xs text-cyber-text-secondary">
                          <p>{task.schedule_type === 'manual' ? '仅手动' : task.schedule_type === 'interval' ? `每 ${task.schedule_value} 分钟` : `Cron ${task.schedule_value}`}</p>
                          {task.next_run_at && <p className="mt-1 text-cyber-text-muted">下次 {formatDate(task.next_run_at)}</p>}
                        </td>
                        <td className="px-4 py-4">
                          {latestRun ? <><Badge variant={runVariant(latestRun.status)}>{latestRun.status}</Badge><p className="mt-1 text-xs text-cyber-text-muted">{formatDate(latestRun.created_at)}</p><p className="mt-1 max-w-44 text-xs text-cyber-text-secondary">{latestRun.safe_summary ?? `${latestRun.counts.matched ?? 0} 条命中`}</p></> : <span className="text-xs text-cyber-text-muted">尚未运行</span>}
                        </td>
                        <td className="px-4 py-4"><Badge variant={taskStateVariant(task.state)}>{task.state === 'enabled' ? '启用' : task.state === 'paused' ? '暂停' : '停用'}</Badge></td>
                        <td className="px-4 py-4">
                          <div className="flex flex-wrap gap-1">
                            <Button variant="secondary" size="sm" title="立即运行" disabled={task.state !== 'enabled'} onClick={() => executeTaskAction('任务已加入串行队列', () => collectorApi.runTask(task.id))}><Play /></Button>
                            {task.state === 'enabled' ? <Button variant="outline" size="sm" title="暂停计划" onClick={() => executeTaskAction('已暂停计划', () => collectorApi.pauseTask(task.id))}><Pause /></Button> : task.state === 'paused' ? <Button variant="outline" size="sm" title="恢复计划" onClick={() => executeTaskAction('已恢复计划', () => collectorApi.resumeTask(task.id))}><Play /></Button> : null}
                            <Button variant="outline" size="sm" title="编辑任务" onClick={() => setEditingTask(task)}><Edit3 /></Button>
                            {task.state !== 'disabled' && <Button variant="destructive" size="sm" title="停用任务" onClick={() => executeTaskAction('任务已停用', () => collectorApi.disableTask(task.id))}><Trash2 /></Button>}
                          </div>
                        </td>
                      </tr>
                    })}
                    {!tasks.length && <tr><td colSpan={6} className="px-4 py-12 text-center text-sm text-cyber-text-muted">还没有任务。创建一个小范围任务开始使用。</td></tr>}
                  </tbody>
                </table>
              </div>
            </Card>
            <p className="text-xs leading-5 text-cyber-text-muted">定时任务按 Asia/Shanghai 时区执行。需要有效的平台登录态；遇到验证或限流时任务会停止并保留已有结果。系统不会绕过平台验证。</p>
          </section>
        ) : (
          <section className="space-y-4">
            <Card className="p-4">
              <form onSubmit={searchComments} className="grid gap-3 md:grid-cols-[minmax(220px,1fr)_160px_220px_auto]">
                <div className="relative"><Search className="absolute left-3 top-2.5 h-4 w-4 text-cyber-text-muted" /><Input className="pl-9" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="搜索评论内容" /></div>
                <select className="rounded-md border border-cyber-border-DEFAULT bg-cyber-bg-tertiary px-3 text-sm text-cyber-text-primary" value={platformFilter} onChange={(event) => setPlatformFilter(event.target.value)}><option value="">全部平台</option><option value="xhs">小红书</option><option value="dy">抖音</option></select>
                <select className="rounded-md border border-cyber-border-DEFAULT bg-cyber-bg-tertiary px-3 text-sm text-cyber-text-primary" value={taskFilter} onChange={(event) => setTaskFilter(event.target.value)}><option value="">全部任务</option>{tasks.map((task) => <option key={task.id} value={task.id}>{task.name}</option>)}</select>
                <Button type="submit"><ListFilter />筛选</Button>
              </form>
            </Card>
            <Card className="overflow-hidden">
              <div className="overflow-x-auto">
                <table className="min-w-[1200px] w-full text-left text-sm">
                  <thead className="bg-cyber-bg-tertiary text-xs text-cyber-text-muted"><tr><th className="px-4 py-3 font-medium">内容 / 评论</th><th className="px-4 py-3 font-medium">作者公开字段</th><th className="px-4 py-3 font-medium">互动</th><th className="px-4 py-3 font-medium">命中规则</th><th className="px-4 py-3 font-medium">评论时间 / 采集时间</th></tr></thead>
                  <tbody className="divide-y divide-cyber-border-subtle">
                    {comments.map((comment) => <tr key={comment.id} className="align-top hover:bg-cyber-bg-tertiary/60">
                      <td className="max-w-[520px] px-4 py-4">
                        {comment.content_url ? <a href={comment.content_url} target="_blank" rel="noreferrer" className="text-xs text-cyber-neon-cyan hover:underline">{comment.content_title || '查看原内容'}</a> : <p className="text-xs text-cyber-text-muted">{comment.content_title || '内容标题未知'}</p>}
                        <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-cyber-text-primary">{comment.body}</p>
                      </td>
                      <td className="px-4 py-4 text-xs">
                        <p className="text-cyber-text-primary">{comment.author_nickname || '未知昵称'}</p>
                        {comment.author_user_id && <p className="mt-1 break-all text-cyber-text-muted">ID: {comment.author_user_id}</p>}
                        {comment.author_profile_url && <a className="mt-1 inline-block text-cyber-neon-cyan hover:underline" href={comment.author_profile_url} target="_blank" rel="noreferrer">作者主页</a>}
                      </td>
                      <td className="whitespace-nowrap px-4 py-4 text-xs text-cyber-text-secondary">赞 {comment.latest_like_count}<br />回复 {comment.latest_reply_count}</td>
                      <td className="px-4 py-4">
                        <div className="flex max-w-56 flex-wrap gap-1">{comment.matched_keywords.length ? comment.matched_keywords.map((word) => <Badge key={word}>{word}</Badge>) : !comment.filter_rule_version && <span className="text-xs text-cyber-text-muted">默认通过</span>}</div>
                        {comment.filter_rule_version && <p className="mt-2 text-xs text-cyber-neon-cyan">AI 语义规则 v{comment.filter_rule_version}</p>}
                        {comment.filter_reason && <p className="mt-1 max-w-56 text-xs leading-5 text-cyber-text-muted">{comment.filter_reason}</p>}
                      </td>
                      <td className="whitespace-nowrap px-4 py-4 text-xs text-cyber-text-muted"><p>评论 {formatDate(comment.comment_time)}</p><p className="mt-1">采集 {formatDate(comment.last_observed_at)}</p></td>
                    </tr>)}
                    {!comments.length && <tr><td colSpan={5} className="px-4 py-12 text-center text-sm text-cyber-text-muted">{loading ? '正在读取评论…' : '当前筛选条件下没有评论记录。'}</td></tr>}
                  </tbody>
                </table>
              </div>
              <footer className="flex items-center justify-between border-t border-cyber-border-subtle px-4 py-3 text-xs text-cyber-text-muted">
                <span>共 {commentTotal} 条</span>
                <div className="flex items-center gap-2"><Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>上一页</Button><span>{Math.floor(offset / 50) + 1}</span><Button variant="outline" size="sm" disabled={offset + 50 >= commentTotal} onClick={() => setOffset(offset + 50)}>下一页</Button></div>
              </footer>
            </Card>
          </section>
        )}
      </div>
      {editingTask !== undefined && <TaskFormDialog task={editingTask} onClose={() => setEditingTask(undefined)} onSaved={refreshTasks} />}
    </main>
  )
}
