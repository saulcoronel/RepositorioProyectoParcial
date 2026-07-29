import { useEffect, useState } from 'react'
import * as api from '../api/client'
import { IconClose, IconRefresh, IconEdit, IconTrash } from './icons.jsx'

export default function GameDetailModal({ juego, onClose, onEdit, onDelete }) {
  const [media, setMedia] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [imagenActiva, setImagenActiva] = useState(0)
  const [reintentando, setReintentando] = useState(false)
  const [mensajeReintento, setMensajeReintento] = useState('')

  useEffect(() => {
    let cancelado = false
    setLoading(true)
    setError('')
    setMedia(null)
    setImagenActiva(0)
    setMensajeReintento('')

    api.getGameMedia(juego.id)
      .then((data) => { if (!cancelado) setMedia(data) })
      .catch((err) => { if (!cancelado) setError(err.message) })
      .finally(() => { if (!cancelado) setLoading(false) })

    return () => { cancelado = true }
  }, [juego.id])

  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  async function handleReintentarVideo() {
    setReintentando(true)
    setMensajeReintento('')
    try {
      const data = await api.retryVideo(juego.id)
      if (data.encontrado) {
        setMedia((m) => ({ ...m, youtube_video_id: data.youtube_video_id }))
        setMensajeReintento('¡Video encontrado!')
      } else {
        setMensajeReintento('No se encontró video esta vez, intenta de nuevo en unos segundos.')
      }
    } catch (err) {
      setMensajeReintento(err.message)
    } finally {
      setReintentando(false)
    }
  }

  const imagenes = media?.imagenes || []
  const youtubeId = media?.youtube_video_id

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose} aria-label="Cerrar"><IconClose size={16} /></button>

        <div className="modal-header">
          <h2 className="modal-title">{juego.nombre}</h2>
          <div className="game-meta">{(juego.estudio || []).join(', ') || 'Estudio desconocido'}</div>
          {(onEdit || onDelete) && (
            <div className="modal-crud-actions">
              {onEdit && (
                <button className="btn btn-small btn-ghost" onClick={() => onEdit(juego)}>
                  <IconEdit size={13} /> Editar
                </button>
              )}
              {onDelete && (
                <button className="btn btn-small btn-danger" onClick={() => onDelete(juego)}>
                  <IconTrash size={13} /> Borrar
                </button>
              )}
            </div>
          )}
        </div>

        {loading && <div className="loading-text">Cargando imágenes y video...</div>}
        {error && <div className="error-msg">{error}</div>}

        {!loading && !error && imagenes.length === 0 && !youtubeId && (
          <div className="empty-state">
            Este juego todavía no tiene imágenes ni video sincronizados.
            Usa "Sincronizar imágenes y video" en el Dashboard.
          </div>
        )}

        {youtubeId && (
          <div className="modal-video-wrap">
            <iframe
              className="modal-video"
              src={`https://www.youtube.com/embed/${youtubeId}`}
              title={`Tráiler de ${juego.nombre}`}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
            />
          </div>
        )}

        {!loading && !youtubeId && (
          <div className="retry-video-bar">
            <button className="btn btn-ghost btn-small" onClick={handleReintentarVideo} disabled={reintentando}>
              <IconRefresh size={13} className={reintentando ? 'spin' : ''} />
              {reintentando ? 'Buscando video...' : 'Reintentar video'}
            </button>
            {mensajeReintento && <span className="sync-status">{mensajeReintento}</span>}
          </div>
        )}

        {imagenes.length > 0 && (
          <>
            <div className="modal-main-image-wrap">
              <img
                className="modal-main-image"
                src={imagenes[imagenActiva]?.url}
                alt={`${juego.nombre} - captura ${imagenActiva + 1}`}
              />
            </div>
            {imagenes.length > 1 && (
              <div className="modal-thumbs">
                {imagenes.map((img, i) => (
                  <img
                    key={img.key}
                    src={img.url}
                    alt={`miniatura ${i + 1}`}
                    className={`modal-thumb ${i === imagenActiva ? 'active' : ''}`}
                    onClick={() => setImagenActiva(i)}
                  />
                ))}
              </div>
            )}
          </>
        )}

        <div className="modal-details">
          {juego.generos?.length > 0 && (
            <div className="game-tags">
              {juego.generos.map((g) => <span className="game-tag" key={g}>{g}</span>)}
            </div>
          )}
          <div className="game-meta" style={{ marginTop: 8 }}>{juego.fecha_lanzamiento}</div>
          <div className="game-price" style={{ marginTop: 4 }}>{juego.precio}</div>
        </div>
      </div>
    </div>
  )
}
