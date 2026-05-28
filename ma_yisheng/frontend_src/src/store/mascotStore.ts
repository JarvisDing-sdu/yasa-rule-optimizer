import { create } from 'zustand'

export type MascotStatus = 'idle' | 'scanning' | 'found'

interface MascotState {
  status: MascotStatus
  setStatus: (status: MascotStatus, autoReset?: boolean) => void
}

let resetTimer: ReturnType<typeof setTimeout> | null = null

export const useMascotStore = create<MascotState>((set) => ({
  status: 'idle',
  setStatus: (status, autoReset = true) => {
    if (resetTimer) { clearTimeout(resetTimer); resetTimer = null }
    set({ status })
    if (autoReset && status === 'found') {
      resetTimer = setTimeout(() => {
        set({ status: 'idle' })
        resetTimer = null
      }, 5000)
    }
  },
}))
