import type { CollectionRun } from './collectorApi'

const PHASE_LABELS: Record<string, string> = {
  queued: '排队中',
  starting: '启动中',
  crawling: '采集中',
  filtering: '智能筛选中',
  ingesting: '入库中',
  finalizing: '收尾中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

export function runPhaseLabel(run: CollectionRun): string {
  if (run.status === 'succeeded' || run.status === 'partial') return '已完成'
  if (run.status === 'failed') return '失败'
  if (run.status === 'cancelled') return '已取消'
  if (run.status === 'interrupted') return '已中断'
  return PHASE_LABELS[run.phase] ?? run.status
}

export function relativeTime(value: string | null | undefined): string {
  if (!value) return '—'
  const seconds = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 1000))
  if (seconds < 10) return '刚刚'
  if (seconds < 60) return `${seconds} 秒前`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} 分钟前`
  return `${Math.floor(minutes / 60)} 小时前`
}

export function elapsedLabel(run: CollectionRun): string {
  if (!run.started_at) return '—'
  const end = run.finished_at ? new Date(run.finished_at).getTime() : Date.now()
  const seconds = Math.max(0, Math.round((end - new Date(run.started_at).getTime()) / 1000))
  const minutes = Math.floor(seconds / 60)
  return minutes > 0 ? `${minutes} 分 ${seconds % 60} 秒` : `${seconds} 秒`
}
