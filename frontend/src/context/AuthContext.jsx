import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import * as api from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [username, setUsername] = useState(() => localStorage.getItem('username'))
  const [token, setToken] = useState(() => localStorage.getItem('token'))
  const [authError, setAuthError] = useState('')

  const isAuthenticated = Boolean(token)

  const doLogin = useCallback(async (user, pass) => {
    setAuthError('')
    const data = await api.login(user, pass)
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('username', user)
    setToken(data.access_token)
    setUsername(user)
  }, [])

  const doRegister = useCallback(async (user, pass) => {
    setAuthError('')
    await api.register(user, pass)
    await doLogin(user, pass)
  }, [doLogin])

  const doLogout = useCallback(() => {
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    setToken(null)
    setUsername(null)
  }, [])

  useEffect(() => {
    const onExpired = () => {
      setToken(null)
      setUsername(null)
      setAuthError('Tu sesión expiró, vuelve a iniciar sesión.')
    }
    window.addEventListener('auth-expired', onExpired)
    return () => window.removeEventListener('auth-expired', onExpired)
  }, [])

  return (
    <AuthContext.Provider
      value={{ username, token, isAuthenticated, authError, doLogin, doRegister, doLogout, setAuthError }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth debe usarse dentro de <AuthProvider>')
  return ctx
}
