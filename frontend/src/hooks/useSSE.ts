import { useEffect, useRef, useState, useCallback } from 'react'
import { useAuthStore } from '../store/auth'

export interface SSEEvent {
  type: 'start' | 'progress' | 'complete' | 'error' | 'step'
  message?: string
  progress?: string
  step?: string
  data?: {
    sql?: string
    row_count?: number
    tables?: string[]
    columns?: string[]
    viz_type?: string
    [key: string]: unknown
  }
  result?: {
    conversation_id: string
    message_id: string
    text: string
    chart?: object | null
    insights: string[]
    key_metrics: Record<string, string>
    follow_up_questions: string[]
    sql: string
    row_count: number
    viz_type?: string | null
    columns: string[]
    rows: Record<string, unknown>[]
    total_latency_ms: number
    model_used: string
    error?: string | null
  }
  error?: string
}

export interface UseSSEOptions {
  onProgress?: (event: SSEEvent) => void
  onComplete?: (result: SSEEvent['result']) => void
  onError?: (error: string) => void
}

export function useSSE() {
  const [isStreaming, setIsStreaming] = useState(false)
  const [events, setEvents] = useState<SSEEvent[]>([])
  const eventSourceRef = useRef<EventSource | null>(null)
  const { accessToken } = useAuthStore()

  const streamQuery = useCallback((
    question: string,
    datasourceId: string,
    conversationId?: string,
    options: UseSSEOptions = {}
  ) => {
    // Close any existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    setIsStreaming(true)
    setEvents([])

    // Build URL with query parameters
    const params = new URLSearchParams({
      question,
      datasource_id: datasourceId,
    })
    if (conversationId) {
      params.append('conversation_id', conversationId)
    }

    const url = `/api/v1/copilot/stream?${params.toString()}`

    // Create EventSource
    const eventSource = new EventSource(url)
    eventSourceRef.current = eventSource

    eventSource.onmessage = (e) => {
      try {
        const data: SSEEvent = JSON.parse(e.data)

        // Add to events list
        setEvents(prev => [...prev, data])

        // Call specific callbacks
        if (data.type === 'progress' && options.onProgress) {
          options.onProgress(data)
        }
        if (data.type === 'complete' && options.onComplete) {
          options.onComplete(data.result)
          setIsStreaming(false)
          eventSource.close()
        }
        if (data.type === 'error' && options.onError) {
          options.onError(data.error || 'Unknown error')
          setIsStreaming(false)
          eventSource.close()
        }
      } catch (err) {
        console.error('Failed to parse SSE event:', err)
      }
    }

    eventSource.onerror = (err) => {
      console.error('SSE error:', err)
      setIsStreaming(false)
      if (options.onError) {
        options.onError('Connection error')
      }
      eventSource.close()
    }

    // Return cleanup function
    return () => {
      eventSource.close()
      setIsStreaming(false)
    }
  }, [])

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    setIsStreaming(false)
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
    }
  }, [])

  return {
    isStreaming,
    events,
    streamQuery,
    disconnect,
  }
}
