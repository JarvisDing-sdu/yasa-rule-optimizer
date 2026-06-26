import { Component, type ErrorInfo, type ReactNode } from 'react'

type Props = {
  children: ReactNode
}

type State = {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ui-error]', error, info)
  }

  render() {
    if (!this.state.error) {
      return this.props.children
    }

    return (
      <main className="min-h-screen bg-brutal-cream p-6">
        <div className="max-w-3xl mx-auto border-3 border-brutal-red bg-white p-5 shadow-brutal-lg">
          <h1 className="text-2xl font-black text-brutal-red mb-3">页面加载失败</h1>
          <p className="text-sm font-bold mb-4">前端运行时发生错误，请把下面这段信息发给开发者。</p>
          <pre className="whitespace-pre-wrap break-words text-xs bg-black text-white p-4 overflow-auto">
            {this.state.error.message || '未知错误'}
          </pre>
        </div>
      </main>
    )
  }
}
