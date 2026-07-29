# uniat-game-library

Biblioteca de juegos de Steam con búsqueda por nombre, por concepto (ChromaDB),
favoritos, CRUD completo e imágenes/video por juego. Backend en FastAPI y frontend en React.

## Requisitos

- Docker Desktop
- Python 3.10+
- Node.js 18+

## Instalación (solo la primera vez)

## Instalación (solo la primera vez)

1. `cp .env.example .env` y edita `.env` con tu propia contraseña de administrador y tu propio `JWT_SECRET`
2. `pip install -r requirements.txt`
3. `docker compose up -d --build`
4. `docker cp biblioteca_steam_automatica.json mongodb-steam:/tmp/juegos.json`
5. `docker exec mongodb-steam mongoimport --db steam --collection juegos --jsonArray --file /tmp/juegos.json`
6. `python cargar_chroma.py`
7. `cd frontend && npm install && cp .env.example .env`

> En Windows, si `python` o `pip` no se reconocen como comando, usa `py` y `py -m pip` en su lugar.

## Uso diario

```
docker compose up -d
cd frontend && npm run dev
```

Abrir `http://localhost:5173` en el navegador.

## Sincronizar imágenes y video (opcional)

Los juegos no traen imágenes/video automáticamente al importarlos. Desde el Dashboard, usar el botón **"Sincronizar imágenes y video"**, o llamar directo al endpoint:

```
POST http://localhost:8080/media/sync-all?limite=20
```

## Busqueda por endpoints
Ejemplos:
- http://localhost:8080/games/search?q=PUBG
- http://localhost:8080/games/similar?q=juegos de terror
- http://localhost:8080/favorites/similar?q=juegos de terror
- http://localhost:8080/health

## Seguridad

- El archivo `.env` nunca se sube al repo (está en `.gitignore`); solo `.env.example` sí.
- Las contraseñas por defecto en `docker-compose.yml` son solo para desarrollo local.