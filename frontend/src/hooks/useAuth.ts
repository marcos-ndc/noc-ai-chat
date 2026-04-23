import { useCallback, useEffect, useState } from 'react'
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { AuthState, AuthCredentials, User } from '../types'

// ─── Auth Store (Zustand + localStorage persistence) ─────────────────────────

interface AuthStore extends AuthState {
  isLoading: boolean
  error: string | null
  login: (token: string, user: User) => void
  logout: () => void
  setLoading: (v: boolean) => void
  setError: (v: string | null) => void
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
      login: (token, user) => set({ token, user, isAuthenticated: true, error: null }),
      logout: () => set({ token: null, user: null, isAuthenticated: false }),
      setLoading: (v) => set({ isLoading: v }),
      setError: (v) => set({ error: v }),
    }),
    {
      name: 'noc-ai-auth',
      version: 2,
      migrate: () => ({ token: null, user: null, isAuthenticated: false }),
      partialize: (state) => ({
        token:           state.token,
        user:            state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)

/** Hook que retorna true assim que o store terminou de hidratar do localStorage */
export function useHydrated(): boolean {
  const [hydrated, setHydrated] = useState(
    () => useAuthStore.persist.hasHydrated()
  )

  useEffect(() => {
    if (hydrated) return
    const unsub = useAuthStore.persist.onFinishHydration(() => setHydrated(true))
    // Caso já tenha hidratado antes de assinar o listener
    if (useAuthStore.persist.hasHydrated()) setHydrated(true)
    return unsub
  }, [hydrated])

  return hydrated
}

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

export function useAuth(): UseAuthReturn {
  const {
    user, isAuthenticated, isLoading, error,
    login: storeLogin, logout: storeLogout,
    setLoading, setError,
  } = useAuthStore()

  const login = useCallback(async (credentials: AuthCredentials) => {
    setLoading(true)
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
      setLoading(false)
    }
  }, [storeLogin, setLoading, setError])

  const logout = useCallback(() => {
    storeLogout()
  }, [storeLogout])

  return { user, isAuthenticated, isLoading, error, login, logout }
}
