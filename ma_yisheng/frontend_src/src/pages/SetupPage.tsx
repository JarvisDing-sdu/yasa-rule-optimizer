import SettingsPage from './SettingsPage'

export default function SetupPage() {
  return (
    <main className="min-h-screen bg-brutal-cream p-6 overflow-y-auto">
      <div className="max-w-5xl mx-auto">
        <div className="mb-6">
          <h1 className="text-4xl font-black uppercase">马医生</h1>
          <p className="text-sm font-bold text-gray-600 mt-1">首次启动需要先填写本地运行环境。</p>
        </div>
        <SettingsPage setupMode />
      </div>
    </main>
  )
}
