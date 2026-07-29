import { useEffect } from 'react'
import GameEditForm from './GameEditForm.jsx'
import { IconClose } from './icons.jsx'

export default function GameEditModal({ juego, onClose, onSaved }) {
  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose} aria-label="Cerrar"><IconClose size={16} /></button>
        <GameEditForm
          juego={juego}
          onCancel={onClose}
          onSaved={(juegoActualizado) => {
            onSaved?.(juegoActualizado)
            onClose()
          }}
        />
      </div>
    </div>
  )
}
