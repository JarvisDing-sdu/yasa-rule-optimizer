import { useState, useRef } from 'react'
import JSZip from 'jszip'
import { scanPath, scanUpload } from '../../api/scan'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Card } from '../ui/Card'

interface Props {
  onSubmitted: () => void
}

type Tab = 'upload' | 'path'

const languageOptions = [
  { value: 'auto', label: '自动识别' },
  { value: 'python', label: 'Python' },
  { value: 'java', label: 'Java' },
  { value: 'go', label: 'Go' },
  { value: 'js', label: 'JavaScript / TypeScript' },
  { value: 'php', label: 'PHP' },
  { value: 'c', label: 'C' },
]

export function ScanForm({ onSubmitted }: Props) {
  const [tab, setTab] = useState<Tab>('upload')
  const [path, setPath] = useState('')
  const [engine, setEngine] = useState('semgrep')
  const [lang, setLang] = useState('auto')
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

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
        await scanUpload(uploadFile, { engine, lang })
      } else {
        if (!path.trim()) { setError('请填写路径'); setLoading(false); return }
        await scanPath({ scan_path: path.trim(), engine, lang })
      }
      setFile(null)
      setPath('')
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

  return (
    <Card className="p-5">
      <h2 className="text-lg font-black uppercase mb-4">提交扫描</h2>

      {/* Tab 切换 */}
      <div className="flex mb-4 border-3 border-black w-fit">
        {(['upload', 'path'] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-1.5 text-xs font-black uppercase tracking-wider transition-colors
              ${tab === t ? 'bg-black text-brutal-yellow' : 'bg-white text-black hover:bg-brutal-gray'}`}
          >
            {t === 'upload' ? '上传 ZIP' : '服务器路径'}
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
          <Input
            label="服务器路径"
            placeholder="/home/user/project"
            value={path}
            onChange={(e) => setPath(e.target.value)}
          />
        )}

        {/* 语言选择 */}
        <div>
          <label className="text-xs font-bold uppercase tracking-wider block mb-1">扫描语言</label>
          <select
            value={lang}
            onChange={(e) => setLang(e.target.value)}
            className="input-brutal text-sm"
          >
            {languageOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </div>

        {/* 引擎选择 */}
        <div>
          <label className="text-xs font-bold uppercase tracking-wider block mb-1">扫描引擎</label>
          <select
            value={engine}
            onChange={(e) => setEngine(e.target.value)}
            className="input-brutal text-sm"
          >
            <option value="semgrep">Semgrep</option>
            <option value="yasa">YASA</option>
          </select>
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
