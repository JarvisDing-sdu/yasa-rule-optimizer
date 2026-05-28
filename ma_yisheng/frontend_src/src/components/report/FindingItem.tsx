import { useState } from 'react'
import type { Finding } from '../../api/reports'
import { reviewFinding, fixFinding, exploitFinding } from '../../api/reports'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'

interface Props {
  finding: Finding
  index: number
  reportPath: string
}

type AIAction = 'review' | 'fix' | 'exploit'

const ACTION_LABEL: Record<AIAction, string> = {
  review:  'AI 研判',
  fix:     '修复建议',
  exploit: '可利用性',
}

const ACTION_VARIANT: Record<AIAction, 'cyan' | 'yellow' | 'red'> = {
  review:  'cyan',
  fix:     'yellow',
  exploit: 'red',
}

const VERDICT_LABEL: Record<string, string> = {
  true_positive:  '真漏洞',
  false_positive: '误报',
  needs_review:   '需人工确认',
}

const VERDICT_COLOR: Record<string, string> = {
  true_positive:  'bg-brutal-red text-white',
  false_positive: 'bg-brutal-cyan text-black',
  needs_review:   'bg-brutal-yellow text-black',
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message
  return '请求失败，请重试。'
}

export function FindingItem({ finding, index: findingIndex, reportPath }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [results, setResults] = useState<Partial<Record<AIAction, string>>>({})
  const [loading, setLoading] = useState<AIAction | null>(null)

  const runAction = async (action: AIAction) => {
    if (results[action] || loading) return
    setLoading(action)
    try {
      const fn = action === 'review' ? reviewFinding : action === 'fix' ? fixFinding : exploitFinding
      const res = await fn(reportPath, findingIndex)
      const data = res.data as Record<string, any>
      let text = ''
      if (action === 'review') {
        text = `[${data.verdict_label}]\n${data.reason}`
      } else if (action === 'fix') {
        text = `${data.explanation}\n\n修复代码:\n${data.fix_code}\n\n攻击场景:\n${data.attack_scenario}`
      } else {
        text = `可利用性: ${data.exploitability}\n难度: ${data.difficulty}\n影响: ${data.impact}\n\n前置条件:\n${data.preconditions}\n\n攻击路径:\n${data.attack_path}\n\nPoC 提示:\n${data.poc_hint}`
      }
      setResults((prev) => ({ ...prev, [action]: text }))
    } catch (error) {
      setResults((prev) => ({ ...prev, [action]: `请求失败：${getErrorMessage(error)}` }))
    } finally {
      setLoading(null)
    }
  }

  // 已缓存的 AI 结果（从 GET findings 自带）
  const hasCachedReview = !!finding.llm_verdict
  const hasCachedFix = !!finding.fix_explanation
  const hasCachedExploit = !!finding.exploitability

  const cachedReviewText = hasCachedReview
    ? `[${VERDICT_LABEL[finding.llm_verdict!] ?? finding.llm_verdict}]\n${finding.llm_reason ?? ''}`
    : ''
  const cachedFixText = hasCachedFix
    ? `${finding.fix_explanation}\n\n修复代码:\n${finding.fix_code ?? ''}\n\n攻击场景:\n${finding.attack_scenario ?? ''}`
    : ''
  const cachedExploitText = hasCachedExploit
    ? `可利用性: ${finding.exploitability}\n难度: ${finding.exploit_difficulty}\n影响: ${finding.exploit_impact}\n\n前置条件:\n${finding.exploit_preconditions ?? ''}\n\n攻击路径:\n${finding.exploit_attack_path ?? ''}\n\nPoC 提示:\n${finding.exploit_poc_hint ?? ''}`
    : ''

  return (
    <div className="border-3 border-black bg-white">
      {/* 头部 */}
      <button
        className="w-full flex items-start gap-3 p-4 text-left hover:bg-brutal-gray transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        <Badge severity={finding.severity} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-black text-sm uppercase truncate">{finding.vuln_name || finding.sink_rule}</p>
            {hasCachedReview && (
              <span className={`${VERDICT_COLOR[finding.llm_verdict!] ?? 'bg-brutal-gray text-black'} border-2 border-black px-1.5 py-0.5 text-xs font-black`}>
                {VERDICT_LABEL[finding.llm_verdict!] ?? finding.llm_verdict}
              </span>
            )}
          </div>
          <p className="text-xs text-gray-600 mt-0.5 line-clamp-2">{finding.message}</p>
          <p className="text-xs font-mono text-gray-400 mt-1">
            {finding.file}:{finding.line}
          </p>
        </div>
        <span className="text-lg font-black shrink-0">{expanded ? '▲' : '▼'}</span>
      </button>

      {/* 展开内容 */}
      {expanded && (
        <div className="border-t-3 border-black p-4 flex flex-col gap-4">
          {/* 代码片段 */}
          {finding.snippet && (
            <div>
              <p className="text-xs font-black uppercase mb-1 text-gray-500">代码片段</p>
              <pre className="bg-black text-brutal-cyan text-xs p-3 overflow-x-auto font-mono leading-relaxed max-h-60 overflow-y-auto">
                {finding.snippet}
              </pre>
            </div>
          )}

          {/* 数据流（code_flow） */}
          {finding.code_flow && finding.code_flow.length > 0 && (
            <div>
              <p className="text-xs font-black uppercase mb-1 text-gray-500">数据流追踪</p>
              <div className="flex flex-col gap-1 border-3 border-black p-3 bg-brutal-cream">
                {finding.code_flow.map((step, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs">
                    <span className="font-black text-gray-400 shrink-0 w-6">{i + 1}.</span>
                    <div>
                      <p className="font-bold">{step.step}</p>
                      {step.line && <p className="font-mono text-gray-500">行 {step.line}</p>}
                      {step.snippet && <pre className="text-xs font-mono text-gray-600 mt-0.5">{step.snippet}</pre>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 引擎标签 */}
          {finding.engine && (
            <div className="flex items-center gap-1">
              <span className="text-xs font-bold text-gray-500 uppercase">引擎：</span>
              <span className="bg-black text-white border-2 border-black px-2 py-0.5 text-xs font-black">
                {finding.engine}
              </span>
            </div>
          )}

          {/* 已缓存的 AI 结果 */}
          {hasCachedReview && !results.review && (
            <div className="border-3 border-brutal-red p-3 bg-brutal-cream">
              <p className="text-xs font-black uppercase mb-2 text-brutal-red">
                AI 研判
                {finding.llm_reviewed_at && <span className="text-gray-500 font-medium ml-2 normal-case">({finding.llm_reviewed_at})</span>}
              </p>
              <p className="text-sm whitespace-pre-wrap leading-relaxed">{cachedReviewText}</p>
            </div>
          )}
          {hasCachedFix && !results.fix && (
            <div className="border-3 border-brutal-yellow p-3 bg-brutal-cream">
              <p className="text-xs font-black uppercase mb-2">修复建议</p>
              <p className="text-sm whitespace-pre-wrap leading-relaxed">{cachedFixText}</p>
            </div>
          )}
          {hasCachedExploit && !results.exploit && (
            <div className="border-3 border-brutal-red p-3 bg-brutal-cream">
              <p className="text-xs font-black uppercase mb-2">可利用性评估</p>
              <p className="text-sm whitespace-pre-wrap leading-relaxed">{cachedExploitText}</p>
            </div>
          )}

          {/* AI 操作按钮 */}
          <div className="flex gap-2 flex-wrap">
            {(Object.keys(ACTION_LABEL) as AIAction[]).map((action) => (
              <Button
                key={action}
                variant={ACTION_VARIANT[action]}
                size="sm"
                onClick={() => runAction(action)}
                disabled={loading === action || !!results[action]}
              >
                {loading === action ? '分析中...'
                  : results[action] ? `${ACTION_LABEL[action]} ✓`
                  : ACTION_LABEL[action]}
              </Button>
            ))}
          </div>

          {/* 新获取的 AI 结果 */}
          {(Object.keys(results) as AIAction[]).map((action) => (
            results[action] && (
              <div key={action} className="border-3 border-black p-3 bg-brutal-cream">
                <p className="text-xs font-black uppercase mb-2">{ACTION_LABEL[action]}</p>
                <p className="text-sm whitespace-pre-wrap leading-relaxed">{results[action]}</p>
              </div>
            )
          ))}
        </div>
      )}
    </div>
  )
}
