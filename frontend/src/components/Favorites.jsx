import { useEffect, useState } from 'react'
import * as api from '../api/client'
import GameCard from './GameCard.jsx'
import GameDetailModal from './GameDetailModal.jsx'

export default function Favorites({ favoriteIds, onToggleFavorite, refreshSignal }) {
  const [juegos, setJuegos] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [juegoSeleccionado, setJuegoSeleccionado] = useState(null)

  const [query, setQuery] = useState('')
  const [semanticResults, setSemanticResults] = useState(null)

  async function cargarFavoritos() {
    setLoading(true)
    setError('')
    try {
      const data = await api.getFavorites()
      setJuegos(data.juegos || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    cargarFavoritos()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshSignal])

  async function handleSearch(e) {
    e.preventDefault()
    if (!query.trim()) {
      setSemanticResults(null)
      return
    }
    setError('')
    setLoading(true)
    try {
      const data = await api.searchFavoritesSemantic(query)
      setSemanticResults(data.resultados || [])
    } catch (err) {
      setError(err.message)
      setSemanticResults([])
    } finally {
      setLoading(false)
    }
  }

  function clearSearch() {
    setQuery('')
    setSemanticResults(null)
  }

  const juegosPorId = new Map(juegos.map((j) => [j.id, j]))
  const listaAMostrar = semanticResults === null
    ? juegos
    : semanticResults.map((r) => juegosPorId.get(r.id)).filter(Boolean)
  const distanciaPorId = semanticResults
    ? new Map(semanticResults.map((r) => [r.id, r.distancia]))
    : null

  return (
    <div>
      <div className="search-box">
        <input
          className="input"
          placeholder='Busca por concepto dentro de tus favoritos, ej: "estrategia"'
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button className="btn" onClick={handleSearch}>Buscar en favoritos</button>
        {semanticResults !== null && (
          <button className="btn btn-ghost" onClick={clearSearch}>Limpiar</button>
        )}
      </div>

      {error && <div className="error-msg">{error}</div>}

      {loading ? (
        <div className="loading-text">Cargando favoritos...</div>
      ) : listaAMostrar.length === 0 ? (
        <div className="empty-state">
          {semanticResults !== null
            ? 'No encontramos favoritos que coincidan con esa búsqueda.'
            : 'Aún no tienes juegos favoritos. Márcalos desde el Dashboard.'}
        </div>
      ) : (
        <div className="game-grid">
          {listaAMostrar.map((j) => (
            <GameCard
              key={j.id}
              juego={j}
              isFavorite={favoriteIds.has(j.id)}
              onToggleFavorite={onToggleFavorite}
              onOpenDetail={setJuegoSeleccionado}
              distancia={distanciaPorId?.get(j.id)}
            />
          ))}
        </div>
      )}

      {juegoSeleccionado && (
        <GameDetailModal juego={juegoSeleccionado} onClose={() => setJuegoSeleccionado(null)} />
      )}
    </div>
  )
}
