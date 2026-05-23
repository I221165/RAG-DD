import { useEffect, useState } from 'react'
import Sidebar from './components/Sidebar'
import ChatBox from './components/ChatBox'
import {
  clearSession,
  getHistory,
  listSessionDocuments,
  listSessions,
} from './services/api'

export default function App() {
  const [sessions, setSessions] = useState([])
  const [activeSessionId, setActiveSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [documents, setDocuments] = useState([])
  const [streaming, setStreaming] = useState(false)

  async function refreshSessions() {
    try { setSessions(await listSessions()) } catch (e) { console.error(e) }
  }

  async function refreshDocuments(sid = activeSessionId) {
    if (!sid) { setDocuments([]); return }
    try { setDocuments(await listSessionDocuments(sid)) }
    catch (e) { console.error(e); setDocuments([]) }
  }

  // initial load: only the sessions list (docs come once a chat is selected)
  useEffect(() => { refreshSessions() }, [])

  // when chat switches, reload its documents
  useEffect(() => { refreshDocuments(activeSessionId) }, [activeSessionId])

  function handleNewChat() {
    if (streaming) return
    setActiveSessionId(null)
    setMessages([])
    setDocuments([])
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
        setDocuments([])
      }
      refreshSessions()
    } catch (e) {
      alert(e.message)
    }
  }

  // Called by UploadBox after a successful upload. Backend returns the
  // session_id used (creating one if we had none). Adopt it as the active
  // chat so the rest of the UI lines up.
  async function handleUploaded(result) {
    if (!activeSessionId && result.session_id) {
      setActiveSessionId(result.session_id)
      refreshSessions()
      // documents will refresh via the activeSessionId useEffect
    } else {
      refreshDocuments(activeSessionId)
    }
  }

  return (
    <div className="h-screen flex bg-slate-100 text-slate-900">
      <Sidebar
        documents={documents}
        sessions={sessions}
        activeSessionId={activeSessionId}
        streaming={streaming}
        onUploaded={handleUploaded}
        onDeletedDocument={() => refreshDocuments(activeSessionId)}
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
