import { useRef, useEffect } from 'react'
import { useSSEChat } from '../../hooks/useSSEChat'
import { Button } from '../ui/Button'

interface Props {
  reportPath: string
}

export function ChatBox({ reportPath }: Props) {
  const { messages, isStreaming, send, stop } = useSSEChat(reportPath)
  const inputRef  = useRef<HTMLInputElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = () => {
    const q = inputRef.current?.value.trim()
    if (!q || isStreaming) return
    send(q)
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <div className="border-3 border-black flex flex-col" style={{ height: 360 }}>
      <div className="bg-black text-brutal-yellow px-4 py-2 font-black text-xs uppercase tracking-widest">
        AI 对话
      </div>

      {/* 消息区 */}
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3 bg-white">
        {messages.length === 0 && (
          <p className="text-xs text-gray-400 text-center mt-8">
            针对本报告提问，AI 将实时回答
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[80%] border-3 border-black px-3 py-2 text-sm whitespace-pre-wrap leading-relaxed
                ${m.role === 'user'
                  ? 'bg-brutal-yellow text-black shadow-brutal-sm'
                  : 'bg-brutal-cream text-black shadow-brutal-sm'}`}
            >
              {m.content}
              {isStreaming && i === messages.length - 1 && m.role === 'assistant' && (
                <span className="inline-block w-2 h-4 bg-black ml-1 animate-pulse" />
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* 输入区 */}
      <div className="border-t-3 border-black flex">
        <input
          ref={inputRef}
          type="text"
          placeholder="输入问题..."
          className="flex-1 px-4 py-3 text-sm font-medium outline-none bg-white border-r-3 border-black"
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          disabled={isStreaming}
        />
        {isStreaming ? (
          <Button variant="red" size="md" onClick={stop} className="rounded-none border-0 border-l-0">
            停止
          </Button>
        ) : (
          <Button variant="black" size="md" onClick={handleSend} className="rounded-none border-0">
            发送
          </Button>
        )}
      </div>
    </div>
  )
}
