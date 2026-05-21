import { api } from './client'

export interface AnalyticsSummary {
  total_queries: number
  cache_hit_rate: number
  avg_latency_ms: number
  success_rate: number
  days: number
}

export interface DailyStats {
  date: string
  count: number
  cache_hits: number
}

export interface PopularQuery {
  question: string
  count: number
}

export interface IntentDistribution {
  intent_type: string
  count: number
}

export interface UserActivity {
  user_id: string
  query_count: number
  avg_latency_ms: number
}

export interface DatasourcePerformance {
  datasource_id: string
  query_count: number
  avg_latency_ms: number
  success_rate: number
}

export interface AdminSummary extends AnalyticsSummary {
  unique_users: number
  datasources: number
}

export const analyticsApi = {
  // User analytics (available to all authenticated users)
  getSummary: async (days = 30) => {
    const { data } = await api.get<AnalyticsSummary>('/analytics/summary', {
      params: { days }
    })
    return data
  },

  getDailyStats: async (days = 30) => {
    const { data } = await api.get<DailyStats[]>('/analytics/daily', {
      params: { days }
    })
    return data
  },

  getPopularQueries: async (limit = 10) => {
    const { data } = await api.get<PopularQuery[]>('/analytics/popular', {
      params: { limit }
    })
    return data
  },

  getIntentDistribution: async () => {
    const { data } = await api.get<IntentDistribution[]>('/analytics/intents')
    return data
  },

  // Admin analytics (admin only)
  getAdminSummary: async (days = 30) => {
    const { data } = await api.get<AdminSummary>('/analytics/admin/summary', {
      params: { days }
    })
    return data
  },

  getUserActivity: async (days = 30) => {
    const { data } = await api.get<UserActivity[]>('/analytics/admin/users', {
      params: { days }
    })
    return data
  },

  getDatasourcePerformance: async (days = 30) => {
    const { data } = await api.get<DatasourcePerformance[]>('/analytics/admin/datasources', {
      params: { days }
    })
    return data
  }
}
