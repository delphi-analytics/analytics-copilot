import axios from 'axios'

export interface LoginRequest {
  email: string
  password: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: {
    id: string
    email: string
    name: string
    role: string
    is_active: boolean
    preferences: Record<string, unknown> | null
  }
}

export interface User {
  id: string
  email: string
  name: string
  role: string
  is_active: boolean
  preferences: Record<string, unknown> | null
}

const authApi = axios.create({
  baseURL: '/api/v1/auth',
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true, // For cookies
})

export const login = async (email: string, password: string): Promise<TokenResponse> => {
  const { data } = await authApi.post('/login', { email, password })
  return data
}

export const refreshToken = async (refreshToken: string): Promise<TokenResponse> => {
  const { data } = await authApi.post('/refresh', { refresh_token: refreshToken })
  return data
}

export const logout = async (): Promise<void> => {
  await authApi.post('/logout')
}

export const getCurrentUser = async (): Promise<User> => {
  const { data } = await authApi.get('/me')
  return data
}

export const createDemoUser = async (
  email: string,
  password: string,
  name?: string,
  role?: string
): Promise<{ id: string; email: string; name: string; role: string }> => {
  const { data } = await authApi.post('/demo/create-user', { email, password, name, role })
  return data
}
