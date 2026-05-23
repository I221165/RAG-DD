import { useRef, useState } from 'react'
import { uploadFile } from '../services/api'

export default function UploadBox({ onUploaded }) {
  const inputRef = useRef(null)
  const [dragOver, setDragOver] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function handleFiles(files) {
    setError('')
    setBusy(true)
    try {
      for (const file of files) {
        const result = await uploadFile(file)
        onUploaded?.(result)
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  return (
    <div className="space-y-2">
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          if (e.dataTransfer.files?.length) handleFiles(e.dataTransfer.files)
        }}
        onClick={() => inputRef.current?.click()}
        className={
          'rounded-lg border-2 border-dashed p-4 text-center cursor-pointer text-sm transition-colors ' +
          (dragOver ? 'border-blue-500 bg-blue-50 ' : 'border-slate-300 bg-white ') +
          (busy ? 'opacity-60 pointer-events-none' : 'hover:border-slate-400')
        }
      >
        {busy ? 'Uploading…' : (
          <>
            <div className="font-medium text-slate-700">Drop a file here</div>
            <div className="text-xs text-slate-500 mt-1">or click to choose</div>
            <div className="text-xs text-slate-400 mt-2">PDF · DOCX · TXT</div>
          </>
        )}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx,.txt"
        multiple
        className="hidden"
        onChange={(e) => e.target.files && handleFiles(e.target.files)}
      />
      {error && <div className="text-xs text-red-600 break-words">{error}</div>}
    </div>
  )
}
