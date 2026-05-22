import { api } from './client'

export interface Report {
  id: string
  name: string
  owner_id: string
  conversation_id: string | null
  content: string
  charts: Record<string, unknown>[]
  schedule: Record<string, unknown> | null
  recipients: string[]
  format: string
  created_at: string
}

export interface CreateReportRequest {
  name: string
  conversation_id?: string
  content?: string
  charts?: Record<string, unknown>[]
  schedule?: Record<string, unknown>
  recipients?: string[]
  format?: string
}

export const reportsApi = {
  list: async () => {
    const { data } = await api.get<Report[]>('/reports')
    return data
  },

  get: async (id: string) => {
    const { data } = await api.get<Report>(`/reports/${id}`)
    return data
  },

  create: async (req: CreateReportRequest) => {
    const { data } = await api.post<{ id: string; name: string; status: string }>('/reports', req)
    return data
  },

  update: async (id: string, req: Record<string, unknown>) => {
    const { data } = await api.put<{ status: string }>(`/reports/${id}`, req)
    return data
  },

  delete: async (id: string) => {
    const { data } = await api.delete<{ status: string }>(`/reports/${id}`)
    return data
  },

  exportReport: async (id: string) => {
    const { data } = await api.post<Record<string, unknown>>(`/reports/${id}/export`)
    return data
  }
}
