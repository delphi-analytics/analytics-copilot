import React, { useEffect, useRef, useState } from 'react'
import { BarChart2, Database, Clock, Plus, Trash2 } from 'lucide-react'
import { useChatStore, ChatSession } from '../store/chat'
import { useThemeStore } from '../store/theme'
import { sendQuery } from '../api/client'
import { ChatMessageComponent } from '../components/Chat/ChatMessage'
import { ChatInput } from '../components/Chat/ChatInput'
import DisambiguationModal from '../components/DisambiguationModal'
import Sidebar from '../components/Layout/Sidebar'
import TransparencyPanel from '../components/TransparencyPanel'
import { useStreamingQuery, type TransparencyStep } from '../hooks/useStreamingQuery'

export const CopilotPage: React.FC = () => {
  const {
    sessions, activeSessionId, isLoading, datasourceId,
    addUserMessage, addAssistantMessage, setLoading, startNewSession,
    setConversationId, setUploadedFile, setDatasourceId, loadSession, purgeExpiredSessions,
    deleteSession, deleteMessage
  } = useChatStore()

  const { theme } = useThemeStore()

  // Permanently reset to ClickHouse datasource — clear any stale uploaded file from localStorage
  useEffect(() => {
    setDatasourceId('limese')
    setUploadedFile(null)
  }, [])

  const activeSession = sessions.find(s => s.id === activeSessionId)
  const messages = activeSession?.messages || []
  const conversationId = activeSession?.conversationId || null
  const [sessionToDelete, setSessionToDelete] = useState<ChatSession | null>(null)
  const [chatInputValue, setChatInputValue] = useState('')
  const [messageToDelete, setMessageToDelete] = useState<string | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)

  // Transparency panel state
  const [transparencySteps, setTransparencySteps] = useState<TransparencyStep[]>([])
  const [showTransparency, setShowTransparency] = useState(false)

  // Streaming query hook
  const { streamQuery, isStreaming } = useStreamingQuery()

  // Disambiguation state
  const [disambiguation, setDisambiguation] = useState<{
    keyword: string
    options: string[]
    originalQuestion: string
  } | null>(null)

  useEffect(() => {
    purgeExpiredSessions()
    const interval = setInterval(purgeExpiredSessions, 60000)
    return () => clearInterval(interval)
  }, [purgeExpiredSessions])

  const bottomRef = useRef<HTMLDivElement>(null)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  // Start / stop elapsed timer when loading state changes
  useEffect(() => {
    if (isLoading) {
      setElapsedSeconds(0)
      timerRef.current = setInterval(() => {
        setElapsedSeconds(prev => prev + 1)
      }, 1000)
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [isLoading])

  const handleSend = async (question: string) => {
    if (isLoading || isStreaming) return
    addUserMessage(question)

    // Immediately capture the activeSessionId in case the user switches sessions during loading
    const targetSessionId = useChatStore.getState().activeSessionId || undefined

    setLoading(true)
    setTransparencySteps([])
    setShowTransparency(true)

    // Use streaming query for real-time updates
    streamQuery(question, datasourceId, {
      onData: (step) => {
        setTransparencySteps(prev => [...prev, step])
      },
      onComplete: (response) => {
        setLoading(false)
        setShowTransparency(false)

        // Check for disambiguation error
        if (response.error?.startsWith('DISAMBIGUATION_NEEDED:')) {
          const errorParts = response.error.split(':')
          const keyword = errorParts[1]
          const options = response.follow_up_questions || []

          // Remove the assistant message with disambiguation request
          const session = useChatStore.getState().sessions.find(s => s.id === targetSessionId)
          if (session?.messages.length) {
            useChatStore.getState().deleteMessage(targetSessionId!, session.messages[session.messages.length - 1].id)
          }

          setDisambiguation({ keyword, options, originalQuestion: question })
          return
        }

        addAssistantMessage(response, targetSessionId)
        if (response.conversation_id && !conversationId) {
          setConversationId(response.conversation_id, targetSessionId)
        }
      },
      onError: (error) => {
        setLoading(false)
        setShowTransparency(false)
        addAssistantMessage({
          conversation_id: conversationId || '',
          message_id: crypto.randomUUID(),
          text: 'Something went wrong. Please try after some time.',
          chart: null, insights: [], key_metrics: {}, follow_up_questions: [],
          sql: '', sql_explanation: '', row_count: 0, viz_type: null,
          columns: [], rows: [], total_latency_ms: 0, model_used: '',
          error,
        }, targetSessionId)
      }
    })
  }

  const handleDisambiguationSelect = async (selectedMeaning: string) => {
    if (!disambiguation) return

    setDisambiguation(null)
    setLoading(true)
    setShowTransparency(true)

    const targetSessionId = useChatStore.getState().activeSessionId || undefined
    const modifiedQuestion = `${disambiguation.originalQuestion} (Note: ${disambiguation.keyword} means '${selectedMeaning}')`

    streamQuery(modifiedQuestion, datasourceId, {
      onData: (step) => {
        setTransparencySteps(prev => [...prev, step])
      },
      onComplete: (response) => {
        setLoading(false)
        setShowTransparency(false)
        addAssistantMessage(response, targetSessionId)
        if (response.conversation_id && !conversationId) {
          setConversationId(response.conversation_id, targetSessionId)
        }
      },
      onError: (error) => {
        setLoading(false)
        setShowTransparency(false)
        addAssistantMessage({
          conversation_id: conversationId || '',
          message_id: crypto.randomUUID(),
          text: 'Something went wrong. Please try after some time.',
          chart: null, insights: [], key_metrics: {}, follow_up_questions: [],
          sql: '', sql_explanation: '', row_count: 0, viz_type: null,
          columns: [], rows: [], total_latency_ms: 0, model_used: '',
          error,
        }, targetSessionId)
      }
    })
  }


  return (
    <div className={`flex h-screen ${theme === 'dark' ? 'bg-zinc-950' : 'bg-slate-50'}`}>
      {/* Sidebar */}
      <Sidebar isOpen={sidebarOpen} onToggle={() => setSidebarOpen(!sidebarOpen)} />

      {/* Main Content */}
      <div className={`flex flex-col flex-1 transition-all duration-300 ${sidebarOpen ? 'lg:ml-60' : 'lg:ml-14'}`}>
        {/* Header */}
        <header className={`flex items-center justify-between px-6 py-4 border-b shadow-sm z-10 ${
          theme === 'dark' ? 'bg-zinc-900 border-zinc-800' : 'bg-white border-slate-200'
        }`}>
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center">
              <BarChart2 size={18} className="text-white" />
            </div>
            <div>
              <h1 className={`font-semibold text-sm ${theme === 'dark' ? 'text-zinc-100' : 'text-slate-800'}`}>
                Data Visualization Copilot
              </h1>
              <p className={`text-xs ${theme === 'dark' ? 'text-zinc-400' : 'text-slate-400'}`}>
                AI-Powered Analytics · Limese
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Datasource indicator */}
            <div className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs ${
              theme === 'dark' ? 'bg-zinc-800 text-zinc-300' : 'bg-slate-100 text-slate-600'
            }`}>
              <Database size={12} className="text-green-500" />
              <span>Limese Analytics · ClickHouse</span>
            </div>
          </div>
        </header>

        {/* Messages - Fixed scrollbar */}
        <div className="flex-1 overflow-y-auto overflow-x-hidden px-4 md:px-8 py-6 max-w-4xl w-full mx-auto">
          {messages.length === 0 ? (
            <WelcomeScreen onQuestionClick={handleSend} theme={theme} />
          ) : (
            <>
              {messages.map((msg) => (
                <ChatMessageComponent
                  key={msg.id}
                  message={msg}
                  onFollowUp={handleSend}
                  onEdit={(id, content) => setChatInputValue(content)}
                  onDelete={(id) => setMessageToDelete(id)}
                  theme={theme}
                />
              ))}
              {isLoading && <ThinkingIndicator seconds={elapsedSeconds} theme={theme} />}
            </>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Transparency Panel - Shows real-time progress */}
        {showTransparency && transparencySteps.length > 0 && (
          <TransparencyPanel
            steps={transparencySteps}
            isComplete={!isLoading && !isStreaming}
            sql={transparencySteps.find(s => s.data?.sql)?.data?.sql as string}
            tables={transparencySteps
              .find(s => s.step === 'discover_schema' || s.step === 'generate_sql')
              ?.data?.tables as string[] || []}
            columns={transparencySteps.find(s => s.data?.columns)?.data?.columns as string[]}
          />
        )}

        {/* Disambiguation Modal */}
        {disambiguation && (
          <div className="max-w-4xl mx-auto px-4 pb-2">
            <DisambiguationModal
              keyword={disambiguation.keyword}
              options={disambiguation.options}
              onSelect={handleDisambiguationSelect}
              onDismiss={() => setDisambiguation(null)}
            />
          </div>
        )}

        {/* Input */}
        <div className={`border-t ${theme === 'dark' ? 'bg-zinc-900 border-zinc-800' : 'bg-white border-slate-200'}`}>
          <div className="max-w-4xl mx-auto">
            <ChatInput
              value={chatInputValue}
              onChange={setChatInputValue}
              onSend={handleSend}
              isLoading={isLoading}
              theme={theme}
            />
          </div>
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {sessionToDelete && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[100] animate-in fade-in duration-200">
          <div className={`${theme === 'dark' ? 'bg-zinc-900 border-zinc-700' : 'bg-white border-slate-200'} border rounded-2xl shadow-xl max-w-sm w-full mx-4 p-5 animate-in zoom-in-95 duration-200`}>
            <h3 className={`font-bold text-base mb-1.5 flex items-center gap-2 ${theme === 'dark' ? 'text-zinc-100' : 'text-slate-800'}`}>
              <span className="p-1.5 bg-red-500/10 rounded-lg text-red-500">
                <Trash2 size={16} />
              </span>
              Delete Conversation?
            </h3>
            <p className={`text-xs mb-5 leading-relaxed ${theme === 'dark' ? 'text-zinc-400' : 'text-slate-500'}`}>
              Are you sure you want to delete <span className={`font-semibold ${theme === 'dark' ? 'text-zinc-300' : 'text-slate-700'}`}>"{sessionToDelete.title}"</span>? This action cannot be undone.
            </p>
            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => setSessionToDelete(null)}
                className={`px-3 py-1.5 rounded-lg border text-xs font-medium transition ${
                  theme === 'dark'
                    ? 'border-zinc-700 text-zinc-300 hover:bg-zinc-800'
                    : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                }`}
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  deleteSession(sessionToDelete.id);
                  setSessionToDelete(null);
                }}
                className="px-3 py-1.5 rounded-lg bg-red-500 hover:bg-red-600 text-white text-xs font-medium transition shadow-sm"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Message Confirmation Modal */}
      {messageToDelete && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[100] animate-in fade-in duration-200">
          <div className={`${theme === 'dark' ? 'bg-zinc-900 border-zinc-700' : 'bg-white border-slate-200'} border rounded-2xl shadow-xl max-w-sm w-full mx-4 p-5 animate-in zoom-in-95 duration-200`}>
            <h3 className={`font-bold text-base mb-1.5 flex items-center gap-2 ${theme === 'dark' ? 'text-zinc-100' : 'text-slate-800'}`}>
              <span className="p-1.5 bg-red-500/10 rounded-lg text-red-500">
                <Trash2 size={16} />
              </span>
              Delete Question?
            </h3>
            <p className={`text-xs mb-5 leading-relaxed ${theme === 'dark' ? 'text-zinc-400' : 'text-slate-500'}`}>
              Are you sure you want to delete this question? This will also remove the associated response.
            </p>
            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => setMessageToDelete(null)}
                className={`px-3 py-1.5 rounded-lg border text-xs font-medium transition ${
                  theme === 'dark'
                    ? 'border-zinc-700 text-zinc-300 hover:bg-zinc-800'
                    : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                }`}
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  deleteMessage(messageToDelete);
                  setMessageToDelete(null);
                }}
                className="px-3 py-1.5 rounded-lg bg-red-500 hover:bg-red-600 text-white text-xs font-medium transition shadow-sm"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

const WelcomeScreen: React.FC<{ onQuestionClick: (q: string) => void; theme: string }> = ({ onQuestionClick, theme }) => (
  <div className="flex flex-col items-center justify-center min-h-96 text-center py-12">
    <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center mb-6 shadow-lg">
      <BarChart2 size={32} className="text-white" />
    </div>
    <h2 className={`text-2xl font-bold mb-2 ${theme === 'dark' ? 'text-zinc-100' : 'text-slate-800'}`}>Limese Data Copilot</h2>
    <p className={`mb-2 max-w-md ${theme === 'dark' ? 'text-zinc-400' : 'text-slate-500'}`}>
      Ask questions about Limese sales, inventory, and products in plain English.
    </p>
    <p className={`text-xs mb-8 ${theme === 'dark' ? 'text-zinc-500' : 'text-slate-400'}`}>Connected to ClickHouse · 340K+ orders · ₹570 Cr revenue</p>
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-xl w-full">
      {[
        { q: "Show total revenue by platform as a pie chart", icon: "📊" },
        { q: "What is the monthly sales trend for Nykaa Beauty in 2025?", icon: "📈" },
        { q: "Top 10 best-selling SKUs by units ordered", icon: "🏆" },
        { q: "Compare Skincare vs Makeup revenue by month", icon: "⚖️" },
        { q: "Which products are low on inventory right now?", icon: "📦" },
        { q: "Show revenue from Nykaa Beauty vs Myntra_PPMP vs Shopify", icon: "🌐" },
      ].map(({ q, icon }) => (
        <button
          key={q}
          onClick={() => onQuestionClick(q)}
          className={`flex items-start gap-3 text-left p-4 rounded-xl hover:border-blue-300 hover:bg-blue-50 transition shadow-sm group ${
            theme === 'dark'
              ? 'bg-zinc-900 border-zinc-800 text-zinc-300 hover:bg-zinc-800'
              : 'bg-white border-slate-200 text-slate-600'
          }`}
        >
          <span className="text-lg">{icon}</span>
          <span className={`text-sm ${theme === 'dark' ? 'group-hover:text-blue-400' : 'group-hover:text-blue-700'}`}>{q}</span>
        </button>
      ))}
    </div>
  </div>
)

// Live thinking indicator with elapsed timer
const ThinkingIndicator: React.FC<{ seconds: number; theme: string }> = ({ seconds, theme }) => {
  const stages = [
    { at: 0, label: 'Understanding your question...' },
    { at: 3, label: 'Discovering schema & tables...' },
    { at: 6, label: 'Generating SQL query...' },
    { at: 10, label: 'Executing on ClickHouse...' },
    { at: 13, label: 'Analysing results...' },
    { at: 16, label: 'Building chart & insights...' },
    { at: 19, label: 'Composing response...' },
  ]

  // Pick the latest stage that has been reached
  const reachedStages = stages.filter(s => seconds >= s.at)
  const current = reachedStages.length > 0 ? reachedStages[reachedStages.length - 1] : stages[0]

  return (
    <div className="flex flex-col gap-2 mb-4">
      <div className={`flex items-center gap-2 ${theme === 'dark' ? 'text-zinc-400' : 'text-slate-400'}`}>
        <div className="w-6 h-6 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
          <div className="w-2 h-2 rounded-full bg-white animate-ping" />
        </div>
        <div className={`flex flex-col rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm gap-1.5 ${
          theme === 'dark'
            ? 'bg-zinc-900 border-zinc-800'
            : 'bg-white border border-slate-200'
        }`}>
          {/* Stage label */}
          <div className="flex items-center gap-2">
            <div className="flex gap-1">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="w-2 h-2 rounded-full bg-blue-400 animate-bounce"
                  style={{ animationDelay: `${i * 150}ms` }}
                />
              ))}
            </div>
            <span className={`text-xs ${theme === 'dark' ? 'text-zinc-300' : 'text-slate-500'}`}>{current.label}</span>
          </div>
          {/* Elapsed timer + progress bar */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1 text-xs font-mono text-blue-500">
              <Clock size={11} />
              <span>{seconds}s</span>
            </div>
            {/* 7-step progress bar — one pip per stage */}
            <div className="flex gap-1">
              {stages.map((s, i) => (
                <div
                  key={i}
                  className={`w-5 h-1 rounded-full transition-all duration-500 ${
                    seconds >= s.at
                      ? 'bg-blue-500'
                      : theme === 'dark' ? 'bg-zinc-700' : 'bg-slate-200'
                  }`}
                />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
