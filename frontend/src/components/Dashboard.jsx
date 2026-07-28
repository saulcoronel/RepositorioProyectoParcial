import { useEffect, useMemo, useState } from 'react'
import * as api from '../api/client'
import GameCard from './GameCard.jsx'
import GameDetailModal from './GameDetailModal.jsx'
import { IconRefresh, IconSearch } from './icons.jsx'

export default function Dashboard({ favoriteIds, onToggleFavorite }) {
  const [juegos, setJuegos] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [juegoSeleccionado, setJuegoSeleccionado] = useState(null)

  const [sincronizando, setSincronizando] = useState(false)
  const [progresoSinc, setProgresoSinc] = useState({ procesados: 0, ultimoJuego: '' })
  const [resultadoSinc, setResultadoSinc] = useState('')

  const [searchMode, setSearchMode] = useState('nombre') // 'nombre' | 'semantica'
  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] = useState(null) // null = sin búsqueda activa
  const [semanticResults, setSemanticResults] = useState(null)

  const [genero, setGenero] = useState('')
  const [precioMin, setPrecioMin] = useState('')
  const [precioMax, setPrecioMax] = useState('')
  const [anio, setAnio] = useState('')

  async function cargarJuegos() {
    setLoading(true)
    setError('')
    try {
      const data = await api.getGames({
        genero: genero || undefined,
        precio_min: precioMin || undefined,
        precio_max: precioMax || undefined,
        anio: anio || undefined,
        limit: 200,
      })
      setJuegos(data.juegos || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    cargarJuegos()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [genero, precioMin, precioMax, anio])

  const generosDisponibles = useMemo(() => {
    const set = new Set()
    juegos.forEach((j) => (j.generos || []).forEach((g) => set.add(g)))
    return Array.from(set).sort()
  }, [juegos])

  async function handleSincronizarTodo() {
    setSincronizando(true)
    setResultadoSinc('')
    setError('')
    let totalProcesados = 0
    let totalErrores = 0

    try {
      // Llama repetidamente al endpoint hasta que ya no queden juegos sin media.
      // Cada llamada procesa hasta 20 juegos (con pausas internas para no saturar Steam),
      // así que esto puede tardar si tienes muchos juegos pendientes.
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const data = await api.syncMediaTodos(5)
        if (data.total_procesados === 0) break

        totalProcesados += data.total_procesados
        totalErrores += (data.detalle || []).filter((d) => d.error).length
        const ultimo = data.detalle?.[data.detalle.length - 1]
        setProgresoSinc({ procesados: totalProcesados, ultimoJuego: ultimo?.nombre || '' })
      }

      setResultadoSinc(
        totalProcesados === 0
          ? 'Todos los juegos ya tenían su media sincronizada.'
          : `Listo: se sincronizaron ${totalProcesados} juego(s)` +
            (totalErrores > 0 ? ` (${totalErrores} no se encontraron en Steam).` : '.')
      )
      await cargarJuegos()
    } catch (err) {
      setError(err.message)
    } finally {
      setSincronizando(false)
    }
  }

  async function handleSearch(e) {
    e.preventDefault()
    if (!query.trim()) {
      setSearchResults(null)
      setSemanticResults(null)
      return
    }
    setError('')
    setLoading(true)
    try {
      if (searchMode === 'nombre') {
        setSemanticResults(null)
        const data = await api.searchGamesByName(query)
        setSearchResults(data.juegos || [])
      } else {
        setSearchResults(null)
        const data = await api.searchSemantic(query)
        setSemanticResults(data.resultados || [])
      }
    } catch (err) {
      setError(err.message)
      setSearchResults(searchMode === 'nombre' ? [] : null)
      setSemanticResults(searchMode === 'semantica' ? [] : null)
    } finally {
      setLoading(false)
    }
  }

  function clearSearch() {
    setQuery('')
    setSearchResults(null)
    setSemanticResults(null)
  }

  // Para resultados semánticos, ChromaDB solo devuelve nombre/id/distancia; cruzamos con
  // los datos completos que ya tenemos en memoria para mostrar la tarjeta completa.
  const juegosPorNombre = useMemo(() => {
    const map = new Map()
    juegos.forEach((j) => map.set(j.nombre, j))
    return map
  }, [juegos])

  let listaAMostrar = juegos
  let distanciaPorNombre = null

  if (searchResults !== null) {
    listaAMostrar = searchResults
  } else if (semanticResults !== null) {
    distanciaPorNombre = new Map(semanticResults.map((r) => [r.nombre, r.distancia]))
    listaAMostrar = semanticResults
      .map((r) => juegosPorNombre.get(r.nombre))
      .filter(Boolean)
    // Si el juego no está en la página actual de /games (por límite/paginación),
    // igual mostramos lo mínimo que ChromaDB devolvió.
    const faltantes = semanticResults.filter((r) => !juegosPorNombre.get(r.nombre))
    listaAMostrar = [
      ...listaAMostrar,
      ...faltantes.map((r) => ({ nombre: r.nombre, id: r.id, generos: [], estudio: [] })),
    ]
  }

  return (
    <div>
      <div className="sync-bar">
        <button className="btn btn-ghost btn-small" onClick={handleSincronizarTodo} disabled={sincronizando}>
          <IconRefresh size={13} />
          {sincronizando ? 'Sincronizando...' : 'Sincronizar imágenes y video'}
        </button>
        {sincronizando && (
          <span className="sync-status">
            {progresoSinc.procesados} sincronizado(s){progresoSinc.ultimoJuego ? ` — último: ${progresoSinc.ultimoJuego}` : ''}
          </span>
        )}
        {!sincronizando && resultadoSinc && (
          <span className="sync-status">{resultadoSinc}</span>
        )}
      </div>

      <div className="search-box">
        <input
          className="input"
          placeholder={
            searchMode === 'nombre' ? 'Buscar juego por nombre...' : 'Describe qué buscas, ej: "juegos de terror"'
          }
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select className="select" value={searchMode} onChange={(e) => setSearchMode(e.target.value)}>
          <option value="nombre">Por nombre</option>
          <option value="semantica">Semántica (ChromaDB)</option>
        </select>
        <button className="btn" onClick={handleSearch}>Buscar</button>
        {(searchResults !== null || semanticResults !== null) && (
          <button className="btn btn-ghost" onClick={clearSearch}>Limpiar</button>
        )}
      </div>

      <div className="filters-row">
        <select className="select" value={genero} onChange={(e) => setGenero(e.target.value)}>
          <option value="">Todos los géneros</option>
          {generosDisponibles.map((g) => (
            <option key={g} value={g}>{g}</option>
          ))}
        </select>
        <input
          className="input"
          style={{ minWidth: 110 }}
          type="number"
          placeholder="Precio mín."
          value={precioMin}
          onChange={(e) => setPrecioMin(e.target.value)}
        />
        <input
          className="input"
          style={{ minWidth: 110 }}
          type="number"
          placeholder="Precio máx."
          value={precioMax}
          onChange={(e) => setPrecioMax(e.target.value)}
        />
        <input
          className="input"
          style={{ minWidth: 110 }}
          type="number"
          placeholder="Año"
          value={anio}
          onChange={(e) => setAnio(e.target.value)}
        />
        {(genero || precioMin || precioMax || anio) && (
          <button
            className="btn btn-ghost"
            onClick={() => { setGenero(''); setPrecioMin(''); setPrecioMax(''); setAnio('') }}
          >
            Limpiar filtros
          </button>
        )}
      </div>

      {error && <div className="error-msg">{error}</div>}

      {loading ? (
        <div className="loading-text">Cargando juegos...</div>
      ) : listaAMostrar.length === 0 ? (
        <div className="empty-state">No se encontraron juegos con esos criterios.</div>
      ) : (
        <div className="game-grid">
          {listaAMostrar.map((j) => (
            <GameCard
              key={j.id}
              juego={j}
              isFavorite={favoriteIds.has(j.id)}
              onToggleFavorite={onToggleFavorite}
              onOpenDetail={setJuegoSeleccionado}
              distancia={distanciaPorNombre?.get(j.nombre)}
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
