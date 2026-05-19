import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { QueryResponse } from '../api/client'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  chart?: object | null
  insights?: string[]
  key_metrics?: Record<string, string>
  sql?: string
  row_count?: number
  viz_type?: string | null
  columns?: string[]
  rows?: Record<string, unknown>[]
  follow_up_questions?: string[]
  latency_ms?: number
  error?: string | null
  timestamp: Date
}

export interface ChatSession {
  id: string
  conversationId: string | null
  messages: ChatMessage[]
  title: string
  initiatedAt: number
  updatedAt?: number
}

interface ChatStore {
  sessions: ChatSession[]
  activeSessionId: string | null
  datasourceId: string
  isLoading: boolean
  uploadedFile: string | null

  setDatasourceId: (id: string) => void
  setUploadedFile: (name: string | null) => void
  setLoading: (loading: boolean) => void

  startNewSession: () => void
  loadSession: (id: string) => void
  deleteSession: (id: string) => void
  purgeExpiredSessions: () => void

  addUserMessage: (content: string) => void
  addAssistantMessage: (response: QueryResponse, sessionId?: string) => void
  deleteMessage: (messageId: string) => void
  setConversationId: (id: string, sessionId?: string) => void
}

const EXPIRY_TIME_MS = 10 * 60 * 1000 // 10 minutes

export const useChatStore = create<ChatStore>()(
  persist(
    (set) => ({
      sessions: [],
      activeSessionId: null,
      datasourceId: 'limese',   // Default to Limese ClickHouse (real data)
      isLoading: false,
      uploadedFile: null,

      setDatasourceId: (id) => set({ datasourceId: id }),
      setUploadedFile: (name) => set({ uploadedFile: name }),
      setLoading: (loading) => set({ isLoading: loading }),

      startNewSession: () => set({ activeSessionId: null }),

      loadSession: (id) => set({ activeSessionId: id }),

      deleteSession: (id) => set((state) => ({
        sessions: state.sessions.filter(s => s.id !== id),
        activeSessionId: state.activeSessionId === id ? null : state.activeSessionId
      })),

      purgeExpiredSessions: () => set((state) => {
        const now = Date.now()
        const validSessions = state.sessions.filter(s => now - (s.updatedAt || s.initiatedAt) <= EXPIRY_TIME_MS)
        return {
          sessions: validSessions,
          activeSessionId: validSessions.find(s => s.id === state.activeSessionId) ? state.activeSessionId : null
        }
      }),

      addUserMessage: (content) => set((state) => {
        let sessionId = state.activeSessionId
        const newSessions = [...state.sessions]
        let currentSession = newSessions.find(s => s.id === sessionId)

        if (!currentSession) {
          sessionId = crypto.randomUUID()
          currentSession = {
            id: sessionId,
            conversationId: null,
            messages: [],
            title: content.slice(0, 30) + (content.length > 30 ? '...' : ''),
            initiatedAt: Date.now(),
            updatedAt: Date.now()
          }
          newSessions.unshift(currentSession)
        } else {
          const index = newSessions.findIndex(s => s.id === sessionId)
          currentSession = { ...currentSession, messages: [...currentSession.messages], updatedAt: Date.now() }
          newSessions[index] = currentSession
        }

        currentSession.messages.push({
          id: crypto.randomUUID(),
          role: 'user',
          content,
          timestamp: new Date(),
        })

        return { sessions: newSessions, activeSessionId: sessionId }
      }),

      addAssistantMessage: (response, sessionId) => set((state) => {
        const targetId = sessionId || state.activeSessionId
        if (!targetId) return state
 
        const newSessions = [...state.sessions]
        const index = newSessions.findIndex(s => s.id === targetId)
        if (index === -1) return state

        const currentSession = { ...newSessions[index], messages: [...newSessions[index].messages], updatedAt: Date.now() }
        if (!currentSession.conversationId && response.conversation_id) {
          currentSession.conversationId = response.conversation_id
        }

        currentSession.messages.push({
          id: response.message_id,
          role: 'assistant',
          content: response.text,
          chart: response.chart,
          insights: response.insights,
          key_metrics: response.key_metrics,
          sql: response.sql,
          row_count: response.row_count,
          viz_type: response.viz_type,
          columns: response.columns,
          rows: response.rows,
          follow_up_questions: response.follow_up_questions,
          latency_ms: response.total_latency_ms,
          error: response.error,
          timestamp: new Date(),
        })

        newSessions[index] = currentSession
        return { sessions: newSessions }
      }),

      setConversationId: (id, sessionId) => set((state) => {
        const targetId = sessionId || state.activeSessionId
        if (!targetId) return state
        const newSessions = [...state.sessions]
        const index = newSessions.findIndex(s => s.id === targetId)
        if (index !== -1) {
          newSessions[index] = { ...newSessions[index], conversationId: id }
        }
        return { sessions: newSessions }
      }),

      deleteMessage: (messageId) => set((state) => {
        const sessionId = state.activeSessionId
        if (!sessionId) return state

        const newSessions = [...state.sessions]
        const sessionIndex = newSessions.findIndex(s => s.id === sessionId)
        if (sessionIndex === -1) return state

        const currentSession = newSessions[sessionIndex]
        const messageIndex = currentSession.messages.findIndex(m => m.id === messageId)
        
        if (messageIndex === -1) return state

        // Delete the user message and the subsequent assistant message (if it exists)
        let numToDelete = 1
        if (currentSession.messages[messageIndex].role === 'user' && 
            messageIndex + 1 < currentSession.messages.length && 
            currentSession.messages[messageIndex + 1].role === 'assistant') {
          numToDelete = 2
        }

        const newMessages = [...currentSession.messages]
        newMessages.splice(messageIndex, numToDelete)

        newSessions[sessionIndex] = { ...currentSession, messages: newMessages, updatedAt: Date.now() }
        return { sessions: newSessions }
      })
    }),
    {
      name: 'analytics-copilot-chat-storage', // name of item in localStorage
      partialize: (state) => ({
        sessions: state.sessions,
        activeSessionId: state.activeSessionId,
        datasourceId: state.datasourceId,
        uploadedFile: state.uploadedFile,
      }), // only persist these fields
    }
  )
)
