import GameEditForm from './GameEditForm.jsx'

/**
 * Sección de Administración: solo para INSERTAR juegos nuevos que aún no existen
 * en la biblioteca (no hay una tarjeta que clickear para ellos todavía).
 * Para editar o borrar un juego existente, se hace desde su propio modal de
 * detalle (clic en la tarjeta, en el Dashboard o en Favoritos).
 */
export default function Admin({ onDataChanged }) {
  return (
    <div className="panel">
      <div className="game-meta" style={{ marginBottom: 16 }}>
        Para editar o borrar un juego que ya existe, ábrelo desde el Dashboard o
        Favoritos (clic en su tarjeta) y usa los botones "Editar" o "Borrar" ahí.
        Aquí solo se insertan juegos nuevos.
      </div>
      <GameEditForm onSaved={() => onDataChanged?.()} />
    </div>
  )
}
