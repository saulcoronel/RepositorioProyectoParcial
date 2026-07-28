# Frontend - Biblioteca Steam (React + Vite)

SPA en React que consume el backend FastAPI (`main.py`) del proyecto de bases de datos.

## Requisitos
- Node.js 18+
- El backend corriendo (por defecto en `http://localhost:8080`, vía `docker compose up -d`)

## Instalación

```bash
npm install
cp .env.example .env
```

Si tu backend corre en otra URL, edita `.env`:
```
VITE_API_URL=http://localhost:8080
```

## Ejecutar en desarrollo

```bash
npm run dev
```

Abre la URL que muestre Vite (normalmente `http://localhost:5173`).

## Compilar para producción

```bash
npm run build
```

Esto genera la carpeta `dist/` con los archivos estáticos listos para servir.

## Estructura

```
src/
  api/client.js          -> todas las llamadas al backend (fetch + JWT)
  context/AuthContext.jsx -> maneja login/registro/sesión (guarda token en localStorage)
  components/
    AuthScreen.jsx        -> login y registro
    Dashboard.jsx         -> lista de juegos + filtros + búsqueda (nombre y semántica)
    Favorites.jsx         -> favoritos del usuario + búsqueda semántica sobre favoritos
    Admin.jsx             -> CRUD: crear, editar y borrar juegos en MongoDB
    GameCard.jsx          -> tarjeta reutilizable de un juego
  App.jsx                 -> arma las pestañas y el estado global de favoritos
```

## Requisitos de la entrega cubiertos

- **Dashboard con todos los juegos de MongoDB**: pestaña "Dashboard", usa `GET /games`.
- **Filtros y barra de búsqueda**: filtros de género, precio y año; búsqueda por nombre (`GET /games/search`).
- **Búsqueda semántica con ChromaDB**: selector "Semántica (ChromaDB)" en el Dashboard, usa `GET /games/similar`.
- **CRUD completo**: pestaña "Administración" (crear `POST /games`, editar `PUT /games/{id}`, borrar `DELETE /games/{id}`).
- **Favoritos por usuario autenticado**: estrella en cada tarjeta (`POST`/`DELETE /favorites`), pestaña "Mis favoritos" (`GET /favorites`).
- **Búsqueda semántica sobre favoritos**: barra de búsqueda dentro de "Mis favoritos", usa `GET /favorites/similar`.
