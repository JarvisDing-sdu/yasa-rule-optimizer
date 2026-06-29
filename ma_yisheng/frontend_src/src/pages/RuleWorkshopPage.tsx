import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { API_BASE } from '../api/client'
import { useAuthStore } from '../store/authStore'
import { Button } from '../components/ui/Button'

export default function RuleWorkshopPage() {
  const nav = useNavigate()
  const iframeRef = useRef<HTMLIFrameElement | null>(null)
  const loadTimerRef = useRef<number | null>(null)
  const loadedOnceRef = useRef(false)
  const token = useAuthStore((state) => state.token)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [reloadKey, setReloadKey] = useState(0)
  const url = useMemo(
    () => `${API_BASE}/rule-workshop?v=${reloadKey}&ts=${Date.now()}#token=${encodeURIComponent(token || '')}`,
    [token, reloadKey],
  )

  const clearLoadTimer = useCallback(() => {
    if (loadTimerRef.current) {
      window.clearTimeout(loadTimerRef.current)
      loadTimerRef.current = null
    }
  }, [])

  const reloadFrame = useCallback(() => {
    clearLoadTimer()
    loadedOnceRef.current = false
    setLoading(true)
    setError('')
    setReloadKey((value) => value + 1)
  }, [clearLoadTimer])

  const syncAuthToFrame = useCallback(() => {
    const authToken = token || localStorage.getItem('token')
    if (!authToken || !iframeRef.current?.contentWindow) return
    try {
      iframeRef.current.contentWindow.localStorage.setItem('token', authToken)
    } catch {
      // postMessage below is the fallback path for stricter frame storage policies.
    }
    iframeRef.current.contentWindow.postMessage({ type: 'MA_YISHENG_AUTH', token: authToken }, API_BASE)
  }, [token])

  useEffect(() => {
    let cancelled = false
    setLoading(!loadedOnceRef.current)
    setError('')

    loadTimerRef.current = window.setTimeout(() => {
      if (!cancelled && !loadedOnceRef.current) {
        window.maYisheng?.log?.(`rule-workshop iframe load timeout reloadKey=${reloadKey}`)
        setLoading(false)
        setError('规则工坊加载超时，请点击重新加载。')
      }
    }, 15000)

    fetch(`${API_BASE}/rule-workshop?probe=${reloadKey}&ts=${Date.now()}`, { cache: 'no-store' })
      .then(async (response) => {
        const text = await response.text()
        if (cancelled) return
        if (!response.ok || text.includes('Not Found')) {
          clearLoadTimer()
          if (!loadedOnceRef.current) {
            setLoading(false)
            setError(`规则工坊页面不可用：后端返回 ${response.status}`)
          }
          return
        }
        if (!text.trim()) {
          clearLoadTimer()
          if (!loadedOnceRef.current) {
            setLoading(false)
            setError('规则工坊页面为空，请点击重新加载。')
          }
        }
      })
      .catch((err) => {
        if (cancelled) return
        clearLoadTimer()
        if (!loadedOnceRef.current) {
          setLoading(false)
          setError(`规则工坊连接失败：${err instanceof Error ? err.message : String(err)}`)
        } else {
          window.maYisheng?.log?.(`rule-workshop probe ignored after load: ${err instanceof Error ? err.message : String(err)}`)
        }
      })

    return () => {
      cancelled = true
      clearLoadTimer()
    }
  }, [clearLoadTimer, reloadKey])

  useEffect(() => {
    return () => clearLoadTimer()
  }, [clearLoadTimer])

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
              reloadFrame()
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

      <div className="relative flex-1 min-h-0">
        {(loading || error) && (
          <div className="absolute inset-0 z-10 flex items-center justify-center border-3 border-black bg-white/95 shadow-brutal">
            <div className="w-full max-w-lg border-3 border-black bg-brutal-cream p-5 shadow-brutal">
              <p className="text-lg font-black">{error ? '规则工坊加载异常' : '规则工坊加载中...'}</p>
              <p className="mt-2 text-sm font-bold text-gray-700">
                {error || `正在连接本地后端 ${API_BASE}`}
              </p>
              <div className="mt-4 flex gap-2">
                <Button
                  variant="cyan"
                  size="sm"
                  onClick={() => {
                    reloadFrame()
                  }}
                >
                  重新加载
                </Button>
                <Button variant="white" size="sm" onClick={() => nav('/')}>返回仪表盘</Button>
              </div>
            </div>
          </div>
        )}

        <iframe
          ref={iframeRef}
          title="规则工坊"
          src={url}
          className="h-full w-full border-3 border-black bg-white shadow-brutal"
          onLoad={(event) => {
            clearLoadTimer()
            loadedOnceRef.current = true
            window.maYisheng?.log?.(`rule-workshop iframe loaded ${event.currentTarget.src}`)
            setLoading(false)
            setError('')
            syncAuthToFrame()
            window.setTimeout(syncAuthToFrame, 200)
            window.setTimeout(syncAuthToFrame, 800)
          }}
          onError={() => {
            clearLoadTimer()
            setLoading(false)
            setError('规则工坊加载失败')
          }}
        />
      </div>
    </div>
  )
}
