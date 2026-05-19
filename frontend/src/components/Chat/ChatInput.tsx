import React, { useRef, useState } from 'react'
import { Send, Loader } from 'lucide-react'

interface Props {
  onSend: (message: string) => void
  isLoading: boolean
  placeholder?: string
  value?: string
  onChange?: (val: string) => void
}

export const ChatInput: React.FC<Props> = ({ onSend, isLoading, placeholder, value, onChange }) => {
  const [internalInput, setInternalInput] = useState('')
  const input = value !== undefined ? value : internalInput
  const setInput = onChange ? onChange : setInternalInput

  const textRef = useRef<HTMLTextAreaElement>(null)

  const handleSend = () => {
    const trimmed = input.trim()
    if (!trimmed || isLoading) return
    onSend(trimmed)
    setInput('')
    setTimeout(() => textRef.current?.focus(), 50)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex flex-col gap-3">
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
