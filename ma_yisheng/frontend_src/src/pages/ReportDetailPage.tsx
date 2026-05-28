import { useEffect, useState } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { getFindings } from '../api/reports'
import { chainAnalysis } from '../api/scan'
import type { Finding } from '../api/reports'
import { FindingItem } from '../components/report/FindingItem'
import { ChatBox } from '../components/report/ChatBox'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'

export default function ReportDetailPage() {
  const { '*': encodedPath } = useParams()
  const reportPath = encodedPath ? decodeURIComponent(encodedPath) : ''
  const [searchParams] = useSearchParams()
  const taskId = searchParams.get('taskId') || ''
  const nav = useNavigate()

  const [findings, setFindings] = useState<Finding[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Chain analysis state
  const [chainLoading, setChainLoading] = useState(false)
  const [chainResult, setChainResult] = useState<{
    files_analyzed: number; chars_analyzed: number
    chains: string[]; chains_count: number; summary: string
  } | null>(null)

  useEffect(() => {
    if (!reportPath) return
    setLoading(true)
    getFindings(reportPath)
      .then((res) => setFindings(res.data.findings ?? []))
      .catch(() => setError('加载报告失败'))
      .finally(() => setLoading(false))
  }, [reportPath])

  const counts = {
    '高危': findings.filter(f => f.severity === '高危').length,
    '中危': findings.filter(f => f.severity === '中危').length,
    '低危': findings.filter(f => f.severity === '低危').length,
  }

  const handleChainAnalysis = async () => {
    if (!taskId) return
    setChainLoading(true)
    setChainResult(null)
    try {
      const res = await chainAnalysis(taskId)
      const d = res.data
      setChainResult({
        files_analyzed: d.files_analyzed,
        chars_analyzed: d.chars_analyzed,
        chains: d.chains,
        chains_count: d.chains_count,
        summary: d.summary,
      })
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '未知错误'
      alert(`漏洞链分析失败: ${msg}`)
    } finally {
      setChainLoading(false)
    }
  }

  const sorted = [...findings].sort((a, b) => {
    const order: Record<string, number> = { '高危': 0, '中危': 1, '低危': 2 }
    return (order[a.severity] ?? 3) - (order[b.severity] ?? 3)
  })

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <Button variant="white" size="sm" onClick={() => nav('/reports')}>← 返回</Button>
        <h2 className="text-3xl font-black uppercase">报告详情</h2>
      </div>

      {loading && (
        <Card className="p-8 text-center">
          <p className="font-black uppercase animate-pulse">加载中...</p>
        </Card>
      )}

      {error && (
        <Card className="p-4 border-brutal-red shadow-brutal-red mb-4">
          <p className="text-brutal-red font-black text-sm">{error}</p>
        </Card>
      )}

      {!loading && !error && (
        <div className="flex flex-col gap-6">
          {/* 摘要 */}
          <div className="grid grid-cols-3 gap-3">
            <Card className="p-4 bg-brutal-red text-white flex flex-col items-center">
              <p className="text-xs font-black uppercase tracking-wider opacity-80">高危</p>
              <p className="text-4xl font-black">{counts['高危']}</p>
            </Card>
            <Card className="p-4 bg-brutal-yellow flex flex-col items-center">
              <p className="text-xs font-black uppercase tracking-wider opacity-70">中危</p>
              <p className="text-4xl font-black">{counts['中危']}</p>
            </Card>
            <Card className="p-4 bg-brutal-cyan flex flex-col items-center">
              <p className="text-xs font-black uppercase tracking-wider opacity-70">低危</p>
              <p className="text-4xl font-black">{counts['低危']}</p>
            </Card>
          </div>

          {/* 分析按钮 */}
          <div className="flex gap-3 flex-wrap">
            {taskId && (
              <Button
                variant="yellow"
                size="md"
                onClick={handleChainAnalysis}
                disabled={chainLoading}
              >
                {chainLoading ? '分析中...' : '漏洞链分析'}
              </Button>
            )}
          </div>

          {/* Chain analysis result */}
          {chainResult && (
            <Card className="p-4 border-brutal-yellow shadow-brutal-yellow">
              <p className="text-xs font-black uppercase text-brutal-yellow mb-2">漏洞链分析</p>
              <p className="text-sm mb-2">{chainResult.summary}</p>
              <p className="text-xs text-gray-500">分析了 {chainResult.files_analyzed} 个文件，发现 {chainResult.chains_count} 条攻击链</p>
              {chainResult.chains.length > 0 && (
                <div className="mt-2 flex flex-col gap-1">
                  {chainResult.chains.map((chain, i) => (
                    <div key={i} className="text-xs border border-brutal-yellow bg-yellow-50 p-2">{chain}</div>
                  ))}
                </div>
              )}
            </Card>
          )}

          {/* 空结果 */}
          {findings.length === 0 && (
            <Card className="p-8 text-center border-3 border-dashed border-black">
              <p className="font-black uppercase text-lg">未发现漏洞</p>
              <p className="text-sm font-medium mt-1">代码看起来很干净</p>
            </Card>
          )}

          <div className="flex flex-col gap-2">
            {sorted.map((f, i) => (
              <FindingItem key={f.fingerprint ?? i} finding={f} index={i} reportPath={reportPath} />
            ))}
          </div>
        </div>
      )}

      {/* AI 对话 */}
      {!loading && reportPath && (
        <div>
          <h2 className="text-xl font-black uppercase mb-3">AI 对话</h2>
          <ChatBox reportPath={reportPath} />
        </div>
      )}
    </div>
  )
}
