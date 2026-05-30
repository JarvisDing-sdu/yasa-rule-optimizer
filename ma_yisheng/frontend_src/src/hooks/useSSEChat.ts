import { useCallback, useRef, useState } from 'react'
import { API_BASE } from '../api/client'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export function useSSEChat(reportPath: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const messagesRef = useRef<ChatMessage[]>([])

  // 保持 ref 与 state 同步
  messagesRef.current = messages

  const send = useCallback(async (question: string) => {
    if (isStreaming) return

    const token = localStorage.getItem('token')
    if (!token) return

    const userMsg: ChatMessage = { role: 'user', content: question }
    const prevMessages = messagesRef.current
    const nextMessages = [...prevMessages, userMsg]
    setMessages(nextMessages)
    setIsStreaming(true)

    abortRef.current = new AbortController()
    let assistantContent = ''

    setMessages((prev) => [...prev, { role: 'assistant', content: '' }])

    const allMessages = [...prevMessages, userMsg]

    const url = `${API_BASE}/api/reports/${encodeURIComponent(reportPath)}/chat/stream`

    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ messages: JSON.stringify(allMessages) }),
        signal: abortRef.current.signal,
      })

      if (!res.ok) {
        const errText = await res.text().catch(() => '')
        throw new Error(`HTTP ${res.status}: ${errText}`)
      }

      if (!res.body) throw new Error('No response body')

      const reader = res.body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const text = decoder.decode(value, { stream: true })
        const lines = text.split('\n')

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim()
          if (!raw || raw === '[DONE]') continue

          try {
            const parsed = JSON.parse(raw)
            const chunk = parsed.chunk ?? ''
            if (chunk) {
              assistantContent += chunk
              setMessages((prev) => {
                const next = [...prev]
                next[next.length - 1] = { role: 'assistant', content: assistantContent }
                return next
              })
            }
          } catch {
            // 忽略非 JSON 行
          }
        }
      }
    } catch (err: unknown) {
      const isAbort = err instanceof DOMException && err.name === 'AbortError'
      if (!isAbort) {
        const msg = err instanceof Error ? err.message : '请求失败'
        setMessages((prev) => {
          const next = [...prev]
          next[next.length - 1] = { role: 'assistant', content: `请求失败: ${msg}` }
          return next
        })
      }
    } finally {
      setIsStreaming(false)
    }
  }, [reportPath, isStreaming])

  const stop = useCallback(() => {
    abortRef.current?.abort()
    setIsStreaming(false)
  }, [])

  const clear = useCallback(() => {
    setMessages([])
  }, [])

  return { messages, isStreaming, send, stop, clear }
}
