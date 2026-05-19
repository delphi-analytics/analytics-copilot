import React, { useState } from 'react'
import { ChevronDown, ChevronUp, Code, Lightbulb, Clock, Edit2, Trash2 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { ChartRenderer } from '../Charts/ChartRenderer'
import { indianiseCurrencyText, autoFormatValue } from '../../lib/formatters'
import type { ChatMessage as ChatMessageType } from '../../store/chat'

interface Props {
  message: ChatMessageType
  onFollowUp: (question: string) => void
  onEdit?: (messageId: string, content: string) => void
  onDelete?: (messageId: string) => void
}

export const ChatMessageComponent: React.FC<Props> = ({ message, onFollowUp, onEdit, onDelete }) => {
  const [showSQL, setShowSQL] = useState(false)

  if (message.role === 'user') {
    return (
      <div className="flex justify-end mb-4 group relative">
        <div className="flex items-center gap-2 mr-2 opacity-60 hover:opacity-100 transition-opacity">
          {onEdit && (
            <button
              onClick={() => onEdit(message.id, message.content)}
              className="p-1.5 text-slate-400 hover:text-blue-500 bg-white rounded-lg shadow-sm border border-slate-200 transition"
              title="Edit question"
            >
              <Edit2 size={14} />
            </button>
          )}
          {onDelete && (
            <button
              onClick={() => onDelete(message.id)}
              className="p-1.5 text-slate-400 hover:text-red-500 bg-white rounded-lg shadow-sm border border-slate-200 transition"
              title="Delete question"
            >
              <Trash2 size={14} />
            </button>
          )}
        </div>
        <div className="max-w-2xl bg-blue-600 text-white rounded-2xl rounded-tr-sm px-5 py-3 shadow-sm">
          <p className="text-sm leading-relaxed">{message.content}</p>
        </div>
      </div>
    )
  }

  // Convert any $-denominated text to ₹
  const displayText = message.content ? indianiseCurrencyText(message.content) : ''

  return (
    <div className="flex flex-col gap-3 mb-6">
      {/* Agent badge */}
      <div className="flex items-center gap-2 text-xs text-slate-500">
        <div className="w-6 h-6 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white text-xs font-bold">
          AI
        </div>
        <span>Limese Copilot</span>
        {message.latency_ms && (
          <span className="flex items-center gap-1 text-slate-400">
            <Clock size={11} /> {(message.latency_ms / 1000).toFixed(1)}s
          </span>
        )}
        {message.row_count !== undefined && message.row_count > 0 && (
          <span className="bg-blue-100 text-blue-600 rounded-full px-2 py-0.5 text-xs">
            {message.row_count.toLocaleString('en-IN')} rows
          </span>
        )}
      </div>

      {/* Error state — friendly messages for known errors */}
      {message.error && (
        <div className={`rounded-xl px-4 py-3 text-sm border ${
          message.error.toLowerCase().includes('daily ai query limit') ||
          message.error.toLowerCase().includes('rate_limit') ||
          message.error.toLowerCase().includes('ratelimit') ||
          message.error.toLowerCase().includes('rate limit')
            ? 'bg-amber-50 border-amber-200 text-amber-800'
            : 'bg-red-50 border-red-200 text-red-700'
        }`}>
          {message.error.toLowerCase().includes('daily ai query limit') ||
          message.error.toLowerCase().includes('rate_limit') ||
          message.error.toLowerCase().includes('ratelimit') ||
          message.error.toLowerCase().includes('rate limit') ? (
            <div className="space-y-2">
              <p className="font-semibold">⏳ Daily AI limit reached</p>
              <p className="text-xs">Groq free tier: 100K tokens/day used. Options:</p>
              <ul className="text-xs list-disc list-inside space-y-1">
                <li><strong>Free fix:</strong> Add <code className="bg-amber-100 px-1 rounded">GEMINI_API_KEY</code> to .env → restart (aistudio.google.com)</li>
                <li><strong>Wait:</strong> Resets at midnight UTC (~40 min)</li>
                <li><strong>Upgrade:</strong> console.groq.com/settings/billing ($9/mo for 100M tokens)</li>
              </ul>
            </div>
          ) : (
            <span>⚠️ {message.error}</span>
          )}
        </div>
      )}

      {/* Main text — $→₹ converted */}
      {displayText && !message.error && (
        <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-sm px-5 py-4 shadow-sm">
          <div className="text-sm text-slate-700 leading-relaxed prose prose-sm max-w-none">
            <ReactMarkdown>{displayText}</ReactMarkdown>
          </div>
        </div>
      )}

      {/* Key Metrics pills — formatted as ₹ */}
      {message.key_metrics && Object.keys(message.key_metrics).length > 0 && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(message.key_metrics).slice(0, 6).map(([k, v]) => {
            const formatted = autoFormatValue(k, v)
            return (
              <div key={k} className="bg-blue-50 border border-blue-200 rounded-lg px-3 py-1.5 text-xs">
                <span className="text-blue-500 font-medium">{k}:</span>{' '}
                <span className="text-blue-800 font-semibold">{indianiseCurrencyText(String(formatted))}</span>
              </div>
            )
          })}
        </div>
      )}

      {/* Chart */}
      {message.chart && (
        <ChartRenderer
          vizConfig={message.chart as Record<string, unknown>}
          vizType={message.viz_type || null}
          columns={message.columns}
          rows={message.rows}
        />
      )}

      {/* Insights — $→₹ converted */}
      {message.insights && message.insights.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-amber-700 mb-2">
            <Lightbulb size={14} /> Key Insights
          </div>
          <ul className="space-y-1">
            {message.insights.map((ins, i) => (
              <li key={i} className="text-xs text-amber-800 flex gap-2">
                <span className="text-amber-400 mt-0.5">•</span>
                {indianiseCurrencyText(ins)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* SQL toggle */}
      {message.sql && (
        <div className="border border-slate-200 rounded-xl overflow-hidden">
          <button
            onClick={() => setShowSQL(!showSQL)}
            className="w-full flex items-center justify-between px-4 py-2.5 bg-slate-50 hover:bg-slate-100 text-xs font-medium text-slate-600 transition"
          >
            <div className="flex items-center gap-2">
              <Code size={13} />
              Generated SQL
            </div>
            {showSQL ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
          {showSQL && (
            <pre className="px-4 py-3 text-xs bg-slate-900 text-green-400 overflow-x-auto whitespace-pre-wrap">
              {message.sql}
            </pre>
          )}
        </div>
      )}

      {/* Follow-up questions */}
      {message.follow_up_questions && message.follow_up_questions.length > 0 && (
        <div>
          <p className="text-xs text-slate-400 mb-2">Suggested follow-ups:</p>
          <div className="flex flex-wrap gap-2">
            {message.follow_up_questions.map((q, i) => (
              <button
                key={i}
                onClick={() => onFollowUp(q)}
                className="text-xs bg-white border border-blue-200 text-blue-600 hover:bg-blue-50 rounded-full px-3 py-1.5 transition"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
