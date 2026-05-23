import { useEffect, useState } from 'react'
import Sidebar from './components/Sidebar'
import ChatBox from './components/ChatBox'
import {
  clearSession,
  getHistory,
  listDocuments,
  listSessions,
} from './services/api'

export default function App() {
  const [documents, setDocuments] = useState([])
  const [sessions, setSessions] = useState([])
  const [activeSessionId, setActiveSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [streaming, setStreaming] = useState(false)

  async function refreshDocuments() {
    try { setDocuments(await listDocuments()) } catch (e) { console.error(e) }
  }
  async function refreshSessions() {
    try { setSessions(await listSessions()) } catch (e) { console.error(e) }
  }

  useEffect(() => {
    refreshDocuments()
    refreshSessions()
  }, [])

  function handleNewChat() {
    if (streaming) return
    setActiveSessionId(null)
    setMessages([])
  }

  async function handleSelectChat(id) {
    if (streaming || id === activeSessionId) return
    try {
      const { messages: msgs } = await getHistory(id)
      setActiveSessionId(id)
      setMessages(
        msgs.map((m) => ({
          role: m.role,
          content: m.content,
          sources: m.sources || [],
          streaming: false,
        })),
      )
    } catch (e) {
      alert(e.message)
    }
  }

  async function handleDeleteChat(id) {
    if (streaming) return
    if (!confirm('Delete this chat?')) return
    try {
      await clearSession(id)
      if (id === activeSessionId) {
        setActiveSessionId(null)
        setMessages([])
      }
      refreshSessions()
    } catch (e) {
      alert(e.message)
    }
  }

  return (
    <div className="h-screen flex bg-slate-100 text-slate-900">
      <Sidebar
        documents={documents}
        sessions={sessions}
        activeSessionId={activeSessionId}
        streaming={streaming}
        onUploaded={refreshDocuments}
        onDeletedDocument={refreshDocuments}
        onNewChat={handleNewChat}
        onSelectChat={handleSelectChat}
        onDeleteChat={handleDeleteChat}
      />
      <ChatBox
        sessionId={activeSessionId}
        setSessionId={setActiveSessionId}
        messages={messages}
        setMessages={setMessages}
        streaming={streaming}
        setStreaming={setStreaming}
        onTurnComplete={refreshSessions}
      />
    </div>
  )
}
