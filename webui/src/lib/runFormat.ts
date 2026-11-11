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

const SUMMARY_LABELS: Record<string, string> = {
  'Collection finished.': '采集完成。',
  'Some comments could not be semantically evaluated and were not saved.': '部分评论未能完成智能语义判断，未保存。',
  'Collection stopped with partial results; saved records were retained.': '采集中断，已保存部分结果。',
  'Upstream collector exited with an error.': '上游采集器异常退出。',
  'Collection was cancelled; already collected records were retained.': '采集已取消，已采集的记录已保留。',
  'Service restarted during collection; partial results were retained.': '服务在采集期间重启，已保留部分结果。',
  'Task is no longer available.': '任务已不可用。',
  'Another collector process is running.': '已有采集进程正在运行。',
}

const SEMANTIC_ERROR_LABELS: Record<string, string> = {
  config: '配置错误',
  redirect: '重定向被拒绝',
  response_too_large: '响应过大',
  timeout: '请求超时',
  rate_limit: '触发限流',
  http_5xx: '服务端异常',
  http_error: '请求被拒绝',
  network: '网络异常',
  invalid_json: '返回格式错误',
  incomplete: '返回结果不完整',
  model_error: '模型错误',
}

export function semanticErrorLabel(code: string | number | undefined): string {
  if (code === undefined) return ''
  return SEMANTIC_ERROR_LABELS[String(code)] ?? '模型错误'
}

export function localizeSummary(summary: string | null | undefined): string {
  if (!summary) return ''
  return SUMMARY_LABELS[summary] ?? summary
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
