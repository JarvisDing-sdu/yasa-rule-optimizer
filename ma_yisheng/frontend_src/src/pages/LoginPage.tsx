import { useEffect, useState, useRef } from 'react'
import { sendCode, register, login, resetPassword } from '../api/auth'
import { getRuntimeConfig } from '../api/config'
import { useAuthStore } from '../store/authStore'
import { useNavigate } from 'react-router-dom'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'

type Tab = 'login' | 'register' | 'reset'

const TAB_LABEL: Record<Tab, string> = {
  login:    '登录',
  register: '注册',
  reset:    '忘记密码',
}

export default function LoginPage() {
  const [tab, setTab] = useState<Tab>('login')
  const [email, setEmail]       = useState('')
  const [code, setCode]         = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm]   = useState('')
  const [countdown, setCountdown] = useState(0)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')
  const [success, setSuccess]   = useState('')
  const [configEditable, setConfigEditable] = useState(false)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const authLogin = useAuthStore((s) => s.login)
  const nav = useNavigate()

  useEffect(() => {
    getRuntimeConfig()
      .then((res) => setConfigEditable(res.data.editable !== false))
      .catch(() => setConfigEditable(false))
  }, [])

  const startCountdown = () => {
    setCountdown(60)
    timerRef.current = setInterval(() => {
      setCountdown((v) => {
        if (v <= 1) { clearInterval(timerRef.current!); return 0 }
        return v - 1
      })
    }, 1000)
  }

  const handleSendCode = async () => {
    if (!email) { setError('请填写邮箱'); return }
    setError(''); setLoading(true)
    try {
      await sendCode(email)
      startCountdown()
      setSuccess('验证码已发送，请查收邮件')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '发送失败')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async () => {
    if (!email) { setError('请填写邮箱'); return }
    setError(''); setSuccess(''); setLoading(true)
    try {
      if (tab === 'login') {
        const res = await login(email, password)
        authLogin(res.data.token ?? res.data.access_token, email)
        nav('/')
      } else if (tab === 'register') {
        if (password !== confirm) { setError('两次密码不一致'); setLoading(false); return }
        await register(email, code, password)
        setSuccess('注册成功，请登录')
        setTab('login')
      } else {
        if (password !== confirm) { setError('两次密码不一致'); setLoading(false); return }
        await resetPassword(email, code, password)
        setSuccess('密码已重置，请登录')
        setTab('login')
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '操作失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="min-h-screen bg-brutal-cream flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* 标题 */}
        <div className="mb-8 text-center">
          <h1 className="text-5xl font-black uppercase tracking-tight">码医生</h1>
          <p className="text-sm font-bold uppercase tracking-widest text-gray-500 mt-1">
            Code Security Scanner
          </p>
        </div>

        {/* 卡片 */}
        <div className="border-3 border-black shadow-brutal-lg bg-white">
          {/* Tab 栏 */}
          <div className="flex border-b-3 border-black">
            {(Object.keys(TAB_LABEL) as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => { setTab(t); setError(''); setSuccess('') }}
                className={`flex-1 py-3 text-xs font-black uppercase tracking-wider transition-colors
                  ${tab === t
                    ? 'bg-brutal-yellow text-black border-r-3 border-black last:border-r-0'
                    : 'bg-white text-black hover:bg-brutal-gray border-r-3 border-black last:border-r-0'}`}
              >
                {TAB_LABEL[t]}
              </button>
            ))}
          </div>

          {/* 表单 */}
          <div className="p-6 flex flex-col gap-4">
            <Input
              label="邮箱"
              type="email"
              placeholder="your@email.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />

            {/* 验证码行（注册/重置） */}
            {(tab === 'register' || tab === 'reset') && (
              <div className="flex gap-2">
                <Input
                  label="验证码"
                  placeholder="6位验证码"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                />
                <div className="flex flex-col gap-1">
                  <label className="text-xs font-bold uppercase tracking-wider opacity-0">发送</label>
                  <Button
                    variant="cyan"
                    size="md"
                    onClick={handleSendCode}
                    disabled={countdown > 0 || loading}
                    className="whitespace-nowrap"
                  >
                    {countdown > 0 ? `${countdown}s` : '发送'}
                  </Button>
                </div>
              </div>
            )}

            <Input
              label="密码"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />

            {(tab === 'register' || tab === 'reset') && (
              <Input
                label="确认密码"
                type="password"
                placeholder="••••••••"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
              />
            )}

            {error && (
              <div className="border-3 border-brutal-red bg-white px-3 py-2 flex flex-col gap-2">
                <p className="text-brutal-red text-xs font-black">{error}</p>
                {configEditable && (error.includes('邮件') || error.includes('SMTP') || error.includes('Connection')) && (
                  <Button variant="white" size="sm" onClick={() => nav('/setup')} className="w-fit">
                    返回环境配置
                  </Button>
                )}
              </div>
            )}
            {success && (
              <div className="border-3 border-black bg-brutal-yellow px-3 py-2">
                <p className="text-black text-xs font-black">{success}</p>
              </div>
            )}

            <Button
              variant="black"
              size="lg"
              onClick={handleSubmit}
              disabled={loading}
              className="w-full mt-2"
            >
              {loading ? '处理中...' : TAB_LABEL[tab]}
            </Button>
          </div>
        </div>
      </div>
    </main>
  )
}
