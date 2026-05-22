import { api } from './client'

export interface Dashboard {
  id: string
  name: string
  description?: string
  chart_count: number
  created_at: string
  is_public: boolean
}

export interface DashboardDetail extends Dashboard {
  layout: Record<string, unknown>
  refresh_interval_seconds?: number
  updated_at: string
  charts: DashboardChart[]
}

export interface DashboardChart {
  id: string
  title: string
  datasource_id: string
  sql_query: string
  viz_config: Record<string, unknown> | null
  position: { x?: number; y?: number; w?: number; h?: number }
}

export interface CreateDashboardRequest {
  name: string
  description?: string
  owner_id?: string
}

export interface AddChartRequest {
  title: string
  datasource_id: string
  sql_query: string
  viz_config: Record<string, unknown>
  position?: Record<string, unknown>
}

export const dashboardsApi = {
  list: async (ownerId = 'anonymous') => {
    const { data } = await api.get<Dashboard[]>('/dashboards', { params: { owner_id: ownerId } })
    return data
  },

  get: async (id: string) => {
    const { data } = await api.get<DashboardDetail>(`/dashboards/${id}`)
    return data
  },

  create: async (req: CreateDashboardRequest) => {
    const { data } = await api.post<{ id: string; name: string; status: string }>('/dashboards', req)
    return data
  },

  update: async (id: string, req: Record<string, unknown>) => {
    const { data } = await api.put<{ status: string }>(`/dashboards/${id}`, req)
    return data
  },

  delete: async (id: string) => {
    const { data } = await api.delete<{ status: string }>(`/dashboards/${id}`)
    return data
  },

  addChart: async (dashboardId: string, req: AddChartRequest) => {
    const { data } = await api.post<{ chart_id: string; status: string }>(`/dashboards/${dashboardId}/charts`, req)
    return data
  },

  updateChart: async (dashboardId: string, chartId: string, req: Record<string, unknown>) => {
    const { data } = await api.put<{ status: string }>(`/dashboards/${dashboardId}/charts/${chartId}`, req)
    return data
  },

  deleteChart: async (dashboardId: string, chartId: string) => {
    const { data } = await api.delete<{ status: string }>(`/dashboards/${dashboardId}/charts/${chartId}`)
    return data
  },

  refreshChart: async (dashboardId: string, chartId: string) => {
    const { data } = await api.get(`/dashboards/${dashboardId}/charts/${chartId}/refresh`)
    return data
  }
}
