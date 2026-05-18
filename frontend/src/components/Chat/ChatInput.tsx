import React, { useRef, useState } from 'react'
import { Send, Paperclip, Loader } from 'lucide-react'

interface Props {
  onSend: (message: string) => void
  onUpload: (file: File) => void
  isLoading: boolean
  placeholder?: string
}

const QUICK_QUESTIONS = [
  "Total revenue by platform as pie chart",
  "Top 10 SKUs by units ordered",
  "Monthly revenue trend for Nykaa Beauty",
  "Skincare vs Makeup revenue by month",
  "Which SKUs have low inventory?",
  "Show Shopify orders trend in 2025",
]

export const ChatInput: React.FC<Props> = ({ onSend, onUpload, isLoading, placeholder }) => {
  const [input, setInput] = useState('')
  const [showQuick, setShowQuick] = useState(true)
  const fileRef = useRef<HTMLInputElement>(null)
  const textRef = useRef<HTMLTextAreaElement>(null)

  const handleSend = () => {
    const trimmed = input.trim()
    if (!trimmed || isLoading) return
    onSend(trimmed)
    setInput('')
    setShowQuick(false)
    setTimeout(() => textRef.current?.focus(), 50)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      onUpload(file)
      e.target.value = ''
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Quick question chips */}
      {showQuick && (
        <div className="flex flex-wrap gap-2 px-4">
          {QUICK_QUESTIONS.map((q) => (
            <button
              key={q}
              onClick={() => { onSend(q); setShowQuick(false) }}
              className="text-xs bg-slate-100 hover:bg-blue-50 hover:text-blue-700 border border-slate-200 hover:border-blue-300 rounded-full px-3 py-1.5 text-slate-600 transition"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Input bar */}
      <div className="flex items-end gap-2 px-4 pb-4">
        <div className="flex-1 flex items-end bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100 transition">
          <textarea
            ref={textRef}
            value={input}
            onChange={(e) => {
              setInput(e.target.value)
              e.target.style.height = 'auto'
              e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
            }}
            onKeyDown={handleKeyDown}
            placeholder={placeholder || "Ask anything about your data... (e.g. 'Show sales trend by region')"}
            rows={1}
            className="flex-1 px-4 py-3 text-sm bg-transparent outline-none resize-none max-h-32 text-slate-700 placeholder-slate-400"
          />
          <button
            onClick={() => fileRef.current?.click()}
            className="p-3 text-slate-400 hover:text-blue-500 transition"
            title="Upload CSV or Excel"
          >
            <Paperclip size={18} />
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,.xlsx,.xls"
            onChange={handleFileChange}
            className="hidden"
          />
        </div>

        <button
          onClick={handleSend}
          disabled={!input.trim() || isLoading}
          className="w-11 h-11 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-200 disabled:cursor-not-allowed rounded-xl flex items-center justify-center text-white transition shadow-sm"
        >
          {isLoading ? <Loader size={18} className="animate-spin" /> : <Send size={18} />}
        </button>
      </div>
    </div>
  )
}
