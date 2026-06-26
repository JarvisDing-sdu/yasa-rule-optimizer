import { useEffect, useState } from 'react'
import { clearLoginLocks, getRuntimeConfig, saveRuntimeConfig, testMail, type RuntimeConfig } from '../api/config'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'

const DEFAULT_CONFIG: RuntimeConfig = {
  YASA_BUNDLE_PATH: '',
  YASA_EXECUTABLE: 'yasa',
  UAST_PYTHON_EXE: 'uast4py-linux-amd64',
  UAST_GO_EXE: 'uast4go-linux-amd64',
  LLM_PROVIDER: 'deepseek',
  LLM_BASE_URL: 'https://api.deepseek.com',
  LLM_API_KEY: '',
  LLM_MODEL: 'deepseek-v4-pro',
  SERVER_URL: '',
  GITHUB_TOKEN: '',
  SEMGREP_RULES_PATH: '',
  SCAN_TIMEOUT: '300',
  SMTP_HOST: '',
  SMTP_PORT: '587',
  SMTP_USER: '',
  SMTP_PASSWORD: '',
  SMTP_FROM_NAME: '马医生',
  SMTP_SECURITY: 'auto',
}

const FIELD_LABELS: Array<[keyof RuntimeConfig, string, string]> = [
  ['SMTP_HOST', 'SMTP 服务器', 'smtp.qq.com'],
  ['SMTP_PORT', 'SMTP 端口', '587'],
  ['SMTP_USER', '发件邮箱', 'your-email@qq.com'],
  ['SMTP_PASSWORD', '邮箱授权码', 'SMTP 授权码或密码'],
  ['SMTP_FROM_NAME', '发件人名称', '马医生'],
  ['SMTP_SECURITY', 'SMTP 加密方式', 'auto / starttls / ssl / none'],
  ['YASA_BUNDLE_PATH', 'YASA 引擎目录', '/path/to/yasa-linux-x64'],
  ['YASA_EXECUTABLE', 'YASA 可执行文件名', 'yasa'],
  ['UAST_PYTHON_EXE', 'Python UAST 文件名', 'uast4py-linux-amd64'],
  ['UAST_GO_EXE', 'Go UAST 文件名', 'uast4go-linux-amd64'],
  ['LLM_PROVIDER', 'LLM Provider', 'deepseek'],
  ['LLM_BASE_URL', 'LLM Base URL', 'https://api.deepseek.com'],
  ['LLM_API_KEY', 'LLM API Key', 'sk-...'],
  ['LLM_MODEL', 'LLM Model', 'deepseek-v4-pro'],
  ['SERVER_URL', '远程服务器 URL', '留空使用本地后端'],
  ['GITHUB_TOKEN', 'GitHub Token', '可选'],
  ['SEMGREP_RULES_PATH', 'Semgrep 离线规则目录', '可选'],
  ['SCAN_TIMEOUT', '扫描超时秒数', '300'],
]

type Props = {
  setupMode?: boolean
}

export default function SettingsPage({ setupMode = false }: Props) {
  const [values, setValues] = useState<RuntimeConfig>(DEFAULT_CONFIG)
  const [missing, setMissing] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testingMail, setTestingMail] = useState(false)
  const [clearingLocks, setClearingLocks] = useState(false)
  const [testEmail, setTestEmail] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [editable, setEditable] = useState(true)

  useEffect(() => {
    getRuntimeConfig()
      .then((res) => {
        const normalized = Object.fromEntries(
          Object.entries({ ...DEFAULT_CONFIG, ...res.data.values, SERVER_URL: res.data.values.SERVER_URL || '' })
            .map(([key, value]) => [key, value == null ? '' : String(value)])
        ) as RuntimeConfig
        setValues(normalized)
        setMissing(res.data.missing || [])
        setEditable(res.data.editable !== false)
      })
      .catch((err) => setError(err instanceof Error ? err.message : '读取配置失败'))
      .finally(() => setLoading(false))
  }, [])

  const updateField = (key: keyof RuntimeConfig, value: string) => {
    setValues((prev) => ({ ...prev, [key]: value }))
  }

  const handleSave = async () => {
    setSaving(true)
    setError('')
    setMessage('')
    try {
      const res = await saveRuntimeConfig(values)
      setMissing(res.data.missing || [])
      if ((res.data.missing || []).length === 0) {
        setMessage(setupMode ? '配置已保存，正在进入登录页...' : '配置已保存')
        if (setupMode) {
          setTimeout(() => { window.location.hash = '#/login'; window.location.reload() }, 600)
        }
      } else {
        setMessage('配置已保存，但仍缺少必要配置')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存配置失败')
    } finally {
      setSaving(false)
    }
  }

  const handleTestMail = async () => {
    setTestingMail(true)
    setError('')
    setMessage('')
    try {
      await saveRuntimeConfig(values)
      const res = await testMail(testEmail || values.SMTP_USER)
      setMessage(res.data.message || '测试邮件已发送')
    } catch (err) {
      setError(err instanceof Error ? err.message : '测试邮件发送失败')
    } finally {
      setTestingMail(false)
    }
  }

  const handleClearLoginLocks = async () => {
    setClearingLocks(true)
    setError('')
    setMessage('')
    try {
      const res = await clearLoginLocks()
      setMessage(res.data.message || '登录失败锁定已清除')
    } catch (err) {
      setError(err instanceof Error ? err.message : '清除登录锁定失败')
    } finally {
      setClearingLocks(false)
    }
  }

  if (loading) {
    return <div className="font-black">加载中...</div>
  }

  if (!editable) {
    return (
      <div className="border-3 border-black bg-white p-5">
        <h2 className="text-2xl font-black uppercase">环境配置不可用</h2>
        <p className="mt-2 text-sm font-bold text-gray-600">
          当前是服务器部署模式，环境变量由服务端管理员维护。
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h2 className="text-3xl font-black uppercase">环境配置</h2>
        <p className="text-sm font-bold text-gray-600 mt-1">
          配置会保存到本地后端目录的 .env 文件。必填项保存完整后才会进入登录页。
        </p>
      </div>

      {missing.length > 0 && (
        <div className="border-3 border-brutal-red bg-white p-4">
          <p className="text-sm font-black text-brutal-red mb-2">缺少必要配置</p>
          <ul className="list-disc pl-5 text-sm font-bold">
            {missing.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
      )}

      {message && <div className="border-3 border-black bg-brutal-yellow px-4 py-3 text-sm font-black">{message}</div>}
      {error && <div className="border-3 border-brutal-red bg-white px-4 py-3 text-sm font-black text-brutal-red">{error}</div>}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {FIELD_LABELS.map(([key, label, placeholder]) => (
          <Input
            key={key}
            label={label}
            placeholder={placeholder}
            type={key.includes('KEY') || key.includes('TOKEN') ? 'password' : 'text'}
            value={values[key]}
            onChange={(event) => updateField(key, event.target.value)}
          />
        ))}
      </div>

      <div className="border-3 border-black bg-white p-4 flex flex-col md:flex-row gap-3 md:items-end">
        <Input
          label="测试收件邮箱"
          placeholder="默认使用发件邮箱"
          value={testEmail}
          onChange={(event) => setTestEmail(event.target.value)}
        />
        <Button variant="cyan" size="md" onClick={handleTestMail} disabled={testingMail} className="md:w-40">
          {testingMail ? '测试中...' : '测试邮件'}
        </Button>
      </div>

      <div className="border-3 border-black bg-white p-4 flex flex-col md:flex-row gap-3 md:items-center md:justify-between">
        <div>
          <p className="text-sm font-black">登录锁定</p>
          <p className="text-xs font-bold text-gray-600">如果提示登录失败次数过多，可以清除本机锁定记录。</p>
        </div>
        <Button variant="red" size="md" onClick={handleClearLoginLocks} disabled={clearingLocks} className="md:w-44">
          {clearingLocks ? '清除中...' : '清除登录锁定'}
        </Button>
      </div>

      <div className="flex justify-end">
        <Button variant="black" size="lg" onClick={handleSave} disabled={saving}>
          {saving ? '保存中...' : '保存配置'}
        </Button>
      </div>
    </div>
  )
}
