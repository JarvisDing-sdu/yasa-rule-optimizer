import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import client from '../api/client'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'

interface Step {
  type: 'tool_call' | 'tool_result'
  tool?: string
  desc: string
}
interface AttachedFile {
  name: string
  content: string
  size: number
  path: string
}
interface Message {
  role: 'user' | 'assistant'
  content: string
  sources?: Array<{ title: string; url: string; domain: string }>
  steps?: Step[]
  reasoning?: string
  file?: AttachedFile
}
interface Conversation {
  id: number
  title: string
  created_at: string
  updated_at: string
  messages: Array<{ id: number; role: string; content: string; created_at: string }>
}

const MAX_FILE_SIZE = 50 * 1024 * 1024
const CODE_EXTS = ['.py','.java','.go','.js','.ts','.jsx','.tsx','.c','.cpp','.h','.php','.rb','.swift','.kt','.sql','.yaml','.yml','.json','.xml','.sh','.bash','.dockerfile','.zip']

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message
  return '请求失败，请重试。'
}

export default function ChatPage() {
  const nav = useNavigate()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [deepThinking, setDeepThinking] = useState(false)
  const [attachedFile, setAttachedFile] = useState<AttachedFile | null>(null)
  const [showPathInput, setShowPathInput] = useState(false)
  const [serverPath, setServerPath] = useState('')
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [convId, setConvId] = useState<number | null>(null)
  const [showSidebar, setShowSidebar] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const pathInputRef = useRef<HTMLInputElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const fetchConversations = useCallback(async () => {
    try {
      const res = await client.get('/api/conversations')
      setConversations(res.data.conversations || [])
    } catch {}
  }, [])

  useEffect(() => { fetchConversations() }, [fetchConversations])

  const loadConversation = async (id: number) => {
    try {
      const res = await client.get(`/api/conversations/${id}`)
      const conv = res.data
      setConvId(id)
      const msgs: Message[] = (conv.messages || []).map((m: any) => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
      }))
      setMessages(msgs)
    } catch {
      alert('加载对话失败')
    }
  }

  const createConversation = async () => {
    try {
      const res = await client.post('/api/conversations', { title: '新对话 ' + new Date().toLocaleString('zh-CN') })
      const conv = res.data
      setConversations((prev) => [conv, ...prev])
      setConvId(conv.id)
      setMessages([])
    } catch { alert('创建对话失败') }
  }

  const deleteConversation = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('确定删除此对话？')) return
    try {
      await client.delete(`/api/conversations/${id}`)
      setConversations((prev) => prev.filter((c) => c.id !== id))
      if (convId === id) { setConvId(null); setMessages([]) }
    } catch { alert('删除失败') }
  }

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (!f) return
    const ext = '.' + f.name.split('.').pop()?.toLowerCase()
    if (!CODE_EXTS.includes(ext)) {
      alert('仅支持代码文件和 zip 包：' + CODE_EXTS.join(', '))
      return
    }
    if (f.size > MAX_FILE_SIZE) {
      alert(`文件过大（最大 ${MAX_FILE_SIZE / 1024 / 1024}MB）`)
      return
    }
    setLoading(true)
    try {
      const formData = new FormData()
      formData.append('file', f)
      const token = localStorage.getItem('token') || ''
      const res = await fetch(`${client.defaults.baseURL}/api/chat/upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '上传失败')
      setAttachedFile({ name: data.filename, content: data.path, size: f.size, path: data.path })
    } catch (err: any) {
      alert(err.message || '上传失败')
    } finally {
      setLoading(false)
    }
  }

  const removeFile = () => {
    setAttachedFile(null)
    setServerPath('')
    setShowPathInput(false)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const attachServerPath = () => {
    const p = serverPath.trim()
    if (!p) return
    if (!p.startsWith('/') && !p.startsWith('~') && !p.match(/^[A-Z]:\\/)) { alert('请输入有效的文件路径'); return }
    const name = p.split('/').pop() || p
    setAttachedFile({ name, content: p, size: 0, path: p })
    setShowPathInput(false)
  }

  const send = async () => {
    const q = input.trim()
    if ((!q && !attachedFile) || loading) return

    // Auto-create conversation if needed
    let cid = convId
    if (!cid) {
      try {
        const res = await client.post('/api/conversations', { title: q.substring(0, 30) || '新对话' })
        const conv = res.data
        cid = conv.id
        setConvId(cid)
        setConversations((prev) => [conv, ...prev])
      } catch { alert('创建对话失败'); return }
    }

    let msgContent = q || '请分析以下代码文件中的安全漏洞'
    if (attachedFile) {
      if (attachedFile.size === 0) {
        msgContent = `${msgContent}\n\n用户本地文件路径：${attachedFile.path}（此文件在用户电脑上，不在服务器上。请告诉用户如何将此文件上传或复制到服务器，例如：1）使用页面上的 📎 按钮上传 2）或用 scp 命令复制到服务器。上传成功后用户会告诉你服务器路径，你再进行扫描分析。）`
      } else {
        msgContent = `${msgContent}\n\n已上传文件：${attachedFile.name}\n服务器路径：${attachedFile.path}\n\n（你可以用 scan_project 扫描这个路径，或者直接读取文件内容分析安全问题。）`
      }
    }

    const displayContent = q || (attachedFile?.size === 0
      ? `📂 本地文件路径：${attachedFile?.path}`
      : `📎 已上传文件：${attachedFile?.name}\n服务器路径：${attachedFile?.path}`)

    setInput('')
    setAttachedFile(null)
    if (fileInputRef.current) fileInputRef.current.value = ''

    const userMsg: Message = { role: 'user', content: displayContent, file: attachedFile || undefined }
    setMessages((prev) => [...prev, userMsg])

    // Stream mode
    if (deepThinking) {
      setLoading(true)
      const placeholderIdx = messages.length + 1
      setMessages((prev) => [...prev, { role: 'assistant', content: '', steps: [], reasoning: '' }])

      try {
        const allMessages = [...messages, { role: 'user', content: msgContent }]
        const token = localStorage.getItem('token') || ''
        const url = `${client.defaults.baseURL}/api/chat/agent?conversation_id=${cid}`
        const resp = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
          body: JSON.stringify({ messages: allMessages.map((m) => ({ role: m.role, content: m.content })), deep_thinking: true, stream: true }),
        })

        if (!resp.ok) {
          const text = await resp.text().catch(() => '')
          throw new Error(text || `HTTP ${resp.status}`)
        }
        const reader = resp.body?.getReader()
        if (!reader) throw new Error('no reader')
        const decoder = new TextDecoder()
        let buffer = '', reply = '', reasoning = ''
        let steps: Step[] = []
        let sources: Array<{title:string;url:string;domain:string}> = []

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''
          for (const line of lines) {
            if (!line.startsWith('data: ') || line === 'data: [DONE]') continue
            try {
              const evt = JSON.parse(line.slice(6))
              if (evt.type === 'reasoning') reasoning += evt.text
              else if (evt.type === 'tool_call') steps = [...steps, { type: 'tool_call', desc: evt.desc }]
              else if (evt.type === 'tool_result') steps = [...steps, { type: 'tool_result', desc: evt.desc }]
              else if (evt.type === 'error') throw new Error(evt.message || '服务器内部错误')
              else if (evt.type === 'done') { reply = evt.reply || ''; sources = evt.sources || [] }
              setMessages((prev) => prev.map((m, i) =>
                i === placeholderIdx ? { ...m, content: reply || '思考中...', reasoning, steps, sources } : m
              ))
            } catch {}
          }
        }
        const finalReply = reply || '（无回复）'
        setMessages((prev) => prev.map((m, i) =>
          i === placeholderIdx ? { ...m, content: finalReply, reasoning, steps, sources } : m
        ))
      } catch (error) {
        const errMsg = `请求失败：${getErrorMessage(error)}`
        setMessages((prev) => prev.map((m, i) =>
          i === placeholderIdx ? { ...m, content: errMsg } : m
        ))
      } finally {
        setLoading(false)
      }
    } else {
      // Non-stream mode
      setLoading(true)
      try {
        const allMessages = [...messages, { role: 'user', content: msgContent }]
        const res = await client.post<{ reply: string; sources?: Array<{ title: string; url: string; domain: string }>; steps?: Step[]; reasoning?: string[] }>(
          `/api/chat/agent?conversation_id=${cid}`,
          {
            messages: allMessages.map((m) => ({ role: m.role, content: m.content })),
            deep_thinking: false, stream: false,
          }
        )
        const reply = res.data.reply || '（无回复）'
        setMessages((prev) => [...prev, {
          role: 'assistant', content: reply,
          sources: res.data.sources, steps: res.data.steps,
          reasoning: Array.isArray(res.data.reasoning) ? res.data.reasoning.join('') : (res.data.reasoning || ''),
        }])
      } catch (error) {
        const errMsg = `请求失败：${getErrorMessage(error)}`
        setMessages((prev) => [...prev, { role: 'assistant', content: errMsg }])
      } finally {
        setLoading(false)
      }
    }
  }

  const openLink = (url: string) => { window.open(url, '_blank', 'noopener,noreferrer') }

  return (
    <div className="flex gap-4 h-[calc(100vh-7rem)]">
      {/* Sidebar toggle */}
      <button
        onClick={() => setShowSidebar(!showSidebar)}
        className={`fixed left-0 top-1/2 -translate-y-1/2 z-10 px-1.5 py-3 text-xs font-black uppercase bg-black text-white border-3 border-black transition-all ${showSidebar ? 'left-64' : 'left-0'}`}
      >
        {showSidebar ? '◀' : '▶'}
      </button>

      {/* Conversation sidebar */}
      {showSidebar && (
        <div className="w-64 shrink-0 border-r-3 border-black bg-white flex flex-col overflow-hidden">
          <div className="border-b-3 border-black px-3 py-3 bg-black">
            <h2 className="text-brutal-yellow text-sm font-black uppercase">对话历史</h2>
          </div>
          <div className="p-2 border-b-3 border-black">
            <Button variant="black" size="sm" onClick={createConversation} className="w-full text-xs">
              + 新对话
            </Button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {conversations.length === 0 && (
              <p className="text-xs text-gray-400 text-center py-8">暂无对话记录</p>
            )}
            {conversations.map((c) => (
              <div
                key={c.id}
                onClick={() => loadConversation(c.id)}
                className={`px-3 py-2.5 border-b-2 border-dashed border-gray-200 cursor-pointer transition-colors hover:bg-brutal-cream ${
                  convId === c.id ? 'bg-brutal-yellow border-black border-solid' : ''
                }`}
              >
                <p className="text-xs font-bold truncate">{c.title}</p>
                <div className="flex items-center justify-between mt-0.5">
                  <span className="text-[10px] text-gray-400">
                    {c.updated_at ? new Date(c.updated_at).toLocaleDateString('zh-CN') : ''}
                  </span>
                  <button onClick={(e) => deleteConversation(c.id, e)} className="text-[10px] text-gray-300 hover:text-brutal-red font-black">✕</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="flex items-center gap-4 mb-4">
          <Button variant="yellow" size="sm" onClick={() => nav('/')}>← 返回</Button>
          <h1 className="text-xl font-black uppercase">码医生 AI 对话</h1>
        </header>

        <Card className="flex-1 flex flex-col mb-4 overflow-hidden">
          <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
            {messages.length === 0 && (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-sm text-gray-500 text-center max-w-lg leading-relaxed px-4">
                  <p className="text-base font-black mb-3">🐴 我是<strong>码医生</strong>，你的代码安全分析助手</p>
                  <div className="text-left space-y-1.5">
                    <p>🔍 <strong>代码扫描</strong> — 上传代码文件或指定路径，自动检测漏洞</p>
                    <p>🌐 <strong>联网搜索</strong> — 搜索最新漏洞情报、技术文档、CVE 详情</p>
                    <p>📊 <strong>报告分析</strong> — 解读扫描结果，给出修复建议和攻击场景</p>
                    <p>🛡️ <strong>CVE 情报</strong> — 查 NVD、EPSS 利用概率、CISA KEV 已知被利用</p>
                    <p>📦 <strong>依赖检查</strong> — OSV 查询依赖包是否存在已知漏洞</p>
                    <p>📏 <strong>规则生成</strong> — 根据漏洞描述自动生成 YASA 检测规则</p>
                    <p>📂 <strong>Git 仓库分析</strong> — 克隆仓库、查看提交历史、分析代码变更</p>
                  </div>
                  <p className="mt-4 text-xs text-gray-400">直接输入问题或上传文件开始分析 ↓</p>
                </div>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] border-3 border-black px-3 py-2 text-sm whitespace-pre-wrap leading-relaxed ${
                  m.role === 'user' ? 'bg-brutal-yellow text-black shadow-brutal-sm' : 'bg-white text-black shadow-brutal-sm'
                }`}>
                  <details className="mb-3" open={m.steps && m.steps.length > 0}>
                    <summary className="text-xs font-bold text-gray-400 cursor-pointer hover:text-gray-600 select-none">
                      思考过程（{m.steps ? m.steps.length : 0} 步{m.reasoning && m.reasoning.length > 0 ? ' · 深度思考' : ''}）
                    </summary>
                    <div className="mt-2 flex flex-col gap-1">
                      {m.reasoning && m.reasoning.length > 0 && (
                        <div className="border border-purple-200 bg-purple-50 p-2 mb-1">
                          <p className="text-[10px] font-black uppercase text-purple-400 mb-1">推理过程</p>
                          <pre className="text-[11px] text-gray-600 whitespace-pre-wrap break-words font-sans leading-relaxed">{m.reasoning}</pre>
                        </div>
                      )}
                      {m.steps && m.steps.length > 0 ? m.steps.map((s, j) => (
                        <div key={j} className={`text-[11px] px-2 py-1 border ${
                          s.type === 'tool_call' ? 'border-brutal-cyan bg-cyan-50 text-gray-700' : 'border-gray-200 bg-gray-50 text-gray-500'
                        }`}>
                          {s.type === 'tool_call' ? '🔧' : ' ✓'} {s.desc}
                        </div>
                      )) : (
                        <div className="text-[11px] px-2 py-1 border border-gray-200 bg-gray-50 text-gray-400">
                          直接回答（未使用搜索工具，答案可能基于训练数据）
                        </div>
                      )}
                    </div>
                  </details>

                  {m.file && (
                    <div className="mb-2 flex items-center gap-2 px-2 py-1 border-2 border-brutal-cyan bg-cyan-50 text-xs font-bold">
                      📎 {m.file.name} ({m.file.path ? '已上传至服务器' : (m.file.size / 1024).toFixed(1) + 'KB'})
                    </div>
                  )}

                  {m.content}

                  {m.sources && m.sources.length > 0 && (
                    <div className="mt-3 pt-3 border-t-2 border-dashed border-gray-300">
                      <p className="text-xs font-black uppercase text-gray-400 mb-2">搜索来源</p>
                      <div className="flex flex-col gap-1.5">
                        {m.sources.map((s, j) => (
                          <button key={j} onClick={() => openLink(s.url)}
                            className="flex items-start gap-2 text-left p-2 border-2 border-gray-200 bg-gray-50 hover:bg-brutal-yellow hover:border-black transition-colors cursor-pointer rounded"
                          >
                            <span className="text-xs font-black text-gray-400 min-w-[18px] mt-0.5">{j + 1}.</span>
                            <div className="min-w-0 flex-1">
                              <p className="text-xs font-bold truncate">{s.title}</p>
                              <p className="text-[10px] text-gray-400 truncate">{s.domain}</p>
                            </div>
                            <span className="text-[10px] text-gray-300 shrink-0 mt-0.5">↗</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="border-3 border-black bg-white px-4 py-2 text-sm font-black animate-pulse">思考中...</div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input area */}
          <div className="border-t-3 border-black">
            {attachedFile && (
              <div className="flex items-center gap-2 px-4 py-2 bg-cyan-50 border-b-2 border-dashed border-black">
                <span className="text-xs font-black">{attachedFile.size === 0 ? '📂' : '📎'} {attachedFile.name}</span>
                <span className="text-[10px] text-gray-400">{attachedFile.size === 0 ? '本地路径' : '已上传'}</span>
                <button onClick={removeFile} className="ml-auto text-xs font-black text-brutal-red hover:underline">✕ 移除</button>
              </div>
            )}
            {showPathInput && (
              <div className="flex items-center gap-2 px-4 py-2 bg-purple-50 border-b-2 border-dashed border-black">
                <input ref={pathInputRef} type="text" placeholder="输入你电脑上的文件路径，如 ~/project/main.py..."
                  value={serverPath} onChange={(e) => setServerPath(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') attachServerPath() }}
                  className="flex-1 px-3 py-1.5 text-xs font-medium outline-none bg-white border-2 border-black" autoFocus
                />
                <button onClick={attachServerPath} className="px-3 py-1.5 text-xs font-black uppercase bg-brutal-purple text-white hover:opacity-90">确认</button>
                <button onClick={() => { setShowPathInput(false); setServerPath(''); }} className="text-xs text-gray-400 hover:text-black font-black">✕</button>
              </div>
            )}
            <div className="flex">
              <button onClick={() => setDeepThinking(!deepThinking)} disabled={loading}
                className={`px-3 py-3 text-sm font-black uppercase border-r-3 border-black transition-colors disabled:opacity-50 ${
                  deepThinking ? 'bg-brutal-purple text-white' : 'bg-white hover:bg-brutal-gray'
                }`} title={deepThinking ? '深度思考已开启' : '深度思考已关闭'}
              >
                {deepThinking ? '🧠' : '💤'}
              </button>
              <input ref={fileInputRef} type="file" onChange={handleFileSelect} className="hidden" accept={CODE_EXTS.join(',')} />
              <button onClick={() => fileInputRef.current?.click()} disabled={loading}
                className="px-3 py-3 text-sm font-black uppercase bg-white hover:bg-brutal-yellow border-r-3 border-black transition-colors disabled:opacity-50" title="上传代码文件"
              >📎</button>
              <button onClick={() => { setShowPathInput(!showPathInput); setServerPath(''); }} disabled={loading}
                className={`px-3 py-3 text-sm font-black uppercase border-r-3 border-black transition-colors disabled:opacity-50 ${
                  showPathInput ? 'bg-brutal-purple text-white' : 'bg-white hover:bg-brutal-gray'
                }`} title="指定本地文件路径"
              >📂</button>
              <input type="text" placeholder={attachedFile ? '输入问题（可选）...' : '问码医生，或上传代码文件...'}
                value={input} onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') send() }} disabled={loading}
                className="flex-1 px-4 py-3 text-sm font-medium outline-none bg-white"
              />
              <Button variant="black" size="md" onClick={send} disabled={loading || (!input.trim() && !attachedFile)}>
                发送
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}
