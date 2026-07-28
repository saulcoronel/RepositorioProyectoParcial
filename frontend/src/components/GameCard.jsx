import { useState } from 'react'
import { IconStar, IconEdit, IconTrash } from './icons.jsx'

export default function GameCard({
  juego,
  isFavorite,
  onToggleFavorite,
  onEdit,
  onDelete,
  onOpenDetail,
  distancia,
}) {
  const [portadaFallo, setPortadaFallo] = useState(false)
  const urlPortada = `https://cdn.akamai.steamstatic.com/steam/apps/${juego.id}/header.jpg`

  return (
    <div
      className="game-card"
      onClick={() => onOpenDetail?.(juego)}
      role={onOpenDetail ? 'button' : undefined}
      tabIndex={onOpenDetail ? 0 : undefined}
    >
      {!portadaFallo && (
        <div className="game-cover-wrap">
          <img
            className="game-cover"
            src={urlPortada}
            alt={`Portada de ${juego.nombre}`}
            loading="lazy"
            onError={() => setPortadaFallo(true)}
          />
        </div>
      )}

      <div className="game-title">{juego.nombre}</div>
      <div className="game-meta">
        {(juego.estudio || []).join(', ') || 'Estudio desconocido'}
      </div>
      <div className="game-meta">{juego.fecha_lanzamiento || 'Fecha desconocida'}</div>

      {juego.generos?.length > 0 && (
        <div className="game-tags">
          {juego.generos.slice(0, 4).map((g) => (
            <span className="game-tag" key={g}>{g}</span>
          ))}
        </div>
      )}

      <div className="game-price">{juego.precio || 'N/A'}</div>

      {typeof distancia === 'number' && (
        <div className="similarity-badge">similitud (distancia): {distancia}</div>
      )}

      <div className="game-actions">
        {onToggleFavorite && (
          <button
            className="btn btn-small btn-ghost"
            onClick={(e) => { e.stopPropagation(); onToggleFavorite(juego) }}
          >
            <IconStar size={14} filled={isFavorite} className={`star-icon ${isFavorite ? 'active' : ''}`} />
            {isFavorite ? 'Quitar' : 'Favorito'}
          </button>
        )}
        {onEdit && (
          <button
            className="btn btn-small btn-ghost"
            onClick={(e) => { e.stopPropagation(); onEdit(juego) }}
          >
            <IconEdit size={13} /> Editar
          </button>
        )}
        {onDelete && (
          <button
            className="btn btn-small btn-danger"
            onClick={(e) => { e.stopPropagation(); onDelete(juego) }}
          >
            <IconTrash size={13} /> Borrar
          </button>
        )}
      </div>
    </div>
  )
}