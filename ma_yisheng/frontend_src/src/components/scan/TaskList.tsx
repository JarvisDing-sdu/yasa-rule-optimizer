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

function getReportPaths(task: Task): string[] {
  const scans = task.result?.scans
  if (!scans) return []
  return scans
    .filter(s => s.ok && (s.report_dir || s.report_json))
    .map(s => s.report_dir || s.report_json!)
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
            const reportPaths = getReportPaths(t)
            const isDone = t.status === 'done' || t.status === 'completed'

            return (
              <div
                key={t.task_id}
                className="flex items-center justify-between border-3 border-black p-3 bg-white"
              >
                <div className="flex flex-col gap-0.5 min-w-0 flex-1">
                  <span className="text-xs font-black uppercase truncate max-w-[200px]">
                    {t.scan_path ?? t.task_id.slice(0, 12) + '...'}
                  </span>
                  <span className="text-xs text-gray-500">
                    {t.created_at ? new Date(t.created_at).toLocaleString('zh-CN') : ''}
                  </span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {isDone && reportPaths.length > 0 && (
                    <Button
                      variant="yellow"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation()
                        nav(`/report/${encodeURIComponent(reportPaths[0])}`)
                      }}
                    >
                      查看报告
                    </Button>
                  )}
                  {isDone && reportPaths.length === 0 && (
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
