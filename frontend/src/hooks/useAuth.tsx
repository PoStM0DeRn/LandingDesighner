import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import api from '../api/client'

export interface AuthUser {
  nickname: string
  created_at?: number | null
}

interface AuthCtx {
  user: AuthUser | null
  login: (nickname: string, password: string) => Promise<void>
  register: (nickname: string, password: string) => Promise<void>
  logout: () => void
  authModalOpen: boolean
  openAuthModal: () => void
  closeAuthModal: () => void
}

const AuthContext = createContext<AuthCtx>({
  user: null,
  login: async () => {},
  register: async () => {},
  logout: () => {},
  authModalOpen: false,
  openAuthModal: () => {},
  closeAuthModal: () => {},
})

function persist(token: string | null, user: AuthUser | null) {
  if (token) localStorage.setItem('lg-token', token)
  else localStorage.removeItem('lg-token')
  if (user) localStorage.setItem('lg-user', JSON.stringify(user))
  else localStorage.removeItem('lg-user')
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => {
    try {
      return JSON.parse(localStorage.getItem('lg-user') || 'null')
    } catch {
      return null
    }
  })
  const [authModalOpen, setAuthModalOpen] = useState(false)

  // Attach Authorization header to every API request
  useEffect(() => {
    const req = api.interceptors.request.use((config) => {
      const token = localStorage.getItem('lg-token')
      if (token) config.headers.Authorization = `Bearer ${token}`
      return config
    })
    return () => api.interceptors.request.eject(req)
  }, [])

  // Auto-logout on 401 from protected endpoints
  useEffect(() => {
    const res = api.interceptors.response.use(
      (r) => r,
      (error) => {
        const url = String(error?.config?.url || '')
        if (error?.response?.status === 401 && !url.includes('/auth/')) {
          persist(null, null)
          setUser(null)
        }
        return Promise.reject(error)
      },
    )
    return () => api.interceptors.response.eject(res)
  }, [])

  // Re-validate the stored token on mount
  useEffect(() => {
    const token = localStorage.getItem('lg-token')
    if (!token) return
    api
      .get('/auth/me')
      .then(({ data }) => {
        setUser(data)
        persist(token, data)
      })
      .catch(() => {
        persist(null, null)
        setUser(null)
      })
  }, [])

  const login = async (nickname: string, password: string) => {
    const { data } = await api.post('/auth/login', { nickname, password })
    persist(data.token, data.user)
    setUser(data.user)
  }

  const register = async (nickname: string, password: string) => {
    const { data } = await api.post('/auth/register', { nickname, password })
    persist(data.token, data.user)
    setUser(data.user)
  }

  const logout = () => {
    api.post('/auth/logout').catch(() => {})
    persist(null, null)
    setUser(null)
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        login,
        register,
        logout,
        authModalOpen,
        openAuthModal: () => setAuthModalOpen(true),
        closeAuthModal: () => setAuthModalOpen(false),
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
