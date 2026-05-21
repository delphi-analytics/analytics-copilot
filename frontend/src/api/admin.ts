import { api } from './client'

export interface Approval {
  id: string
  change_type: string
  title: string
  description: string
  diff_data: Record<string, unknown>
  status: string
  created_at: string
}

export interface ScanResponse {
  status: string
  message?: string
  approval_id?: string
}

export const adminApi = {
  getApprovals: async () => {
    const { data } = await api.get<Approval[]>('/admin/approvals')
    return data
  },

  approveChange: async (approvalId: string) => {
    const { data } = await api.post<{ status: string; message: string }>(`/admin/approve/${approvalId}`)
    return data
  },

  rejectChange: async (approvalId: string, reason?: string) => {
    const { data } = await api.post<{ status: string; message: string }>(
      `/admin/reject/${approvalId}`,
      { reason }
    )
    return data
  },

  triggerScan: async () => {
    const { data } = await api.post<ScanResponse>('/admin/trigger-scan')
    return data
  }
}
