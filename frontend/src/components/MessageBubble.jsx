import Markdown from 'react-markdown'

export default function MessageBubble({ role, content, sources, streaming }) {
  const isUser = role === 'user'
  const displayContent = content || (streaming ? '…' : '')

  return (
    <div className={'flex ' + (isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={
          'max-w-2xl rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap ' +
          (isUser
            ? 'bg-blue-600 text-white'
            : 'bg-white text-slate-800 border border-slate-200')
        }
      >
        {isUser ? displayContent : <Markdown>{displayContent}</Markdown>}

        {!isUser && sources && sources.length > 0 && (
          <div className="mt-3 pt-2 border-t border-slate-100">
            <div className="text-[10px] uppercase tracking-wide text-slate-400 mb-1">
              Sources
            </div>
            <div className="space-y-1">
              {sources.map((s, i) => (
                <details key={i} className="text-xs text-slate-600">
                  <summary className="cursor-pointer hover:text-slate-800">
                    {s.filename}{' '}
                    <span className="text-slate-400">· chunk {s.chunk_index}</span>
                  </summary>
                  <div className="mt-1 pl-3 text-[11px] text-slate-500 border-l-2 border-slate-200">
                    {s.snippet}
                  </div>
                </details>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
