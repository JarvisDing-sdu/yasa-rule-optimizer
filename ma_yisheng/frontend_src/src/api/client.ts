import axios from 'axios'

export const API_BASE = window.location.origin

const client = axios.create({
  baseURL: API_BASE,
  timeout: 180000,
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('email')
      // 不 reject，避免调用方显示错误（本拦截器已处理跳转）
      setTimeout(() => { window.location.href = '/login' }, 0)
      return Promise.resolve({ data: null } as any)
    }
    const detail = err.response?.data?.detail
    if (detail) {
      return Promise.reject(new Error(typeof detail === 'string' ? detail : JSON.stringify(detail)))
    }
    return Promise.reject(err)
  }
)

export default client
