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
      // 跳转登录页，同时 reject 让调用方知道自己被中断了
      setTimeout(() => { window.location.href = '/login' }, 0)
      return Promise.reject(new Error('AUTH_REQUIRED'))
    }
    const detail = err.response?.data?.detail
    if (detail) {
      return Promise.reject(new Error(typeof detail === 'string' ? detail : JSON.stringify(detail)))
    }
    return Promise.reject(err)
  }
)

export default client
