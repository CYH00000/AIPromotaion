import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  apiErrorMessage,
  collectorApi,
  filterRulesApi,
  type CollectionTask,
  type FilterRule,
  type PlatformCapability,
  type PlatformId,
  type TaskPayload,
} from '@/lib/collectorApi'
import {
  CONTENT_SORT_OPTIONS,
  PUBLISH_WINDOW_OPTIONS,
} from '@/lib/taskFormat'

interface TaskFormDialogProps {
  task: CollectionTask | null
  onClose: () => void
  onSaved: () => Promise<void>
}

const fieldClass = 'w-full rounded-md border border-cyber-border-DEFAULT bg-cyber-bg-tertiary px-3 py-2 text-sm text-cyber-text-primary outline-none focus:border-cyber-neon-cyan'

const FALLBACK_PLATFORMS: PlatformCapability[] = [
  { platform: 'xhs', label: '小红书', source_modes: ['search', 'detail'], login_supported: true, content_filters_supported: true },
  { platform: 'dy', label: '抖音', source_modes: ['search', 'detail'], login_supported: true, content_filters_supported: true },
]

function splitLines(value: string) {
  return value.split(/[\r\n,]+/).map((part) => part.trim()).filter(Boolean)
}

export function TaskFormDialog({ task, onClose, onSaved }: TaskFormDialogProps) {
  const [name, setName] = useState(task?.name ?? '')
  const [platform, setPlatform] = useState<PlatformId>(task?.platform ?? 'xhs')
  const [platformOptions, setPlatformOptions] = useState<PlatformCapability[]>(FALLBACK_PLATFORMS)
  const [sourceMode, setSourceMode] = useState<'search' | 'detail'>(task?.source_mode ?? 'search')
  const [sources, setSources] = useState(task?.source_values.join('\n') ?? '')
  const [includeKeywords, setIncludeKeywords] = useState(task?.include_keywords.join('\n') ?? '')
  const [excludeKeywords, setExcludeKeywords] = useState(task?.exclude_keywords.join('\n') ?? '')
  const [maxContents, setMaxContents] = useState(task?.max_contents ?? 20)
  const [maxComments, setMaxComments] = useState(task?.max_comments_per_content ?? 100)
  const [contentSort, setContentSort] = useState<CollectionTask['content_sort']>(task?.content_sort ?? 'general')
  const [publishTimeDays, setPublishTimeDays] = useState<CollectionTask['publish_time_days']>(task?.publish_time_days ?? 0)
  const [scheduleType, setScheduleType] = useState<TaskPayload['schedule_type']>(task?.schedule_type ?? 'manual')
  const [scheduleValue, setScheduleValue] = useState(task?.schedule_value ?? '')
  const [semanticIntent, setSemanticIntent] = useState(task?.filter_rule?.intent ?? '')
  const [filterRule, setFilterRule] = useState<FilterRule | null>(task?.filter_rule ?? null)
  const [draftRule, setDraftRule] = useState<FilterRule | null>(null)
  const [modelConfigured, setModelConfigured] = useState(false)
  const [modelName, setModelName] = useState<string | null>(null)
  const [agentBusy, setAgentBusy] = useState(false)
  const [agentError, setAgentError] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (task) {
      setName(task.name)
      setPlatform(task.platform)
      setSourceMode(task.source_mode)
      setSources(task.source_values.join('\n'))
      setIncludeKeywords(task.include_keywords.join('\n'))
      setExcludeKeywords(task.exclude_keywords.join('\n'))
      setMaxContents(task.max_contents)
      setMaxComments(task.max_comments_per_content)
      setContentSort(task.content_sort)
      setPublishTimeDays(task.publish_time_days)
      setScheduleType(task.schedule_type)
      setScheduleValue(task.schedule_value ?? '')
      setSemanticIntent(task.filter_rule?.intent ?? '')
      setFilterRule(task.filter_rule ?? null)
    }
  }, [task])

  useEffect(() => {
    filterRulesApi.status().then((status) => {
      setModelConfigured(status.configured)
      setModelName(status.model_name)
    }).catch(() => {
      setModelConfigured(false)
      setModelName(null)
    })
    collectorApi.platformCapabilities().then(setPlatformOptions).catch(() => {
      setPlatformOptions(FALLBACK_PLATFORMS)
    })
  }, [])

  useEffect(() => {
    const modes = platformOptions.find((item) => item.platform === platform)?.source_modes
    if (modes?.length && !modes.includes(sourceMode)) setSourceMode(modes[0])
  }, [platform, platformOptions, sourceMode])

  const generateRule = async () => {
    setAgentBusy(true)
    setAgentError('')
    try {
      const nextDraft = await filterRulesApi.createDraft(
        semanticIntent.trim(),
        draftRule?.id ?? filterRule?.id ?? undefined,
      )
      setDraftRule(nextDraft)
    } catch (cause) {
      setAgentError(apiErrorMessage(cause))
    } finally {
      setAgentBusy(false)
    }
  }

  const approveRule = async () => {
    if (!draftRule) return
    setAgentBusy(true)
    setAgentError('')
    try {
      const approved = await filterRulesApi.approve(draftRule.id)
      setDraftRule(approved)
      setFilterRule(approved)
    } catch (cause) {
      setAgentError(apiErrorMessage(cause))
    } finally {
      setAgentBusy(false)
    }
  }

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (semanticIntent.trim() && (!filterRule || filterRule.intent !== semanticIntent.trim())) {
      setAgentError('先生成规则预览并点击“确认并应用此规则”，再保存任务；也可以清空描述，不启用智能语义筛选。')
      return
    }
    setBusy(true)
    setError('')
    const payload: TaskPayload = {
      name: name.trim(),
      platform,
      source_mode: sourceMode,
      source_values: splitLines(sources),
      include_keywords: splitLines(includeKeywords),
      exclude_keywords: splitLines(excludeKeywords),
      filter_rule_id: filterRule?.id ?? null,
      max_contents: maxContents,
      max_comments_per_content: maxComments,
      content_sort: sourceMode === 'search' ? contentSort : 'general',
      publish_time_days: sourceMode === 'search' ? publishTimeDays : 0,
      schedule_type: scheduleType,
      schedule_value: scheduleType === 'manual' ? null : scheduleValue.trim(),
    }
    try {
      if (task) {
        const { platform: _platform, source_mode: _sourceMode, ...editable } = payload
        await collectorApi.updateTask(task.id, editable)
      } else {
        await collectorApi.createTask(payload)
      }
      await onSaved()
      onClose()
    } catch (cause) {
      setError(apiErrorMessage(cause))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <section role="dialog" aria-modal="true" aria-labelledby="task-dialog-title" className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-cyber-border-DEFAULT bg-cyber-bg-secondary p-6 shadow-cyber-card">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h2 id="task-dialog-title" className="text-lg font-semibold text-cyber-text-primary">{task ? '编辑采集任务' : '创建采集任务'}</h2>
            <p className="mt-1 text-sm text-cyber-text-muted">任务使用本机已配置的平台登录态；输入源每行一个。</p>
          </div>
          <button className="text-sm text-cyber-text-muted hover:text-cyber-text-primary" onClick={onClose} type="button">关闭</button>
        </div>
        <form className="space-y-4" onSubmit={submit}>
          <label className="block space-y-1.5 text-sm text-cyber-text-secondary">
            任务名称
            <Input value={name} onChange={(event) => setName(event.target.value)} required maxLength={120} />
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block space-y-1.5 text-sm text-cyber-text-secondary">
              平台
              <select className={fieldClass} value={platform} onChange={(event) => setPlatform(event.target.value as PlatformId)} disabled={!!task}>
                {platformOptions.map((item) => <option key={item.platform} value={item.platform}>{item.label}</option>)}
              </select>
            </label>
            <label className="block space-y-1.5 text-sm text-cyber-text-secondary">
              采集来源
              <select className={fieldClass} value={sourceMode} onChange={(event) => setSourceMode(event.target.value as 'search' | 'detail')} disabled={!!task}>
                {platformOptions.find((item) => item.platform === platform)?.source_modes.includes('search') && <option value="search">关键词搜索</option>}
                {platformOptions.find((item) => item.platform === platform)?.source_modes.includes('detail') && <option value="detail">指定笔记 / 视频链接</option>}
              </select>
            </label>
          </div>
          <label className="block space-y-1.5 text-sm text-cyber-text-secondary">
            {sourceMode === 'search' ? '关键词' : '内容链接'}
            <textarea className={`${fieldClass} min-h-24 resize-y`} value={sources} onChange={(event) => setSources(event.target.value)} required placeholder={sourceMode === 'search' ? '每行一个关键词' : '每行一个内容链接'} />
          </label>
          {sourceMode === 'search' && platformOptions.find((item) => item.platform === platform)?.content_filters_supported ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block space-y-1.5 text-sm text-cyber-text-secondary">
                内容排序
                <select className={fieldClass} value={contentSort} onChange={(event) => setContentSort(event.target.value as CollectionTask['content_sort'])}>
                  {CONTENT_SORT_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </label>
              <label className="block space-y-1.5 text-sm text-cyber-text-secondary">
                发布时间
                <select className={fieldClass} value={publishTimeDays} onChange={(event) => setPublishTimeDays(Number(event.target.value) as CollectionTask['publish_time_days'])}>
                  {PUBLISH_WINDOW_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </label>
            </div>
          ) : sourceMode === 'detail' ? (
            <p className="text-xs leading-5 text-cyber-text-muted">指定链接模式按你提供的链接采集，排序和时间筛选不生效。</p>
          ) : null}
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block space-y-1.5 text-sm text-cyber-text-secondary">
              包含词（任意命中）
              <textarea className={`${fieldClass} min-h-20 resize-y`} value={includeKeywords} onChange={(event) => setIncludeKeywords(event.target.value)} placeholder="留空表示不限制" />
            </label>
            <label className="block space-y-1.5 text-sm text-cyber-text-secondary">
              排除词
              <textarea className={`${fieldClass} min-h-20 resize-y`} value={excludeKeywords} onChange={(event) => setExcludeKeywords(event.target.value)} placeholder="命中任一排除词即跳过" />
            </label>
          </div>
          <section className="space-y-3 rounded-lg border border-cyber-border-DEFAULT bg-cyber-bg-tertiary/60 p-4">
            <div>
              <h3 className="text-sm font-semibold text-cyber-text-primary">智能评论筛选助手</h3>
              <p className="mt-1 text-xs leading-5 text-cyber-text-muted">用自然语言描述你想筛选的评论。助手先生成规则预览；只有确认后才会应用到任务。采集时，命中关键词预筛的评论文本会发送给配置的云端模型判断，作者信息不会发送。</p>
            </div>
            <div className="flex items-center justify-between gap-3 text-xs">
              <span className={modelConfigured ? 'text-cyber-neon-green' : 'text-amber-300'}>
                {modelConfigured ? `模型已配置${modelName ? `：${modelName}` : ''}` : '模型未配置：请在服务端 .env 设置智能筛选接口地址、密钥和模型名称'}
              </span>
              {filterRule && <span className="text-cyber-text-muted">当前已批准 v{filterRule.version}</span>}
            </div>
            <textarea
              className={`${fieldClass} min-h-20 resize-y`}
              value={semanticIntent}
              onChange={(event) => { setSemanticIntent(event.target.value); setDraftRule(null); setAgentError('') }}
              maxLength={2000}
              placeholder="例如：筛选正在寻找软件开发团队、询问定制系统报价或明确表达项目外包需求的评论；排除招聘求职和课程咨询。"
            />
            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" variant="outline" onClick={generateRule} disabled={!modelConfigured || !semanticIntent.trim() || agentBusy}>
                {agentBusy ? '处理中…' : '生成规则预览'}
              </Button>
              {filterRule && <Button type="button" variant="ghost" onClick={() => { setFilterRule(null); setDraftRule(null); setSemanticIntent('') }}>移除当前规则</Button>}
            </div>
            {(draftRule || filterRule) && (() => {
              const previewRule = draftRule ?? filterRule!
              const isApplied = filterRule?.id === previewRule.id
              return <div className="space-y-2 rounded-md border border-cyber-border-subtle bg-cyber-bg-secondary p-3 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-medium text-cyber-text-primary">规则预览 · v{previewRule.version}</p>
                  <span className={isApplied ? 'text-cyber-neon-green' : 'text-amber-300'}>{isApplied ? '已确认并应用' : '草稿 · 尚未生效'}</span>
                </div>
                <p className="text-cyber-text-secondary">{previewRule.definition.summary}</p>
                {!!previewRule.definition.required_signals.length && <div>
                  <p className="text-xs text-cyber-text-muted">必须同时满足</p>
                  <ul className="mt-1 list-inside list-disc text-xs text-cyber-text-secondary">{previewRule.definition.required_signals.map((signal, index) => <li key={`${index}-${signal}`}>{signal}</li>)}</ul>
                </div>}
                <div>
                  <p className="text-xs text-cyber-text-muted">匹配信号（任一）</p>
                  <ul className="mt-1 list-inside list-disc text-xs text-cyber-text-secondary">{previewRule.definition.positive_signals.map((signal, index) => <li key={`${index}-${signal}`}>{signal}</li>)}</ul>
                </div>
                {!!previewRule.definition.negative_signals.length && <div>
                  <p className="text-xs text-cyber-text-muted">排除情形</p>
                  <ul className="mt-1 list-inside list-disc text-xs text-cyber-text-secondary">{previewRule.definition.negative_signals.map((signal, index) => <li key={`${index}-${signal}`}>{signal}</li>)}</ul>
                </div>}
                {!isApplied && draftRule && <Button type="button" onClick={approveRule} disabled={agentBusy}>确认并应用此规则</Button>}
              </div>
            })()}
            {agentError && <p role="alert" className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{agentError}</p>}
          </section>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block space-y-1.5 text-sm text-cyber-text-secondary">
              最多采集内容数（1–100）
              <Input type="number" min={1} max={100} value={maxContents} onChange={(event) => setMaxContents(Number(event.target.value))} />
            </label>
            <label className="block space-y-1.5 text-sm text-cyber-text-secondary">
              每条内容最多评论数（1–1000）
              <Input type="number" min={1} max={1000} value={maxComments} onChange={(event) => setMaxComments(Number(event.target.value))} />
            </label>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block space-y-1.5 text-sm text-cyber-text-secondary">
              运行计划
              <select className={fieldClass} value={scheduleType} onChange={(event) => setScheduleType(event.target.value as TaskPayload['schedule_type'])}>
                <option value="manual">仅手动</option><option value="interval">固定间隔</option><option value="cron">定时表达式</option>
              </select>
            </label>
            {scheduleType !== 'manual' && <label className="block space-y-1.5 text-sm text-cyber-text-secondary">
              {scheduleType === 'interval' ? '间隔分钟（至少 60）' : '定时表达式（5 段，上海时区）'}
              <Input value={scheduleValue} onChange={(event) => setScheduleValue(event.target.value)} required placeholder={scheduleType === 'interval' ? '例如 360' : '例如 0 9 * * *'} />
            </label>}
          </div>
          {error && <p role="alert" className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</p>}
          <div className="flex justify-end gap-3 border-t border-cyber-border-subtle pt-4">
            <Button type="button" variant="outline" onClick={onClose}>取消</Button>
            <Button type="submit" disabled={busy}>{busy ? '保存中…' : task ? '保存修改' : '创建任务'}</Button>
          </div>
        </form>
      </section>
    </div>
  )
}
