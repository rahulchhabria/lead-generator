import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api, User, Team } from '../api/client'

interface AuthState {
  user: User | null
  team: Team | null
  token: string | null
  isLoading: boolean
  isAuthenticated: boolean
}

interface AuthContextType extends AuthState {
  login: (googleToken: string) => Promise<void>
  signup: (googleToken: string, teamName: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [state, setState] = useState<AuthState>({
    user: null,
    team: null,
    token: localStorage.getItem('token'),
    isLoading: true,
    isAuthenticated: false,
  })

  // Validate token on mount
  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) {
      setState(s => ({ ...s, isLoading: false }))
      return
    }

    api.auth.me()
      .then(({ user, team }) => {
        setState({
          user,
          team,
          token,
          isLoading: false,
          isAuthenticated: true,
        })
      })
      .catch(() => {
        localStorage.removeItem('token')
        setState({
          user: null,
          team: null,
          token: null,
          isLoading: false,
          isAuthenticated: false,
        })
      })
  }, [])

  const login = useCallback(async (googleToken: string) => {
    const { token, user, team } = await api.auth.login(googleToken)
    localStorage.setItem('token', token)
    setState({
      user,
      team,
      token,
      isLoading: false,
      isAuthenticated: true,
    })
  }, [])

  const signup = useCallback(async (googleToken: string, teamName: string) => {
    const { token, user, team } = await api.auth.signup(googleToken, teamName)
    localStorage.setItem('token', token)
    setState({
      user,
      team,
      token,
      isLoading: false,
      isAuthenticated: true,
    })
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('token')
    queryClient.clear()
    setState({
      user: null,
      team: null,
      token: null,
      isLoading: false,
      isAuthenticated: false,
    })
  }, [queryClient])

  return (
    <AuthContext.Provider value={{ ...state, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
