import { NavLink, Outlet } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { getRuntimeConfig } from '../../api/config'
import { useAuthStore } from '../../store/authStore'
import { MascotCard } from '../mascot/MascotCard'
import { Button } from '../ui/Button'

const NAV_ITEMS = [
  { to: '/',        label: '仪表盘',   icon: '◆' },
  { to: '/reports', label: '报告列表', icon: '◇' },
  { to: '/rule-workshop', label: '规则工坊', icon: '◆' },
]

export function AppLayout() {
  const { email, logout } = useAuthStore()
  const [configEditable, setConfigEditable] = useState(false)

  useEffect(() => {
    getRuntimeConfig()
      .then((res) => setConfigEditable(res.data.editable !== false))
      .catch(() => setConfigEditable(false))
  }, [])

  const navItems = configEditable
    ? [...NAV_ITEMS, { to: '/settings', label: '环境配置', icon: '◇' }]
    : NAV_ITEMS

  return (
    <div className="min-h-screen bg-brutal-cream flex">
      {/* ── 左侧栏 ── */}
      <aside className="w-72 shrink-0 border-r-3 border-black flex flex-col bg-white">
        {/* 品牌 */}
        <div className="border-b-3 border-black px-5 py-4 bg-black">
          <h1 className="text-brutal-yellow text-xl font-black uppercase tracking-tight">码医生</h1>
          <p className="text-brutal-gray text-xs uppercase tracking-widest mt-0.5">Security Scanner</p>
        </div>

        {/* 吉祥物 */}
        <div className="border-b-3 border-black p-6 flex justify-center bg-brutal-cream">
          <MascotCard />
        </div>

        {/* 导航 */}
        <nav className="border-b-3 border-black py-3 px-3 flex flex-col gap-1">
          {navItems.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 text-sm font-black uppercase tracking-wider transition-colors border-3 ${
                  isActive
                    ? 'bg-brutal-yellow text-black border-black shadow-brutal-sm'
                    : 'bg-white text-black border-transparent hover:bg-brutal-gray hover:border-black'
                }`
              }
            >
              <span className="text-lg">{icon}</span>
              {label}
            </NavLink>
          ))}
        </nav>

        {/* 用户信息 */}
        <div className="border-b-3 border-black px-5 py-4">
          <p className="text-xs font-black uppercase tracking-wider text-gray-500 mb-1">当前用户</p>
          <p className="text-sm font-bold truncate">{email}</p>
        </div>

        {/* 退出 */}
        <div className="mt-auto p-5">
          <Button variant="red" size="sm" onClick={logout} className="w-full">
            退出登录
          </Button>
        </div>
      </aside>

      {/* ── 主区域 ── */}
      <main className="flex-1 p-6 overflow-y-auto">
        <div className="max-w-7xl mx-auto">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
