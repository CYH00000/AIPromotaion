import api from './api'

export type PlatformId = 'dy' | 'xhs'
export type TaskState = 'enabled' | 'paused' | 'disabled'

export interface FilterRule {
  id: string
  lineage_id: string
  version: number
  parent_rule_id: string | null
  intent: string
  definition: {
    summary: string
    required_signals: string[]
    positive_signals: string[]
    negative_signals: string[]
  }
  model_name: string
  status: 'draft' | 'approved'
  created_at: string
  approved_at: string | null
}

export interface CollectionTask {
  id: string
  name: string
  platform: PlatformId
  source_mode: 'search' | 'detail'
  source_values: string[]
  include_keywords: string[]
  exclude_keywords: string[]
  filter_rule_id: string | null
  filter_rule: FilterRule | null
  max_contents: number
  max_comments_per_content: number
  schedule_type: 'manual' | 'interval' | 'cron'
  schedule_value: string | null
  state: TaskState
  next_run_at: string | null
  created_at: string
  updated_at: string
}

export interface CollectionRun {
  id: string
  task_id: string
  trigger_type: string
  status: string
  counts: Record<string, number>
  safe_summary: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface CollectedComment {
  id: string
  platform: PlatformId
  content_title: string
  content_url: string
  body: string
  comment_time: string | null
  latest_like_count: number
  latest_reply_count: number
  author_user_id: string | null
  author_nickname: string | null
  author_profile_url: string | null
  matched_keywords: string[]
  filter_rule_id: string | null
  filter_rule_version: number | null
  filter_reason: string | null
  last_observed_at: string
}

export interface AccountInfo {
  platform: PlatformId
  label: string
  configured: boolean
  profile_mode: 'cdp' | 'standard'
  last_login_at: string | null
  login_state: 'idle' | 'running' | 'succeeded' | 'failed'
  login_started_at: string | null
  login_error: string | null
}

export interface TaskPayload {
  name: string
  platform: PlatformId
  source_mode: 'search' | 'detail'
  source_values: string[]
  include_keywords: string[]
  exclude_keywords: string[]
  filter_rule_id: string | null
  max_contents: number
  max_comments_per_content: number
  schedule_type: 'manual' | 'interval' | 'cron'
  schedule_value: string | null
}

let csrfToken = ''

export const authApi = {
  async csrf() {
    const response = await api.get<{ csrf_token: string }>('/auth/csrf')
    csrfToken = response.data.csrf_token
    return csrfToken
  },
  async me() {
    const response = await api.get<{ username: string }>('/auth/me')
    return response.data
  },
  async login(username: string, password: string, token: string) {
    const response = await api.post<{ username: string }>(
      '/auth/login',
      { username, password },
      { headers: { 'X-CSRF-Token': token } },
    )
    await authApi.csrf()
    return response.data
  },
  async logout() {
    await authApi.csrf()
    await api.post('/auth/logout', null, { headers: { 'X-CSRF-Token': csrfToken } })
    csrfToken = ''
  },
}

async function mutate<T>(path: string, body?: unknown, method = 'post') {
  if (!csrfToken) await authApi.csrf()
  const response = await api.request<T>({
    url: path,
    method,
    data: body,
    headers: { 'X-CSRF-Token': csrfToken },
  })
  return response.data
}

export const collectorApi = {
  async tasks() {
    const response = await api.get<{ items: CollectionTask[] }>('/tasks')
    return response.data.items
  },
  createTask: (payload: TaskPayload) => mutate<CollectionTask>('/tasks', payload),
  updateTask: (taskId: string, payload: Partial<TaskPayload>) =>
    mutate<CollectionTask>(`/tasks/${taskId}`, payload, 'patch'),
  disableTask: (taskId: string) => mutate<void>(`/tasks/${taskId}`, undefined, 'delete'),
  runTask: (taskId: string) => mutate<{ run_id: string; status: string }>(`/tasks/${taskId}/run`),
  pauseTask: (taskId: string) => mutate<CollectionTask>(`/tasks/${taskId}/pause`),
  resumeTask: (taskId: string) => mutate<CollectionTask>(`/tasks/${taskId}/resume`),
  async runs(taskId?: string) {
    const response = await api.get<{ items: CollectionRun[] }>('/runs', {
      params: { task_id: taskId, limit: 20 },
    })
    return response.data.items
  },
  async comments(params: { q?: string; platform?: string; task_id?: string; offset?: number }) {
    const response = await api.get<{ items: CollectedComment[]; total: number; limit: number; offset: number }>(
      '/comments',
      { params: { ...params, limit: 50 } },
    )
    return response.data
  },
  async exportComments(format: 'csv' | 'xlsx', params: { q?: string; platform?: string; task_id?: string }) {
    const response = await api.get('/exports/comments', {
      params: { format, ...params },
      responseType: 'blob',
    })
    const url = URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url
    link.download = `comments.${format}`
    link.click()
    URL.revokeObjectURL(url)
  },
}

export const accountsApi = {
  async list() {
    const response = await api.get<{ items: AccountInfo[] }>('/accounts')
    return response.data.items
  },
  login: (platform: PlatformId) =>
    mutate<{ platform: string; status: string }>(`/accounts/${platform}/login`),
  unbind: (platform: PlatformId) =>
    mutate<void>(`/accounts/${platform}`, undefined, 'delete'),
}

export const filterRulesApi = {
  async status() {
    const response = await api.get<{ configured: boolean; model_name: string | null }>(
      '/filter-rules/config',
    )
    return response.data
  },
  createDraft: (intent: string, supersedes_rule_id?: string) =>
    mutate<FilterRule>('/filter-rules/drafts', {
      intent,
      supersedes_rule_id: supersedes_rule_id ?? null,
    }),
  approve: (ruleId: string) =>
    mutate<FilterRule>(`/filter-rules/${ruleId}/approve`),
}

export function apiErrorMessage(error: unknown): string {
  if (typeof error === 'object' && error !== null && 'response' in error) {
    const response = (error as { response?: { data?: { detail?: string } } }).response
    return response?.data?.detail ?? '请求失败，请检查服务状态后重试。'
  }
  return error instanceof Error ? error.message : '请求失败。'
}
