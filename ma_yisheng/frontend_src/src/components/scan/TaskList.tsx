import { useNavigate } from 'react-router-dom'
import type { Task } from '../../api/scan'
import { Card } from '../ui/Card'
import { Button } from '../ui/Button'

const STATUS_STYLE: Record<string, string> = {
  pending:   'bg-brutal-gray text-black',
  running:   'bg-brutal-cyan text-black animate-pulse',
  done:      'bg-brutal-yellow text-black',
  completed: 'bg-brutal-yellow text-black',
  failed:    'bg-brutal-red text-white',
  cancelled: 'bg-brutal-red text-white',
}

const STATUS_LABEL: Record<string, string> = {
  pending:   '等待中',
  running:   '扫描中',
  done:      '已完成',
  completed: '已完成',
  failed:    '失败',
  cancelled: '已取消',
}

interface Props {
  tasks: Task[]
  loading: boolean
  onRefresh: () => void
}

interface ReportLink {
  path: string
  lang: string
  ok: boolean
  error: string
}

function getReportLinks(task: Task): ReportLink[] {
  const scans = task.result?.scans
  if (!scans) return []
  return scans
    .filter(s => s.report_dir || s.report_json)
    .map(s => ({
      path: s.report_dir || s.report_json!,
      lang: s.lang || s.engine || 'scan',
      ok: s.ok,
      error: s.error || '',
    }))
}

function getScanMessages(task: Task): string[] {
  const scans = task.result?.scans
  if (!scans) {
    return task.result?.error ? [task.result.error] : []
  }
  return scans
    .filter(s => !s.ok || s.error)
    .map(s => `${s.lang || s.engine}: ${s.error || (s.report_dir || s.report_json ? '扫描失败，已生成诊断报告' : '未生成报告')}`)
}

function reportLabel(item: ReportLink, index: number, total: number) {
  const { path } = item
  const name = path.split('/').filter(Boolean).pop() || `报告 ${index + 1}`
  if (!item.ok) return total > 1 ? `诊断 ${index + 1}: ${item.lang}` : '查看诊断'
  return total > 1 ? `报告 ${index + 1}: ${name}` : '查看报告'
}

export function TaskList({ tasks, loading, onRefresh }: Props) {
  const nav = useNavigate()

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-black uppercase">任务列表</h2>
        <Button variant="white" size="sm" onClick={onRefresh} disabled={loading}>
          {loading ? '...' : '刷新'}
        </Button>
      </div>

      {tasks.length === 0 ? (
        <p className="text-sm text-gray-500 font-medium py-4 text-center border-3 border-dashed border-black">
          暂无任务，提交扫描后在此查看
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {tasks.map((t) => {
            const reportLinks = getReportLinks(t)
            const scanMessages = getScanMessages(t)
            const successCount = reportLinks.filter(r => r.ok).length
            const diagnosticCount = reportLinks.length - successCount
            const isDone = t.status === 'done' || t.status === 'completed'

            return (
              <div
                key={t.task_id}
                className="flex items-start justify-between border-3 border-black p-3 bg-white gap-3"
              >
                <div className="flex flex-col gap-0.5 min-w-0 flex-1">
                  <span className="text-xs font-black uppercase truncate max-w-[200px]">
                    {t.scan_path ?? t.task_id.slice(0, 12) + '...'}
                  </span>
                  <span className="text-xs text-gray-500">
                    {t.created_at ? new Date(t.created_at).toLocaleString('zh-CN') : ''}
                  </span>
                  {t.progress && !isDone && (
                    <span className="text-xs text-gray-600 truncate max-w-full">
                      {t.progress}
                    </span>
                  )}
                  {isDone && reportLinks.length > 0 && (
                    <span className="text-xs text-gray-500 truncate max-w-full" title={reportLinks.map(r => r.path).join('\n')}>
                      {successCount > 0 ? `已生成 ${successCount} 份报告` : ''}
                      {successCount > 0 && diagnosticCount > 0 ? '，' : ''}
                      {diagnosticCount > 0 ? `${diagnosticCount} 份诊断报告` : ''}
                    </span>
                  )}
                  {scanMessages.length > 0 && (
                    <span className="text-xs text-brutal-red font-bold truncate max-w-full" title={scanMessages.join('\n')}>
                      {scanMessages[0]}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {isDone && reportLinks.length > 0 && (
                    <div className="flex flex-col gap-1.5 items-end">
                      {reportLinks.map((item, index) => (
                        <Button
                          key={item.path}
                          variant={item.ok ? 'yellow' : 'white'}
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation()
                            nav(`/report/${encodeURIComponent(item.path)}`)
                          }}
                          title={item.error || item.path}
                        >
                          {reportLabel(item, index, reportLinks.length)}
                        </Button>
                      ))}
                    </div>
                  )}
                  {isDone && reportLinks.length === 0 && (
                    <span className="bg-brutal-gray text-black border-2 border-black px-2 py-0.5 text-xs font-black">
                      无报告
                    </span>
                  )}
                  <span className={`${STATUS_STYLE[t.status] ?? 'bg-brutal-gray text-black'} border-2 border-black px-2 py-0.5 text-xs font-black uppercase`}>
                    {STATUS_LABEL[t.status] ?? t.status}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </Card>
  )
}
