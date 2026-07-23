import { useEffect, useRef, useState } from 'react'
import { useStore } from '../store'
import { streamPost } from '../api/client'
import type { ChatMsg, SseEvent } from '../types'

function download(name: string, text: string) {
  const blob = new Blob([text], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

function parseContent(content: string) {
  const parts: { type: 'text' | 'code'; lang?: string; text: string }[] = []
  const re = /```(\w*)\r?\n?([\s\S]*?)```/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(content))) {
    if (m.index > last) parts.push({ type: 'text', text: content.slice(last, m.index) })
    parts.push({ type: 'code', lang: m[1] || '', text: m[2] })
    last = re.lastIndex
  }
  if (last < content.length) parts.push({ type: 'text', text: content.slice(last) })
  return parts
}

function MessageContent({ content }: { content: string }) {
  return (
    <>
      {parseContent(content).map((p, i) => {
        if (p.type === 'text') return <span key={i}>{p.text}</span>
        const isGjf = (p.lang || '').toLowerCase().includes('gjf') || p.lang === 'g09'
        return (
          <pre key={i} className="code-block">
            <div className="code-head">
              <span className="muted" style={{ color: '#94a3b8' }}>{p.lang || 'code'}</span>
              <div className="spacer" />
              <button className="ghost sm" style={{ color: '#e2e8f0' }} onClick={() => navigator.clipboard?.writeText(p.text)}>复制</button>
              {isGjf && <button className="sm" onClick={() => download('job.gjf', p.text)}>下载 .gjf</button>}
            </div>
            <code>{p.text}</code>
          </pre>
        )
      })}
    </>
  )
}

export function ChatView() {
  const chat = useStore((s) => s.chat)
  const addChat = useStore((s) => s.addChat)
  const appendChat = useStore((s) => s.appendChat)
  const setChatStreaming = useStore((s) => s.setChatStreaming)
  const streaming = useStore((s) => s.chatStreaming)
  const settings = useStore((s) => s.settings)
  const clearChat = useStore((s) => s.clearChat)
  const setCurrentMolecule = useStore((s) => s.setCurrentMolecule)
  const refreshMolecules = useStore((s) => s.refreshMolecules)
  const [input, setInput] = useState('')
  const [atBottom, setAtBottom] = useState(true)
  const [webSearch, setWebSearch] = useState(false)
  const bodyRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (atBottom) bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight })
  }, [chat, atBottom])

  const onScroll = () => {
    const el = bodyRef.current
    if (!el) return
    setAtBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 60)
  }

  const send = async () => {
    const text = input.trim()
    if (!text || streaming) return
    const history = chat.filter((m) => m.content)
    addChat({ role: 'user', content: text })
    setInput('')
    addChat({ role: 'assistant', content: '' })
    setChatStreaming(true)
    setAtBottom(true)
    try {
      const msgs: ChatMsg[] = [...history, { role: 'user', content: text }]
      const stream = streamPost('/chat', {
        messages: msgs.map((m) => ({ role: m.role, content: m.content })),
        provider_id:
          settings?.active_provider_id && settings.active_provider_id !== 'mock'
            ? settings.active_provider_id
            : undefined,
        model: settings?.active_model || undefined,
        web_search: webSearch,
      })
      for await (const raw of stream) {
        const evt = JSON.parse(raw) as SseEvent
        if (evt.type === 'delta' && evt.content) appendChat(evt.content)
        else if (evt.type === 'molecule' && evt.molecule) {
          setCurrentMolecule(evt.molecule)
          refreshMolecules()
          useStore.getState().setActiveView('modeling')
        } else if (evt.type === 'search' && evt.query) {
          appendChat(`\n🔍 联网搜索「${evt.query}」- ${evt.count} 条结果\n`)
        } else if (evt.type === 'error') appendChat(`\n[错误] ${evt.message}`)
      }
    } catch (e) {
      appendChat(`\n[请求失败] ${String(e)}`)
    } finally {
      setChatStreaming(false)
    }
  }

  return (
    <div className="card" style={{ height: '100%' }}>
      <div className="card-head">
        <span>AI 对话</span>
        <div className="spacer" />
        <button className="ghost sm" onClick={clearChat}>清空</button>
      </div>
      <div className="card-body chat-body" ref={bodyRef} onScroll={onScroll}>
        <div className="chat-stream">
          {chat.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              <MessageContent content={m.content} />
              {streaming && i === chat.length - 1 && m.role === 'assistant' && (
                <span className="cursor">▋</span>
              )}
            </div>
          ))}
        </div>
        {!atBottom && (
          <button className="scroll-latest" onClick={() => { bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight, behavior: 'smooth' }); setAtBottom(true) }}>
            ↓ 最新
          </button>
        )}
      </div>
      <div className="chat-input">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="描述计算需求或分子名称…(Enter 发送,Shift+Enter 换行)"
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
        />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'flex-end' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: 'var(--text-dim)', cursor: 'pointer', userSelect: 'none' }}>
            <input type="checkbox" checked={webSearch} onChange={(e) => setWebSearch(e.target.checked)} style={{ width: 14, height: 14 }} />
            🔍 联网搜索
          </label>
          <button className="primary" onClick={send} disabled={streaming}>
            {streaming ? '生成中…' : '发送'}
          </button>
        </div>
      </div>
    </div>
  )
}
