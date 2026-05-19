import axios from 'axios'

export const api = axios.create({
  baseURL: '/api/v1',
  timeout: 90000,
  headers: { 'Content-Type': 'application/json' },
})

export interface QueryResponse {
  conversation_id: string
  message_id: string
  text: string
  chart: object | null
  insights: string[]
  key_metrics: Record<string, string>
  follow_up_questions: string[]
  sql: string
  sql_explanation: string
  row_count: number
  viz_type: string | null
  columns: string[]
  rows: Record<string, unknown>[]
  total_latency_ms: number
  model_used: string
  error: string | null
}

export const sendQuery = async (
  question: string,
  datasource_id: string,
  conversation_id?: string
): Promise<QueryResponse> => {
  const { data } = await api.post('/copilot/query', {
    question,
    datasource_id,
    conversation_id,
    user_id: 'demo_user',
  })
  return data
}

export const uploadFile = async (file: File): Promise<{ datasource_id: string; schema: object }> => {
  const form = new FormData()
  form.append('file', file)
  form.append('datasource_name', file.name)
  const { data } = await api.post('/copilot/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export const getHistory = async (conversation_id: string) => {
  const { data } = await api.get(`/copilot/history/${conversation_id}`)
  return data
}

export const getSchema = async (datasource_id: string) => {
  const { data } = await api.get(`/copilot/schema/${datasource_id}`)
  return data
}
