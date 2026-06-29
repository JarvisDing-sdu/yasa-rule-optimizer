import client from './client'

export interface ScanResultItem {
  lang: string
  ok: boolean
  report_dir: string | null
  error: string | null
  engine: string
  report_json?: string
  report_txt?: string
}

export interface Task {
  task_id: string
  status: 'pending' | 'running' | 'done' | 'failed' | 'completed' | 'cancelled'
  progress?: string
  scan_path?: string
  lang?: string
  created_at?: string
  result?: { scans?: ScanResultItem[]; error?: string }
}

export interface ScanParams {
  scan_path: string
  lang?: string
  scene?: string
  timeout?: number
  favorite?: boolean
  engine?: string
  rule_set_ids?: number[]
}

export const scanPath = (params: ScanParams) =>
  client.post<{ task_id: string }>('/api/scan', {
    path: params.scan_path,
    lang: params.lang,
    scene: params.scene,
    engine: params.engine,
    timeout: params.timeout,
    rule_set_ids: params.rule_set_ids ?? [],
  })

export const scanUpload = (file: File, params: Omit<ScanParams, 'scan_path'>) => {
  const form = new FormData()
  form.append('file', file)
  if (params.lang) form.append('lang', params.lang)
  if (params.scene) form.append('scene', params.scene)
  form.append('timeout', String(params.timeout ?? 300))
  form.append('favorite', String(params.favorite ?? false))
  if (params.engine) form.append('engine', params.engine)
  if (params.rule_set_ids?.length) form.append('rule_set_ids', params.rule_set_ids.join(','))
  return client.post<{ task_id: string }>('/api/scan/upload', form)
}

export const getTask = (taskId: string) =>
  client.get<Task>(`/api/scan/${taskId}`)

export const listTasks = () =>
  client.get<{ tasks: Task[]; count: number }>('/api/tasks')

export const chainAnalysis = (taskId: string) =>
  client.post<{
    ok: boolean; task_id: string; files_analyzed: number
    chars_analyzed: number; chains: string[]; chains_count: number; summary: string
  }>(`/api/scan/${taskId}/chain-analysis`)
