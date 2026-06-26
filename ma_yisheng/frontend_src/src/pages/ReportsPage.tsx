import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { listReports, deleteReport, toggleFavorite, getExportUrl } from '../api/reports'
import type { Report } from '../api/reports'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'

export default function ReportsPage() {
  const nav = useNavigate()
  const [reports, setReports] = useState<Report[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [deleting, setDeleting] = useState<string | null>(null)
  const [faving, setFaving] = useState<string | null>(null)

  const fetch = useCallback(async (project = '') => {
    setLoading(true)
    try {
      const res = await listReports(50, project)
      setReports(res.data.reports ?? [])
      setError('')
    } catch {
      setError('加载报告列表失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetch() }, [fetch])

  const handleSearch = () => {
    fetch(search.trim())
  }

  const handleDelete = async (path: string) => {
    if (!confirm('确认删除此报告？')) return
    setDeleting(path)
    try {
      await deleteReport(path)
      setReports(prev => prev.filter(r => r.path !== path))
    } catch {
      alert('删除失败，可能该报告已收藏')
    } finally {
      setDeleting(null)
    }
  }

  const handleFavorite = async (path: string) => {
    setFaving(path)
    try {
      const res = await toggleFavorite(path)
      setReports(prev => prev.map(r => r.path === path ? { ...r, favorite: res.data.favorite } : r))
    } catch {
      alert('操作失败')
    } finally {
      setFaving(null)
    }
  }

  const handleExport = (path: string) => {
    window.open(getExportUrl(path), '_blank')
  }

  const handleShowPath = async (path: string) => {
    if (!window.maYisheng?.showPath) {
      alert(path)
      return
    }
    const res = await window.maYisheng.showPath(path)
    if (!res.ok) alert(res.error || '打开报告目录失败')
  }

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-3xl font-black uppercase">历史报告</h2>
        <p className="text-sm text-gray-500 font-medium mt-1">浏览和管理所有扫描报告</p>
      </div>

      {/* 搜索栏 */}
      <div className="flex gap-3 mb-5">
        <Input
          placeholder="按项目名搜索..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          className="flex-1"
        />
        <Button variant="black" size="md" onClick={handleSearch}>
          搜索
        </Button>
        {search && (
          <Button variant="white" size="md" onClick={() => { setSearch(''); fetch() }}>
            清除
          </Button>
        )}
      </div>

      {/* 列表 */}
      {loading && (
        <Card className="p-8 text-center">
          <p className="font-black uppercase animate-pulse">加载中...</p>
        </Card>
      )}

      {error && (
        <Card className="p-4 border-brutal-red shadow-brutal-red">
          <p className="text-brutal-red font-black text-sm">{error}</p>
        </Card>
      )}

      {!loading && !error && reports.length === 0 && (
        <Card className="p-8 text-center border-3 border-dashed border-black">
          <p className="font-black uppercase text-lg">暂无报告</p>
          <p className="text-sm font-medium mt-1 text-gray-500">提交扫描后，报告会出现在这里</p>
        </Card>
      )}

      <div className="flex flex-col gap-3">
        {reports.map((r) => (
          <Card key={r.path} className="p-4 hover:shadow-brutal-lg transition-shadow cursor-pointer">
            <div className="flex items-start justify-between gap-4">
              {/* 点击进入详情 */}
              <div
                className="flex-1 min-w-0"
                onClick={() => nav(`/report/${encodeURIComponent(r.path)}`)}
              >
                <div className="flex items-center gap-2 flex-wrap mb-1">
                  <h3 className="text-base font-black uppercase truncate">{r.project}</h3>
                  {r.favorite && (
                    <span className="text-brutal-red text-xs font-black">★ 已收藏</span>
                  )}
                </div>
                <div className="flex items-center gap-3 text-xs font-bold text-gray-500 flex-wrap">
                  <span>{r.language}</span>
                  <span>·</span>
                  <span>{r.files_analyzed} 个文件</span>
                  <span>·</span>
                  <span>{new Date(r.mtime * 1000).toLocaleString('zh-CN')}</span>
                </div>
                <div className="mt-1 text-xs text-gray-500 truncate" title={r.path}>
                  {r.path}
                </div>
                {r.vuln_types.length > 0 && (
                  <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                    {r.vuln_types.slice(0, 5).map((v, i) => (
                      <span key={i} className="bg-black text-white border-2 border-black px-2 py-0.5 text-xs font-black">
                        {v}
                      </span>
                    ))}
                    {r.vuln_types.length > 5 && (
                      <span className="text-xs font-bold text-gray-500">+{r.vuln_types.length - 5}</span>
                    )}
                  </div>
                )}
              </div>

              {/* 右侧操作 */}
              <div className="flex flex-col items-end gap-2 shrink-0">
                <Badge severity={r.severity === '无' ? undefined : r.severity} />
                <span className="text-2xl font-black">{r.findings_count}</span>
                <span className="text-xs font-bold uppercase text-gray-500">个漏洞</span>
                <div className="flex gap-1.5">
                  <Button
                    variant={r.favorite ? 'yellow' : 'white'}
                    size="sm"
                    disabled={faving === r.path}
                    onClick={(e) => { e.stopPropagation(); handleFavorite(r.path) }}
                    title={r.favorite ? '取消收藏' : '收藏'}
                  >
                    {r.favorite ? '★' : '☆'}
                  </Button>
                  <Button
                    variant="cyan"
                    size="sm"
                    onClick={(e) => { e.stopPropagation(); handleExport(r.path) }}
                    title="导出 HTML"
                  >
                    ⬇
                  </Button>
                  <Button
                    variant="white"
                    size="sm"
                    onClick={(e) => { e.stopPropagation(); handleShowPath(r.path) }}
                    title="在 Finder 中打开报告目录"
                  >
                    目录
                  </Button>
                  <Button
                    variant="red"
                    size="sm"
                    disabled={deleting === r.path}
                    onClick={(e) => { e.stopPropagation(); handleDelete(r.path) }}
                  >
                    ✕
                  </Button>
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}
