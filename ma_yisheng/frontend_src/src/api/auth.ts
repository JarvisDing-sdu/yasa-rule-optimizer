import client from './client'

export const sendCode = (email: string) =>
  client.post('/api/auth/send-code', { email })

export const register = (email: string, code: string, password: string) =>
  client.post('/api/auth/register', { email, code, password })

export const login = (email: string, password: string) =>
  client.post<{ token: string; access_token?: string }>('/api/auth/login', { email, password })

export const resetPassword = (email: string, code: string, new_password: string) =>
  client.post('/api/auth/reset-password', { email, code, new_password })
