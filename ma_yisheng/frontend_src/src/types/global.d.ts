export {}

declare global {
  interface Window {
    maYisheng?: {
      apiBase?: string
      log?: (message: string) => void
      showPath?: (targetPath: string) => Promise<{ ok: boolean; error?: string }>
      selectDirectory?: () => Promise<{ ok: boolean; path?: string }>
    }
  }
}
