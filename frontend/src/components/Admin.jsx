import { useState } from 'react'
import * as api from '../api/client'
import GameCard from './GameCard.jsx'

const CAMPOS_VACIOS = {
  id: '',
  nombre: '',
  estudio: '',
  publisher: '',
  generos: '',
  tags: '',
  fecha_lanzamiento: '',
  precio: '',
  valoracion: '',
  peso_estimado: '',
}

function listaDesdeTexto(txt) {
  return txt.split(',').map((s) => s.trim()).filter(Boolean)
}

export default function Admin({ onDataChanged }) {
  const [modo, setModo] = useState('crear') // 'crear' | 'editar'
  const [form, setForm] = useState(CAMPOS_VACIOS)
  const [mensaje, setMensaje] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const [busquedaId, setBusquedaId] = useState('')
  const [juegoEncontrado, setJuegoEncontrado] = useState(null)

  function actualizarCampo(campo, valor) {
    setForm((f) => ({ ...f, [campo]: valor }))
  }

  function cargarParaEditar(juego) {
    setModo('editar')
    setJuegoEncontrado(juego)
    setForm({
      id: String(juego.id),
      nombre: juego.nombre || '',
      estudio: (juego.estudio || []).join(', '),
      publisher: (juego.publisher || []).join(', '),
      generos: (juego.generos || []).join(', '),
      tags: (juego.tags || []).join(', '),
      fecha_lanzamiento: juego.fecha_lanzamiento || '',
      precio: juego.precio || '',
      valoracion: juego.valoracion || '',
      peso_estimado: juego.peso_estimado || '',
    })
    setMensaje('')
    setError('')
  }

  async function handleBuscarPorId(e) {
    e.preventDefault()
    setError('')
    setMensaje('')
    if (!busquedaId.trim()) return
    setLoading(true)
    try {
      const data = await api.getGames({ limit: 500 })
      const encontrado = (data.juegos || []).find((j) => String(j.id) === busquedaId.trim())
      if (!encontrado) {
        setError('No se encontró ningún juego con ese ID en MongoDB.')
        setJuegoEncontrado(null)
      } else {
        cargarParaEditar(encontrado)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function limpiarFormulario() {
    setForm(CAMPOS_VACIOS)
    setModo('crear')
    setJuegoEncontrado(null)
    setMensaje('')
    setError('')
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setMensaje('')
    setLoading(true)
    try {
      if (modo === 'crear') {
        if (!form.id || !form.nombre) {
          throw new Error('El ID y el nombre son obligatorios.')
        }
        await api.createGame({
          id: Number(form.id),
          nombre: form.nombre,
          estudio: listaDesdeTexto(form.estudio),
          publisher: listaDesdeTexto(form.publisher),
          generos: listaDesdeTexto(form.generos),
          tags: listaDesdeTexto(form.tags),
          fecha_lanzamiento: form.fecha_lanzamiento || null,
          precio: form.precio || 'Gratis/N/A',
          valoracion: form.valoracion || 'Sin valoración',
          peso_estimado: form.peso_estimado || 'No especificado',
        })
        setMensaje(`Juego "${form.nombre}" creado correctamente.`)
        limpiarFormulario()
      } else {
        await api.updateGame(Number(form.id), {
          nombre: form.nombre || undefined,
          estudio: form.estudio ? listaDesdeTexto(form.estudio) : undefined,
          publisher: form.publisher ? listaDesdeTexto(form.publisher) : undefined,
          generos: form.generos ? listaDesdeTexto(form.generos) : undefined,
          tags: form.tags ? listaDesdeTexto(form.tags) : undefined,
          fecha_lanzamiento: form.fecha_lanzamiento || undefined,
          precio: form.precio || undefined,
          valoracion: form.valoracion || undefined,
          peso_estimado: form.peso_estimado || undefined,
        })
        setMensaje(`Juego "${form.nombre}" actualizado correctamente.`)
        limpiarFormulario()
      }
      onDataChanged?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleBorrar(juego) {
    if (!confirm(`¿Seguro que quieres borrar "${juego.nombre}"? Esta acción no se puede deshacer.`)) return
    setError('')
    setMensaje('')
    try {
      await api.deleteGame(juego.id)
      setMensaje(`Juego "${juego.nombre}" eliminado.`)
      if (juegoEncontrado?.id === juego.id) limpiarFormulario()
      onDataChanged?.()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div>
      <div className="panel" style={{ marginBottom: 20 }}>
        <div style={{ marginBottom: 10, fontSize: 13, color: 'var(--text-dim)' }}>
          Buscar juego existente por ID (Mongo) para editarlo o borrarlo:
        </div>
        <div className="search-box" style={{ marginBottom: 0 }}>
          <input
            className="input"
            placeholder="ID del juego (app_id de Steam)"
            value={busquedaId}
            onChange={(e) => setBusquedaId(e.target.value)}
          />
          <button className="btn" onClick={handleBuscarPorId}>Buscar</button>
        </div>

        {juegoEncontrado && (
          <div style={{ marginTop: 14 }}>
            <GameCard juego={juegoEncontrado} onEdit={cargarParaEditar} onDelete={handleBorrar} />
          </div>
        )}
      </div>

      <div className="panel">
        <div style={{ marginBottom: 14, fontSize: 15, fontWeight: 600, color: 'var(--text)' }}>
          {modo === 'crear' ? 'Insertar nuevo juego' : `Editando: ${form.nombre || form.id}`}
        </div>

        {mensaje && <div className="game-meta" style={{ color: 'var(--ok)', marginBottom: 12 }}>{mensaje}</div>}
        {error && <div className="error-msg">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-grid">
            <div className="form-field">
              <label>ID (app_id de Steam)</label>
              <input
                className="input"
                type="number"
                value={form.id}
                onChange={(e) => actualizarCampo('id', e.target.value)}
                disabled={modo === 'editar'}
                required
              />
            </div>
            <div className="form-field">
              <label>Nombre</label>
              <input className="input" value={form.nombre} onChange={(e) => actualizarCampo('nombre', e.target.value)} required />
            </div>
            <div className="form-field">
              <label>Estudio (separa con comas)</label>
              <input className="input" value={form.estudio} onChange={(e) => actualizarCampo('estudio', e.target.value)} />
            </div>
            <div className="form-field">
              <label>Publisher (separa con comas)</label>
              <input className="input" value={form.publisher} onChange={(e) => actualizarCampo('publisher', e.target.value)} />
            </div>
            <div className="form-field">
              <label>Géneros (separa con comas)</label>
              <input className="input" value={form.generos} onChange={(e) => actualizarCampo('generos', e.target.value)} />
            </div>
            <div className="form-field">
              <label>Tags (separa con comas)</label>
              <input className="input" value={form.tags} onChange={(e) => actualizarCampo('tags', e.target.value)} />
            </div>
            <div className="form-field">
              <label>Fecha de lanzamiento</label>
              <input className="input" value={form.fecha_lanzamiento} onChange={(e) => actualizarCampo('fecha_lanzamiento', e.target.value)} placeholder="ej: 15 mar, 2023" />
            </div>
            <div className="form-field">
              <label>Precio</label>
              <input className="input" value={form.precio} onChange={(e) => actualizarCampo('precio', e.target.value)} placeholder="ej: $199.00 MXN" />
            </div>
            <div className="form-field">
              <label>Valoración</label>
              <input className="input" value={form.valoracion} onChange={(e) => actualizarCampo('valoracion', e.target.value)} />
            </div>
            <div className="form-field">
              <label>Peso estimado</label>
              <input className="input" value={form.peso_estimado} onChange={(e) => actualizarCampo('peso_estimado', e.target.value)} />
            </div>
          </div>

          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn" type="submit" disabled={loading}>
              {loading ? 'Guardando...' : modo === 'crear' ? 'Crear juego' : 'Guardar cambios'}
            </button>
            {modo === 'editar' && (
              <button type="button" className="btn btn-ghost" onClick={limpiarFormulario}>
                Cancelar edición
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  )
}
