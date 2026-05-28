import { ScanForm } from '../components/scan/ScanForm'
import { TaskList } from '../components/scan/TaskList'
import { useTaskPoller } from '../hooks/useTaskPoller'

export default function DashboardPage() {
  const { tasks, loading, refresh } = useTaskPoller(true)

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-3xl font-black uppercase">扫描控制台</h2>
        <p className="text-sm text-gray-500 font-medium mt-1">
          上传代码包或指定服务器路径，开始漏洞扫描
        </p>
      </div>

      {/* Bento Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* 扫描提交 */}
        <div className="lg:col-span-1">
          <ScanForm onSubmitted={refresh} />
        </div>

        {/* 任务列表 */}
        <div className="lg:col-span-1">
          <TaskList tasks={tasks} loading={loading} onRefresh={refresh} />
        </div>

        {/* 统计卡片 */}
        <div className="lg:col-span-2 grid grid-cols-3 gap-4">
          {[
            { label: '总任务', value: tasks.length, bg: 'bg-white' },
            { label: '进行中', value: tasks.filter(t => t.status === 'running' || t.status === 'pending').length, bg: 'bg-brutal-cyan' },
            { label: '已完成', value: tasks.filter(t => t.status === 'done' || t.status === 'completed').length, bg: 'bg-brutal-yellow' },
          ].map(({ label, value, bg }) => (
            <div key={label} className={`${bg} border-3 border-black shadow-brutal p-4`}>
              <p className="text-xs font-black uppercase tracking-wider opacity-70">{label}</p>
              <p className="text-4xl font-black mt-1">{value}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
