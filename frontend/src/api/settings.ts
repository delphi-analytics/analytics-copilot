import { api } from './client'

export interface UpdateProfileRequest {
  name?: string
  email?: string
}

export interface UpdatePasswordRequest {
  current_password: string
  new_password: string
}

export const settingsApi = {
  updateProfile: async (req: UpdateProfileRequest) => {
    const { data } = await api.put('/auth/me', req)
    return data
  },

  updatePassword: async (req: UpdatePasswordRequest) => {
    const { data } = await api.put('/auth/me/password', req)
    return data
  },

  getPreferences: async () => {
    const { data } = await api.get<{ preferences: Record<string, unknown> }>('/auth/me/preferences')
    return data
  },

  updatePreferences: async (preferences: Record<string, unknown>) => {
    const { data } = await api.put('/auth/me/preferences', { preferences })
    return data
  }
}
