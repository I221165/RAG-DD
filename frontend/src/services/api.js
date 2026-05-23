// All endpoints are proxied through Vite to FastAPI on :8000 during dev
// (see vite.config.js). In production, both are served from the same origin.

async function _failPayload(res) {
  try {
    const body = await res.json()
    return body.detail || res.statusText
  } catch {
    return res.statusText
  }
}

export async function uploadFile(file) {
  const fd = new FormData()
  fd.append('file', file)
  const res = await fetch('/upload', { method: 'POST', body: fd })
  if (!res.ok) throw new Error(await _failPayload(res))
  return res.json()
}

export async function listDocuments() {
  const res = await fetch('/documents')
  if (!res.ok) throw new Error(await _failPayload(res))
  return res.json()
}

export async function deleteDocument(documentId) {
  const res = await fetch(`/documents/${documentId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(await _failPayload(res))
  return res.json()
}

export async function getHistory(sessionId) {
  const res = await fetch(`/history/${sessionId}`)
  if (!res.ok) throw new Error(await _failPayload(res))
  return res.json()
}

export async function clearSession(sessionId) {
  const res = await fetch(`/session/${sessionId}`, { method: 'DELETE' })
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
  const res = await fetch('/chat', {
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
