import { deleteDocument } from '../services/api'
import UploadBox from './UploadBox'

export default function Sidebar({ documents, onUploaded, onDeleted, onClearChat }) {
  async function handleDelete(docId) {
    if (!confirm('Delete this document and its embeddings?')) return
    try {
      await deleteDocument(docId)
      onDeleted?.(docId)
    } catch (e) {
      alert(e.message)
    }
  }

  return (
    <aside className="w-72 bg-slate-50 border-r border-slate-200 p-4 flex flex-col gap-4 overflow-hidden">
      <div>
        <h1 className="text-lg font-semibold text-slate-800">RAG Chatbot</h1>
        <p className="text-xs text-slate-500 mt-0.5">
          Ask questions about your documents
        </p>
      </div>

      <UploadBox onUploaded={onUploaded} />

      <div className="flex-1 min-h-0 flex flex-col">
        <div className="text-xs font-medium uppercase tracking-wide text-slate-500 mb-2">
          Documents ({documents.length})
        </div>
        <div className="flex-1 overflow-y-auto space-y-1">
          {documents.length === 0 ? (
            <div className="text-xs text-slate-400 italic">No documents yet</div>
          ) : (
            documents.map(d => (
              <div
                key={d.document_id}
                className="flex items-center gap-2 px-2 py-1.5 rounded bg-white border border-slate-200 text-sm"
              >
                <div className="flex-1 min-w-0 truncate" title={d.filename}>
                  {d.filename}
                </div>
                <span className="text-[10px] text-slate-400">{d.num_chunks}</span>
                <button
                  onClick={() => handleDelete(d.document_id)}
                  className="text-slate-400 hover:text-red-500 text-base leading-none"
                  title="Delete"
                  aria-label="Delete document"
                >
                  ×
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      <button
        onClick={onClearChat}
        className="text-xs text-slate-500 hover:text-slate-800 underline self-start"
      >
        Clear current chat
      </button>
    </aside>
  )
}
