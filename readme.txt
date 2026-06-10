# uniat-game-library

Biblioteca de juegos de Steam con búsqueda por nombre y por concepto.

## Requisitos

- Docker Desktop
- Python 3.10+

## Instalación (solo la primera vez)

1. pip install -r requirements.txt
2. docker compose up -d --build
3. docker cp biblioteca_steam_automatica.json mongodb-steam:/tmp/juegos.json
4. docker exec mongodb-steam mongoimport --db steam --collection juegos --jsonArray --file /tmp/juegos.json
5. python cargar_chroma.py

## Uso diario

docker compose up -d

Abrir `index.html` en el navegador.

## Busqueda por endpoints
Ejemplos:
-http://localhost:8080/games/search?q=PUBG
-http://localhost:8080/games/similar?q=juegos de terror
-http://localhost:8080/health