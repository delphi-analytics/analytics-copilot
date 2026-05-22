import { api } from './client'

export interface User {
  id: string
  email: string
  name: string
  role: string
  is_active: boolean
  preferences: Record<string, unknown> | null
}

export interface CreateUserRequest {
  email: string
  name: string
  role: string
}

export const usersApi = {
  listUsers: async () => {
    const { data } = await api.get<User[]>('/auth/users')
    return data
  },

  createUser: async (req: CreateUserRequest) => {
    const { data } = await api.post('/auth/users', req)
    return data as { id: string; email: string; name: string; role: string; temp_password: string; message: string }
  },

  updateUser: async (userId: string, req: Record<string, unknown>) => {
    const { data } = await api.put(`/auth/users/${userId}`, req)
    return data as { message: string }
  },

  deleteUser: async (userId: string) => {
    const { data } = await api.delete(`/auth/users/${userId}`)
    return data as { message: string }
  },

  resetPassword: async (email: string) => {
    const { data } = await api.post(`/auth/reset-password?email=${encodeURIComponent(email)}`)
    return data as { message: string; temp_password: string; email: string }
  }
}
