import { useCallback, useEffect, useState } from 'react'
import { Square } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  apiErrorMessage,
  collectorApi,
  type CollectionRun,
  type CrawlerLog,
} from '@/lib/collectorApi'
import {
  elapsedLabel,
  localizeSummary,
  relativeTime,
  runPhaseLabel,
  semanticErrorLabel,
} from '@/lib/runFormat'

interface RunDetailDialogProps {
  run: CollectionRun | null
  onClose: () => void
  onChanged: () => void | Promise<void>
}

function formatDate(value: string | null) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'medium' }).format(
    new Date(value),
  )
}

function localizeLogMessage(message: string): string {
  const text = message.replace(/^.*?MediaCrawler\s+\w+\s+\([^)]*\)\s*-\s*/i, '')
  const comment = text.match(/(?:aweme comment|comment):\s*\S+?,\s*content:\s*(.*)$/i)
  if (comment) return `采集到评论：${comment[1]}`
  if (/Sleeping for\s+(\d+)\s+seconds/i.test(text)) {
    return `等待 ${text.match(/Sleeping for\s+(\d+)/i)?.[1] ?? ''} 秒后继续采集`
  }
  if (/comments have all been obtained/i.test(text)) return '该内容的评论已采集完成'
  if (/Begin search|Current keyword/i.test(text)) return '正在搜索关键词'
  if (/Begin login|login/i.test(text)) return '正在处理平台登录'
  if (/Crawler started/i.test(text)) return '采集进程已启动'
  if (/Crawler completed successfully/i.test(text)) return '采集完成'
  if (/Crawler exited with code/i.test(text)) {
    return `采集进程退出，退出码 ${text.match(/Crawler exited with code:\s*(\d+)/i)?.[1] ?? ''}`
  }
  if (/error|failed/i.test(text)) return '采集出现异常，请查看服务日志'
  if (/[\u4e00-\u9fff]/.test(text)) return `采集日志：${text}`
  return '采集进程正在运行'
}

export function RunDetailDialog({ run, onClose, onChanged }: RunDetailDialogProps) {
  const [logs, setLogs] = useState<CrawlerLog[]>([])
  const [canceling, setCanceling] = useState(false)

  const loadLogs = useCallback(async () => {
    try {
      setLogs(await collectorApi.logs(50))
    } catch {
      // Logs are diagnostic only; keep the dialog usable if the endpoint fails.
    }
  }, [])

  useEffect(() => {
    if (!run) return
    void loadLogs()
    if (run.status !== 'running' && run.status !== 'queued') return
    const timer = window.setInterval(() => {
      void loadLogs()
    }, 2000)
    return () => window.clearInterval(timer)
  }, [run, loadLogs])

  const stopRun = async () => {
    if (!run) return
    setCanceling(true)
    try {
      await collectorApi.cancelRun(run.id)
      toast.success('已请求停止当前运行')
      await onChanged()
    } catch (error) {
      toast.error(apiErrorMessage(error))
    } finally {
      setCanceling(false)
    }
  }

  const active = run?.status === 'running' || run?.status === 'queued'
  const progress = run?.progress ?? {}

  return (
    <Dialog open={run !== null} onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>运行详情</DialogTitle>
          <DialogDescription>
            {run ? `运行 ${run.id.slice(0, 8)} · 开始 ${formatDate(run.started_at)}` : ''}
          </DialogDescription>
        </DialogHeader>

        {run && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <Badge variant={progress.stalled ? 'warning' : 'default'}>
                {progress.stalled ? '无活动' : runPhaseLabel(run)}
              </Badge>
              <span className="text-cyber-text-secondary">已运行 {elapsedLabel(run)}</span>
              <span className="text-cyber-text-muted">最近活动 {relativeTime(run.last_activity_at)}</span>
            </div>

            <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              <div className="rounded-md border border-cyber-border-subtle p-3">
                <p className="text-xs text-cyber-text-muted">已暂存评论</p>
                <p className="mt-1 text-lg text-cyber-text-primary">{progress.staged_comments ?? 0}</p>
              </div>
              <div className="rounded-md border border-cyber-border-subtle p-3">
                <p className="text-xs text-cyber-text-muted">已暂存内容</p>
                <p className="mt-1 text-lg text-cyber-text-primary">{progress.staged_contents ?? 0}</p>
              </div>
              <div className="rounded-md border border-cyber-border-subtle p-3">
                <p className="text-xs text-cyber-text-muted">已读取评论</p>
                <p className="mt-1 text-lg text-cyber-text-primary">{run.counts.seen ?? 0}</p>
              </div>
              <div className="rounded-md border border-cyber-border-subtle p-3">
                <p className="text-xs text-cyber-text-muted">命中 / 过滤</p>
                <p className="mt-1 text-lg text-cyber-text-primary">
                  {run.counts.matched ?? 0} / {run.counts.filtered ?? 0}
                </p>
              </div>
            </div>

            {Number(run.counts.semantic_failed ?? 0) > 0 && (
              <p className="rounded-md border border-cyber-neon-orange/40 bg-cyber-neon-orange/10 px-3 py-2 text-xs text-cyber-neon-orange">
                智能筛选失败 {run.counts.semantic_failed} 条
                {run.counts.semantic_error_code
                  ? `（${semanticErrorLabel(run.counts.semantic_error_code)}）`
                  : ''}
              </p>
            )}

            {active && (
              <p className="rounded-md border border-cyber-neon-cyan/30 bg-cyber-neon-cyan/5 px-3 py-2 text-xs leading-5 text-cyber-text-secondary">
                暂存数量会实时增长；命中结果要等采集结束并完成智能筛选后才会写入评论列表。
              </p>
            )}

            {localizeSummary(run.safe_summary) && (
              <p className="rounded-md border border-cyber-border-subtle px-3 py-2 text-xs text-cyber-text-secondary">
                结果摘要：{localizeSummary(run.safe_summary)}
              </p>
            )}

            <div>
              <p className="mb-2 text-xs font-medium text-cyber-text-muted">最近采集日志</p>
              <div className="h-56 overflow-y-auto rounded-md border border-cyber-border-subtle bg-cyber-bg-primary p-3 font-mono text-[11px] leading-5 text-cyber-text-secondary">
                {logs.length ? (
                  logs.map((log) => (
                    <p key={log.id} className="break-words">
                      <span className="text-cyber-text-muted">{log.timestamp}</span>{' '}
                      <span className={log.level === 'error' ? 'text-red-300' : ''}>
                        {localizeLogMessage(log.message)}
                      </span>
                    </p>
                  ))
                ) : (
                  <p className="text-cyber-text-muted">还没有日志。</p>
                )}
              </div>
            </div>
          </div>
        )}

        <DialogFooter>
          {active && (
            <Button variant="destructive" onClick={() => void stopRun()} disabled={canceling}>
              <Square />{canceling ? '正在停止…' : '停止运行'}
            </Button>
          )}
          <Button variant="outline" onClick={onClose}>关闭</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
