import { deleteDocument } from '../services/api'
import UploadBox from './UploadBox'

export default function Sidebar({
  documents,
  sessions,
  activeSessionId,
  streaming,
  onUploaded,
  onDeletedDocument,
  onNewChat,
  onSelectChat,
  onDeleteChat,
}) {
  async function handleDeleteDoc(docId) {
    if (!confirm('Delete this document and its embeddings?')) return
    try {
      await deleteDocument(docId)
      onDeletedDocument?.(docId)
    } catch (e) {
      alert(e.message)
    }
  }

  return (
    <aside className="w-72 bg-slate-50 border-r border-slate-200 flex flex-col overflow-hidden">
      <div className="p-4 pb-2">
        <h1 className="text-lg font-semibold text-slate-800">RAG Chatbot</h1>
        <p className="text-xs text-slate-500 mt-0.5">
          Ask questions about your documents
        </p>
      </div>

      {/* --- New chat button --- */}
      <div className="px-4 pb-3">
        <button
          onClick={onNewChat}
          disabled={streaming}
          className="w-full px-3 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          + New Chat
        </button>
      </div>

      {/* --- Chats list --- */}
      <div className="px-4 pb-3 flex flex-col min-h-0 flex-1">
        <div className="text-xs font-medium uppercase tracking-wide text-slate-500 mb-2">
          Chats ({sessions.length})
        </div>
        <div className="flex-1 overflow-y-auto -mx-1 px-1 space-y-1">
          {sessions.length === 0 ? (
            <div className="text-xs text-slate-400 italic">No chats yet</div>
          ) : (
            sessions.map((s) => {
              const isActive = s.session_id === activeSessionId
              return (
                <div
                  key={s.session_id}
                  onClick={() => onSelectChat(s.session_id)}
                  className={
                    'group flex items-center gap-2 px-2 py-2 rounded cursor-pointer text-sm border ' +
                    (isActive
                      ? 'bg-blue-100 border-blue-300 text-slate-900'
                      : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-100') +
                    (streaming ? ' opacity-60 pointer-events-none' : '')
                  }
                  title={s.title}
                >
                  <div className="flex-1 min-w-0 truncate">{s.title}</div>
                  <span className="text-[10px] text-slate-400 shrink-0">
                    {s.message_count}
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      onDeleteChat(s.session_id)
                    }}
                    className="text-slate-400 hover:text-red-500 text-base leading-none opacity-0 group-hover:opacity-100"
                    title="Delete chat"
                    aria-label="Delete chat"
                  >
                    ×
                  </button>
                </div>
              )
            })
          )}
        </div>
      </div>

      {/* --- Documents section --- */}
      <div className="border-t border-slate-200 p-4 space-y-3 max-h-[40%] flex flex-col min-h-0">
        <UploadBox onUploaded={onUploaded} />

        <div className="flex-1 min-h-0 flex flex-col">
          <div className="text-xs font-medium uppercase tracking-wide text-slate-500 mb-2">
            Documents ({documents.length})
          </div>
          <div className="flex-1 overflow-y-auto space-y-1">
            {documents.length === 0 ? (
              <div className="text-xs text-slate-400 italic">No documents yet</div>
            ) : (
              documents.map((d) => (
                <div
                  key={d.document_id}
                  className="flex items-center gap-2 px-2 py-1.5 rounded bg-white border border-slate-200 text-sm"
                >
                  <div className="flex-1 min-w-0 truncate" title={d.filename}>
                    {d.filename}
                  </div>
                  <span className="text-[10px] text-slate-400">{d.num_chunks}</span>
                  <button
                    onClick={() => handleDeleteDoc(d.document_id)}
                    className="text-slate-400 hover:text-red-500 text-base leading-none"
                    title="Delete document"
                    aria-label="Delete document"
                  >
                    ×
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </aside>
  )
}
