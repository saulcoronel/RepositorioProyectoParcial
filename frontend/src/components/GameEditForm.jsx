import { useState } from 'react'
import * as api from '../api/client'

function listaDesdeTexto(txt) {
  return txt.split(',').map((s) => s.trim()).filter(Boolean)
}

function juegoAFormulario(juego) {
  return {
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
  }
}

const CAMPOS_VACIOS = {
  id: '', nombre: '', estudio: '', publisher: '', generos: '',
  tags: '', fecha_lanzamiento: '', precio: '', valoracion: '', peso_estimado: '',
}

/**
 * Formulario de crear/editar un juego. Si se pasa `juego`, arranca en modo edición
 * con los campos precargados; si no, arranca vacío en modo creación.
 * onSaved(juego) se llama tras un guardado exitoso.
 */
export default function GameEditForm({ juego, onSaved, onCancel }) {
  const modo = juego ? 'editar' : 'crear'
  const [form, setForm] = useState(juego ? juegoAFormulario(juego) : CAMPOS_VACIOS)
  const [mensaje, setMensaje] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  function actualizarCampo(campo, valor) {
    setForm((f) => ({ ...f, [campo]: valor }))
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
        const resultado = await api.createGame({
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
        setForm(CAMPOS_VACIOS)
        onSaved?.(resultado.juego)
      } else {
        const resultado = await api.updateGame(Number(form.id), {
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
        onSaved?.(resultado.juego)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
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
          {onCancel && (
            <button type="button" className="btn btn-ghost" onClick={onCancel}>
              Cancelar
            </button>
          )}
        </div>
      </form>
    </div>
  )
}
