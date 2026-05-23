import { useEffect, useState } from 'react'
import Sidebar from './components/Sidebar'
import ChatBox from './components/ChatBox'
import { listDocuments, clearSession } from './services/api'

export default function App() {
  const [documents, setDocuments] = useState([])
  const [sessionId, setSessionId] = useState(null)
  const [messages, setMessages] = useState([])

  async function refreshDocuments() {
    try {
      setDocuments(await listDocuments())
    } catch (e) {
      console.error('Failed to load documents', e)
    }
  }

  useEffect(() => { refreshDocuments() }, [])

  async function handleClearChat() {
    if (sessionId) {
      try { await clearSession(sessionId) } catch { /* best-effort */ }
    }
    setSessionId(null)
    setMessages([])
  }

  return (
    <div className="h-screen flex bg-slate-100 text-slate-900">
      <Sidebar
        documents={documents}
        onUploaded={refreshDocuments}
        onDeleted={refreshDocuments}
        onClearChat={handleClearChat}
      />
      <ChatBox
        sessionId={sessionId}
        setSessionId={setSessionId}
        messages={messages}
        setMessages={setMessages}
      />
    </div>
  )
}
