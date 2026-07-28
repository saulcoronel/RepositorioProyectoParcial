import { useEffect, useState, useCallback } from 'react'
import { useAuth } from './context/AuthContext.jsx'
import AuthScreen from './components/AuthScreen.jsx'
import Dashboard from './components/Dashboard.jsx'
import Favorites from './components/Favorites.jsx'
import Admin from './components/Admin.jsx'
import * as api from './api/client'
import { IconGamepad, IconUser, IconStar, IconLayoutGrid, IconSliders } from './components/icons.jsx'

export default function App() {
  const { isAuthenticated, username, doLogout } = useAuth()
  const [tab, setTab] = useState('dashboard') // 'dashboard' | 'favoritos' | 'admin'
  const [health, setHealth] = useState(null)

  const [favoriteIds, setFavoriteIds] = useState(new Set())
  const [favoritesRefresh, setFavoritesRefresh] = useState(0)

  const cargarFavoritosIds = useCallback(async () => {
    if (!isAuthenticated) return
    try {
      const data = await api.getFavorites()
      setFavoriteIds(new Set((data.juegos || []).map((j) => j.id)))
    } catch {
      // silencioso: si falla, el usuario simplemente no ve estrellas marcadas
    }
  }, [isAuthenticated])

  useEffect(() => {
    api.checkHealth().then(setHealth).catch(() => setHealth(null))
    cargarFavoritosIds()
  }, [cargarFavoritosIds])

  async function handleToggleFavorite(juego) {
    const esFavorito = favoriteIds.has(juego.id)
    try {
      if (esFavorito) {
        await api.removeFavorite(juego.id)
      } else {
        await api.addFavorite(juego.id)
      }
      await cargarFavoritosIds()
      setFavoritesRefresh((n) => n + 1)
    } catch (err) {
      alert(err.message)
    }
  }

  function handleDataChanged() {
    setFavoritesRefresh((n) => n + 1)
  }

  if (!isAuthenticated) {
    return <AuthScreen />
  }

  return (
    <div>
      <div className="header">
        <div className="header-logo"><IconGamepad size={22} /> Biblioteca Steam — UNIAT</div>
        <div className="header-sub">Proyecto de Bases de Datos</div>
        <div className="header-user">
          <span className="header-user-name"><IconUser size={16} /> {username}</span>
          <button className="btn btn-danger btn-small" onClick={doLogout}>Cerrar sesión</button>
        </div>
      </div>

      <div className="status-bar">
        <span className={`status-dot ${health ? 'online' : ''}`} />
        <span className="status-text">
          {health ? 'API conectada' : 'Verificando conexión con la API...'}
        </span>
        {health && (
          <span className="status-count">{health.juegos_en_db} juegos en la base de datos</span>
        )}
      </div>

      <div className="main">
        <div className="tabs">
          <button className={`tab ${tab === 'dashboard' ? 'active' : ''}`} onClick={() => setTab('dashboard')}>
            <IconLayoutGrid size={15} /> Dashboard
          </button>
          <button className={`tab ${tab === 'favoritos' ? 'active' : ''}`} onClick={() => setTab('favoritos')}>
            <IconStar size={15} filled={tab === 'favoritos'} /> Mis favoritos
          </button>
          <button className={`tab ${tab === 'admin' ? 'active' : ''}`} onClick={() => setTab('admin')}>
            <IconSliders size={15} /> Administración
          </button>
        </div>

        {tab === 'dashboard' && (
          <Dashboard favoriteIds={favoriteIds} onToggleFavorite={handleToggleFavorite} />
        )}
        {tab === 'favoritos' && (
          <Favorites
            favoriteIds={favoriteIds}
            onToggleFavorite={handleToggleFavorite}
            refreshSignal={favoritesRefresh}
          />
        )}
        {tab === 'admin' && <Admin onDataChanged={handleDataChanged} />}
      </div>
    </div>
  )
}
