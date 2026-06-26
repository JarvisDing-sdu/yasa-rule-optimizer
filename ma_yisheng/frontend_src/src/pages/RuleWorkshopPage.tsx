import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { API_BASE } from '../api/client'
import { Button } from '../components/ui/Button'

export default function RuleWorkshopPage() {
  const nav = useNavigate()
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)
  const url = useMemo(() => `${API_BASE}/rule-workshop`, [])

  return (
    <div className="flex flex-col gap-4 h-[calc(100vh-48px)]">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-3xl font-black uppercase">规则工坊</h2>
          <p className="text-sm font-bold text-gray-600 mt-1">本地后端页面，运行在 {API_BASE}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="white" size="sm" onClick={() => nav('/')}>返回</Button>
          <Button
            variant="cyan"
            size="sm"
            onClick={() => {
              setError('')
              setReloadKey((value) => value + 1)
            }}
          >
            刷新
          </Button>
        </div>
      </div>

      {error && (
        <div className="border-3 border-brutal-red bg-white p-4">
          <p className="text-sm font-black text-brutal-red">{error}</p>
          <p className="text-xs font-bold text-gray-600 mt-2">可以返回仪表盘，或确认后端已正常启动后刷新。</p>
        </div>
      )}

      <iframe
        key={reloadKey}
        title="规则工坊"
        src={url}
        className="w-full flex-1 border-3 border-black bg-white shadow-brutal"
        onLoad={(event) => {
          try {
            const frame = event.currentTarget
            const title = frame.contentDocument?.title || ''
            const text = frame.contentDocument?.body?.innerText || ''
            if (title.includes('404') || text.includes('Not Found')) {
              setError('规则工坊页面未找到：后端返回 404 Not Found')
            }
          } catch {
            setError('')
          }
        }}
        onError={() => setError('规则工坊加载失败')}
      />
    </div>
  )
}
