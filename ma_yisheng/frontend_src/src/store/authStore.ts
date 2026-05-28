import { create } from 'zustand'

interface AuthState {
  token: string | null
  email: string | null
  login: (token: string, email: string) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('token'),
  email: localStorage.getItem('email'),
  login: (token, email) => {
    localStorage.setItem('token', token)
    localStorage.setItem('email', email)
    set({ token, email })
  },
  logout: () => {
    localStorage.removeItem('token')
    localStorage.removeItem('email')
    set({ token: null, email: null })
  },
}))
