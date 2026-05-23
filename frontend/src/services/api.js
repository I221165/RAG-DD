// In dev, `VITE_API_BASE` is unset and we use relative paths (Vite proxy
// in vite.config.js forwards them to FastAPI on :8000).
// In prod, set VITE_API_BASE to the backend URL, e.g.
//   VITE_API_BASE=https://rag-backend.up.railway.app
const API_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '')
const url = (path) => `${API_BASE}${path}`

async function _failPayload(res) {
  try {
    const body = await res.json()
    return body.detail || res.statusText
  } catch {
    return res.statusText
  }
}

/**
 * Upload a document to a chat session.
 * If `sessionId` is null/undefined, the backend creates a new session
 * and returns its id in `response.session_id`.
 */
export async function uploadFile(file, sessionId) {
  const fd = new FormData()
  fd.append('file', file)
  if (sessionId) fd.append('session_id', sessionId)
  const res = await fetch(url('/upload'), { method: 'POST', body: fd })
  if (!res.ok) throw new Error(await _failPayload(res))
  return res.json()
}

export async function listSessionDocuments(sessionId) {
  const res = await fetch(url(`/sessions/${sessionId}/documents`))
  if (!res.ok) throw new Error(await _failPayload(res))
  return res.json()
}

export async function deleteSessionDocument(sessionId, documentId) {
  const res = await fetch(
    url(`/sessions/${sessionId}/documents/${documentId}`),
    { method: 'DELETE' },
  )
  if (!res.ok) throw new Error(await _failPayload(res))
  return res.json()
}

export async function listSessions() {
  const res = await fetch(url('/sessions'))
  if (!res.ok) throw new Error(await _failPayload(res))
  return res.json()
}

export async function getHistory(sessionId) {
  const res = await fetch(url(`/history/${sessionId}`))
  if (!res.ok) throw new Error(await _failPayload(res))
  return res.json()
}

export async function clearSession(sessionId) {
  const res = await fetch(url(`/session/${sessionId}`), { method: 'DELETE' })
  if (!res.ok) throw new Error(await _failPayload(res))
  return res.json()
}

/**
 * Send a chat message and stream events back.
 *
 * The server returns NDJSON (one JSON object per line). This calls
 * `onEvent({type, content})` for each event.
 *
 * Event types:
 *   - "session"  -> content is the assigned session_id (new sessions only)
 *   - "token"    -> content is a text fragment
 *   - "sources"  -> content is an array of {filename, document_id, chunk_index, snippet}
 *   - "done"     -> end of stream
 *   - "error"    -> content is a human-readable error
 */
export async function sendMessage(message, sessionId, onEvent) {
  const res = await fetch(url('/chat'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId ?? null }),
  })
  if (!res.ok) throw new Error(await _failPayload(res))

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let nl
    while ((nl = buffer.indexOf('\n')) !== -1) {
      const line = buffer.slice(0, nl).trim()
      buffer = buffer.slice(nl + 1)
      if (!line) continue
      try {
        onEvent(JSON.parse(line))
      } catch {
        console.warn('Could not parse stream line:', line)
      }
    }
  }
  const tail = buffer.trim()
  if (tail) {
    try { onEvent(JSON.parse(tail)) } catch { /* ignore trailing garbage */ }
  }
}
