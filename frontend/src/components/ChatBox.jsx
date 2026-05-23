import { useEffect, useRef, useState } from 'react'
import { sendMessage } from '../services/api'
import MessageBubble from './MessageBubble'

export default function ChatBox({
  sessionId,
  setSessionId,
  messages,
  setMessages,
  streaming,
  setStreaming,
  onTurnComplete,
}) {
  const [input, setInput] = useState('')
  const scrollRef = useRef(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: 'smooth',
    })
  }, [messages])

  async function handleSend() {
    const text = input.trim()
    if (!text || streaming) return
    setInput('')

    setMessages((prev) => [
      ...prev,
      { role: 'user', content: text },
      { role: 'assistant', content: '', sources: [], streaming: true },
    ])
    setStreaming(true)

    const patchLast = (patch) => {
      setMessages((prev) => {
        const next = [...prev]
        const last = next[next.length - 1]
        next[next.length - 1] = { ...last, ...patch(last) }
        return next
      })
    }

    try {
      await sendMessage(text, sessionId, (ev) => {
        if (ev.type === 'session') {
          setSessionId(ev.content)
        } else if (ev.type === 'token') {
          patchLast((last) => ({ content: last.content + ev.content }))
        } else if (ev.type === 'sources') {
          patchLast(() => ({ sources: ev.content }))
        } else if (ev.type === 'done') {
          patchLast(() => ({ streaming: false }))
        } else if (ev.type === 'error') {
          patchLast(() => ({
            content: `_Error: ${ev.content}_`,
            streaming: false,
          }))
        }
      })
    } catch (e) {
      patchLast(() => ({
        content: `_Error: ${e.message}_`,
        streaming: false,
      }))
    } finally {
      setStreaming(false)
      onTurnComplete?.()
    }
  }

  return (
    <div className="flex-1 flex flex-col bg-slate-100 min-w-0">
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 ? (
          <div className="h-full flex items-center justify-center text-slate-400 text-sm">
            Upload a document, then ask a question.
          </div>
        ) : (
          messages.map((m, i) => <MessageBubble key={i} {...m} />)
        )}
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); handleSend() }}
        className="border-t border-slate-200 bg-white p-4 flex gap-2"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={streaming}
          placeholder="Ask about your documents…"
          className="flex-1 px-4 py-2 rounded-lg border border-slate-300 focus:outline-none focus:border-blue-500 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={streaming || !input.trim()}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Send
        </button>
      </form>
    </div>
  )
}
