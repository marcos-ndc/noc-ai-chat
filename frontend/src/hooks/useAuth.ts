import { useCallback } from 'react'
import { create } from 'zustand'
import type { AuthState, AuthCredentials, User } from '../types'

// ─── Auth Store (Zustand) ─────────────────────────────────────────────────────

interface AuthStore extends AuthState {
  login: (token: string, user: User) => void
  logout: () => void
}

export const useAuthStore = create<AuthStore>((set) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  login: (token, user) => set({ token, user, isAuthenticated: true }),
  logout: () => set({ token: null, user: null, isAuthenticated: false }),
}))

// ─── useAuth Hook ─────────────────────────────────────────────────────────────

const API_URL = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'

interface UseAuthReturn {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  login: (credentials: AuthCredentials) => Promise<void>
  logout: () => void
}

import { useState } from 'react'

export function useAuth(): UseAuthReturn {
  const { user, isAuthenticated, login: storeLogin, logout: storeLogout } = useAuthStore()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const login = useCallback(async (credentials: AuthCredentials) => {
    setIsLoading(true)
    setError(null)

    try {
      const response = await fetch(`${API_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(credentials),
      })

      if (!response.ok) {
        const data = await response.json() as { detail?: string }
        throw new Error(data.detail ?? 'Credenciais inválidas')
      }

      const data = await response.json() as { token: string; user: User }
      storeLogin(data.token, data.user)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao fazer login')
    } finally {
      setIsLoading(false)
    }
  }, [storeLogin])

  const logout = useCallback(() => {
    storeLogout()
  }, [storeLogout])

  return { user, isAuthenticated, isLoading, error, login, logout }
}
