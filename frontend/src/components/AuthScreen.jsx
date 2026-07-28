import { useState } from 'react'
import { useAuth } from '../context/AuthContext.jsx'
import { IconGamepad } from './icons.jsx'

export default function AuthScreen() {
  const { doLogin, doRegister, authError, setAuthError } = useAuth()
  const [mode, setMode] = useState('login') // 'login' | 'register'
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setAuthError('')
    setLoading(true)
    try {
      if (mode === 'login') {
        await doLogin(username, password)
      } else {
        await doRegister(username, password)
      }
    } catch (err) {
      setAuthError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-wrapper">
      <div className="auth-card">
        <div className="auth-title"><IconGamepad size={26} /> Biblioteca Steam</div>
        <div className="auth-sub">
          {mode === 'login' ? 'Inicia sesión para continuar' : 'Crea una cuenta nueva'}
        </div>

        {authError && <div className="error-msg">{authError}</div>}

        <form onSubmit={handleSubmit}>
          <div className="auth-field">
            <label>Usuario</label>
            <input
              className="input"
              style={{ width: '100%' }}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
            />
          </div>
          <div className="auth-field">
            <label>Contraseña</label>
            <input
              className="input"
              style={{ width: '100%' }}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <button className="btn" style={{ width: '100%' }} type="submit" disabled={loading}>
            {loading ? 'Espera...' : mode === 'login' ? 'Iniciar sesión' : 'Registrarme'}
          </button>
        </form>

        <div className="auth-switch">
          {mode === 'login' ? (
            <>
              ¿No tienes cuenta?{' '}
              <button onClick={() => { setMode('register'); setAuthError('') }}>Regístrate</button>
            </>
          ) : (
            <>
              ¿Ya tienes cuenta?{' '}
              <button onClick={() => { setMode('login'); setAuthError('') }}>Inicia sesión</button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
