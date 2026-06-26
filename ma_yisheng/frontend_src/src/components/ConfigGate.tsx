import { useEffect, useState } from 'react'
import { Outlet } from 'react-router-dom'
import { getRuntimeConfig } from '../api/config'
import SetupPage from '../pages/SetupPage'

export function ConfigGate() {
  const [loading, setLoading] = useState(true)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    getRuntimeConfig()
      .then((res) => {
        setReady(res.data.editable === false || (res.data.missing || []).length === 0)
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : '无法读取环境配置')
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return <main className="min-h-screen bg-brutal-cream p-6 font-black">正在检查环境配置...</main>
  }

  if (error) {
    return (
      <main className="min-h-screen bg-brutal-cream p-6">
        <div className="border-3 border-brutal-red bg-white p-5 font-black text-brutal-red">{error}</div>
      </main>
    )
  }

  return ready ? <Outlet /> : <SetupPage />
}
