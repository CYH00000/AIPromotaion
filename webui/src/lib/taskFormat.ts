import type { CollectionTask } from './collectorApi'

export const CONTENT_SORT_OPTIONS: ReadonlyArray<{
  value: CollectionTask['content_sort']
  label: string
}> = [
  { value: 'general', label: '综合排序' },
  { value: 'latest', label: '最新发布' },
  { value: 'most_liked', label: '最多点赞' },
]

export const PUBLISH_WINDOW_OPTIONS: ReadonlyArray<{
  value: CollectionTask['publish_time_days']
  label: string
}> = [
  { value: 0, label: '不限时间' },
  { value: 1, label: '一天内' },
  { value: 7, label: '一周内' },
  { value: 180, label: '半年内' },
]

export function contentSortLabel(value: CollectionTask['content_sort']): string {
  return CONTENT_SORT_OPTIONS.find((option) => option.value === value)?.label ?? '综合排序'
}

export function publishWindowLabel(value: CollectionTask['publish_time_days']): string {
  return PUBLISH_WINDOW_OPTIONS.find((option) => option.value === value)?.label ?? '不限时间'
}
