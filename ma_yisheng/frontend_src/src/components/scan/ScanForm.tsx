import { useEffect, useMemo, useRef, useState } from 'react'
import JSZip from 'jszip'
import { scanPath, scanUpload } from '../../api/scan'
import { listRuleSets, type RuleSetSummary } from '../../api/ruleSets'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Card } from '../ui/Card'
import { usePageStateStore, type ScanTab } from '../../store/pageStateStore'

interface Props {
  onSubmitted: () => void
}

const languageOptions = [
  { value: 'auto', label: '自动识别' },
  { value: 'python', label: 'Python' },
  { value: 'java', label: 'Java' },
  { value: 'go', label: 'Go' },
  { value: 'js', label: 'JavaScript / TypeScript' },
  { value: 'php', label: 'PHP' },
  { value: 'c', label: 'C' },
]

const sceneOptions = [
  { value: 'full', label: 'Full（Web/source-sink）' },
  { value: 'minimal', label: 'Minimal（快速）' },
]

export function ScanForm({ onSubmitted }: Props) {
  const scanForm = usePageStateStore((s) => s.scanForm)
  const setScanForm = usePageStateStore((s) => s.setScanForm)
  const resetScanInput = usePageStateStore((s) => s.resetScanInput)
  const { tab, path, engine, lang, scene, timeout, ruleSetIds } = scanForm
  const [ruleSets, setRuleSets] = useState<RuleSetSummary[]>([])
  const [ruleSetsError, setRuleSetsError] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    listRuleSets()
      .then((res) => {
        setRuleSets(res.data.rule_sets ?? [])
        setRuleSetsError('')
      })
      .catch((err) => setRuleSetsError(err instanceof Error ? err.message : '规则集加载失败'))
  }, [])

  const usableRuleSets = useMemo(() => {
    const currentLang = lang === 'auto' ? '' : lang
    return ruleSets.filter((rs) => {
      if (rs.is_official) return false
      if (!currentLang) return true
      return rs.lang === currentLang
    })
  }, [ruleSets, lang])

  const toggleRuleSet = (id: number) => {
    setScanForm({
      ruleSetIds: ruleSetIds.includes(id)
        ? ruleSetIds.filter((x) => x !== id)
        : [...ruleSetIds, id],
    })
  }

  const submit = async () => {
    setError('')
    setLoading(true)
    try {
      if (tab === 'upload') {
        if (!file) { setError('请选择文件'); setLoading(false); return }
        let uploadFile = file
        if (!file.name.endsWith('.zip')) {
          const zip = new JSZip()
          zip.file(file.name, file)
          const blob = await zip.generateAsync({ type: 'blob' })
          uploadFile = new File([blob], file.name.replace(/\.[^.]+$/, '') + '.zip', { type: 'application/zip' })
        }
        await scanUpload(uploadFile, { engine, lang, scene, timeout: Number(timeout) || 1800, rule_set_ids: ruleSetIds })
      } else {
        if (!path.trim()) { setError('请填写路径'); setLoading(false); return }
        await scanPath({ scan_path: path.trim(), engine, lang, scene, timeout: Number(timeout) || 1800, rule_set_ids: ruleSetIds })
      }
      setFile(null)
      resetScanInput()
      if (fileRef.current) fileRef.current.value = ''
      onSubmitted()
    } catch (e: unknown) {
      let msg = ''
      const err = e as any
      if (err?.response) {
        // 服务器返回了错误
        const status = err.response.status
        const detail = err.response.data?.detail
        msg = `[HTTP ${status}] ${typeof detail === 'string' ? detail : JSON.stringify(detail)}`
      } else if (err?.request) {
        // 请求发出了但没收到响应（真正的 network error）
        msg = `无法连接服务器 (${window.location.origin} → 47.94.95.178:8000)，请检查：\n1. 服务器是否在运行\n2. 网络是否能访问 47.94.95.178:8000`
      } else {
        msg = e instanceof Error ? e.message : '提交失败'
      }
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const selectDirectory = async () => {
    if (!window.maYisheng?.selectDirectory) {
      setError('当前环境不支持目录选择，请手动填写本地路径')
      return
    }
    setError('')
    const res = await window.maYisheng.selectDirectory()
    if (res.ok && res.path) {
      setScanForm({ tab: 'path', path: res.path })
    }
  }

  return (
    <Card className="p-5">
      <h2 className="text-lg font-black uppercase mb-4">提交扫描</h2>

      {/* Tab 切换 */}
      <div className="flex mb-4 border-3 border-black w-fit">
        {(['path', 'upload'] as ScanTab[]).map((t) => (
          <button
            key={t}
            onClick={() => setScanForm({ tab: t })}
            className={`px-4 py-1.5 text-xs font-black uppercase tracking-wider transition-colors
              ${tab === t ? 'bg-black text-brutal-yellow' : 'bg-white text-black hover:bg-brutal-gray'}`}
          >
            {t === 'upload' ? '上传 ZIP' : '本地路径'}
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-3">
        {tab === 'upload' ? (
          <div>
            <label className="text-xs font-bold uppercase tracking-wider block mb-1">选择文件（zip 或单个代码文件）</label>
            <input
              ref={fileRef}
              type="file"
              accept=".zip,.py,.js,.ts,.java,.go,.php,.rb,.c,.cpp,.cs,.rs"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="input-brutal text-sm file:mr-3 file:border-0 file:bg-brutal-yellow
                         file:font-bold file:uppercase file:text-xs file:px-3 file:py-1 file:cursor-pointer"
            />
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            <Input
              label="本地项目路径"
              placeholder="/Users/infinite/Downloads/project"
              value={path}
              onChange={(e) => setScanForm({ path: e.target.value })}
            />
            <Button variant="white" size="sm" onClick={selectDirectory} type="button">
              选择文件夹
            </Button>
          </div>
        )}

        {/* 语言选择 */}
        <div>
          <label className="text-xs font-bold uppercase tracking-wider block mb-1">扫描语言</label>
          <select
            value={lang}
            onChange={(e) => setScanForm({ lang: e.target.value })}
            className="input-brutal text-sm"
          >
            {languageOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </div>

        {/* 规则模式 */}
        <div>
          <label className="text-xs font-bold uppercase tracking-wider block mb-1">规则模式</label>
          <select
            value={scene}
            onChange={(e) => setScanForm({ scene: e.target.value })}
            className="input-brutal text-sm"
          >
            {sceneOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </div>

        {/* 引擎选择 */}
        <div>
          <label className="text-xs font-bold uppercase tracking-wider block mb-1">扫描引擎</label>
          <select
            value={engine}
            onChange={(e) => setScanForm({ engine: e.target.value })}
            className="input-brutal text-sm"
          >
            <option value="semgrep">Semgrep</option>
            <option value="yasa">YASA</option>
          </select>
        </div>

        <Input
          label="扫描超时（秒）"
          type="number"
          min="60"
          max="1800"
          value={timeout}
          onChange={(e) => setScanForm({ timeout: e.target.value })}
        />

        <div>
          <label className="text-xs font-bold uppercase tracking-wider block mb-1">自定义规则集</label>
          <div className="border-3 border-black bg-white max-h-36 overflow-y-auto">
            {ruleSetsError && (
              <div className="px-3 py-2 text-xs font-bold text-brutal-red">{ruleSetsError}</div>
            )}
            {!ruleSetsError && usableRuleSets.length === 0 && (
              <div className="px-3 py-2 text-xs font-bold text-gray-500">暂无匹配当前语言的自定义规则集</div>
            )}
            {usableRuleSets.map((rs) => {
              const id = Number(rs.id)
              return (
                <label key={String(rs.id)} className="flex items-start gap-2 px-3 py-2 border-b-2 border-dashed border-gray-200 text-xs font-bold cursor-pointer hover:bg-brutal-gray">
                  <input
                    type="checkbox"
                    checked={ruleSetIds.includes(id)}
                    onChange={() => toggleRuleSet(id)}
                    className="mt-0.5"
                  />
                  <span className="min-w-0">
                    <span className="block truncate">{rs.name}</span>
                    <span className="block text-[10px] text-gray-500">{rs.lang}/{rs.scene || 'full'} · {rs.rule_count || 0} 条</span>
                  </span>
                </label>
              )
            })}
          </div>
        </div>

        {error && (
          <p className="text-brutal-red text-xs font-bold border-2 border-brutal-red px-3 py-2 bg-white whitespace-pre-wrap">
            {error}
          </p>
        )}

        <Button
          variant="yellow"
          size="md"
          onClick={submit}
          disabled={loading}
          className="w-full"
        >
          {loading ? '提交中...' : '开始扫描'}
        </Button>
      </div>
    </Card>
  )
}
