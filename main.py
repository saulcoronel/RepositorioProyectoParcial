# main.py
from fastapi import FastAPI, HTTPException, Query, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from pydantic import BaseModel
import chromadb
from sentence_transformers import SentenceTransformer
import requests as req_lib
import re
import redis
import json
import jwt
import time
import os
import uuid
import psycopg2
import bcrypt
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
from datetime import datetime, timedelta, timezone

# =================================================================
# CONFIGURACIÓN
# =================================================================
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = "steam"
COLLECTION_NAME = "juegos"
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = 8000
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = 6379
CACHE_TTL = 300  # segundos que se guarda cada consulta en cache

# --- Postgres (login) ---
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "steam_auth")
POSTGRES_USER = os.getenv("POSTGRES_USER", "steam")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "steam123")

# --- RustFS (objetos: imágenes y video de gameplay) ---
RUSTFS_ENDPOINT = os.getenv("RUSTFS_ENDPOINT", "http://localhost:9000")
RUSTFS_PUBLIC_ENDPOINT = os.getenv("RUSTFS_PUBLIC_ENDPOINT", "http://localhost:9000")
RUSTFS_ACCESS_KEY = os.getenv("RUSTFS_ACCESS_KEY", "rustfsadmin")
RUSTFS_SECRET_KEY = os.getenv("RUSTFS_SECRET_KEY", "rustfsadmin123")
RUSTFS_BUCKET = os.getenv("RUSTFS_BUCKET", "steam-media")

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
JWT_SECRET = os.getenv("JWT_SECRET", "clave-secreta-cambia-esto")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60
# =================================================================

app = FastAPI(
    title="Steam Game Library API",
    description="API para buscar y gestionar una biblioteca de juegos de Steam usando MongoDB y ChromaDB. "
                 "La mayoría de los endpoints requieren autenticación con token JWT. "
                 "Obtén tu token en /auth/login y úsalo en el botón 'Authorize' de Swagger.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

mongo_col = None
chroma_collection = None
model = None
redis_client = None
pg_conn = None
s3_client = None          # cliente interno (sube/baja objetos desde el backend)
s3_public_client = None   # cliente usado SOLO para firmar URLs que abre el navegador

security = HTTPBearer()


# =================================================================
# MODELOS
# =================================================================
class AddGameRequest(BaseModel):
    app_id: int


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    username: str
    password: str


class UpdateGameRequest(BaseModel):
    nombre: str | None = None
    estudio: list[str] | None = None
    publisher: list[str] | None = None
    valoracion: str | None = None
    generos: list[str] | None = None
    tags: list[str] | None = None
    fecha_lanzamiento: str | None = None
    precio: str | None = None
    peso_estimado: str | None = None


class CreateGameManualRequest(BaseModel):
    """Permite crear un juego a mano (sin depender de la API de Steam) para cumplir con
    el CRUD completo pedido en la entrega, además de /games/add que trae datos de Steam."""
    id: int
    nombre: str
    estudio: list[str] = []
    publisher: list[str] = []
    valoracion: str = "Sin valoración"
    generos: list[str] = []
    tags: list[str] = []
    fecha_lanzamiento: str | None = None
    precio: str = "Gratis/N/A"
    peso_estimado: str = "No especificado"


class FavoriteRequest(BaseModel):
    app_id: int


# =================================================================
# STARTUP
# =================================================================
@app.on_event("startup")
def startup():
    global mongo_col, chroma_collection, model, redis_client, pg_conn, s3_client, s3_public_client

    try:
        cliente = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
        cliente.admin.command("ping")
        mongo_col = cliente[DB_NAME][COLLECTION_NAME]
        print("Conectado a MongoDB")
    except ConnectionFailure:
        print("No se pudo conectar a MongoDB")

    try:
        chroma_client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        chroma_collection = chroma_client.get_or_create_collection("juegos")
        print("Conectado a ChromaDB")
    except Exception as e:
        print(f"No se pudo conectar a ChromaDB: {e}")

    try:
        redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        redis_client.ping()
        print("Conectado a Redis")
    except Exception as e:
        print(f"No se pudo conectar a Redis: {e}")
        redis_client = None

    try:
        pg_conn = psycopg2.connect(
            host=POSTGRES_HOST, port=POSTGRES_PORT,
            dbname=POSTGRES_DB, user=POSTGRES_USER, password=POSTGRES_PASSWORD
        )
        pg_conn.autocommit = True
        cur = pg_conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(100) NOT NULL,
                creado_en TIMESTAMP DEFAULT NOW()
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS favoritos (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) NOT NULL REFERENCES usuarios(username) ON DELETE CASCADE,
                app_id INTEGER NOT NULL,
                agregado_en TIMESTAMP DEFAULT NOW(),
                UNIQUE (username, app_id)
            );
        """)
        # Siembra el usuario admin (una sola vez) si la tabla está vacía
        cur.execute("SELECT COUNT(*) FROM usuarios")
        if cur.fetchone()[0] == 0:
            hash_admin = bcrypt.hashpw(ADMIN_PASSWORD.encode(), bcrypt.gensalt()).decode()
            cur.execute(
                "INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)",
                (ADMIN_USER, hash_admin)
            )
            print(f"Usuario admin '{ADMIN_USER}' creado en Postgres")
        cur.close()
        print("Conectado a Postgres")
    except Exception as e:
        print(f"No se pudo conectar a Postgres: {e}")
        pg_conn = None

    try:
        # signature_version="s3v4" es importante: sin esto, boto3 puede firmar con el
        # esquema legacy (v2), que RustFS no siempre acepta bien y causa
        # "AccessDenied" al abrir la URL firmada desde el navegador.
        s3_config = Config(signature_version="s3v4")

        s3_client = boto3.client(
            "s3",
            endpoint_url=RUSTFS_ENDPOINT,
            aws_access_key_id=RUSTFS_ACCESS_KEY,
            aws_secret_access_key=RUSTFS_SECRET_KEY,
            region_name="us-east-1",
            config=s3_config,
        )
        try:
            s3_client.head_bucket(Bucket=RUSTFS_BUCKET)
        except ClientError:
            s3_client.create_bucket(Bucket=RUSTFS_BUCKET)
            print(f"Bucket '{RUSTFS_BUCKET}' creado en RustFS")

        # Cliente aparte, firmado con el endpoint público, para generar URLs
        # que el navegador pueda abrir directamente (streaming de video, imágenes)
        s3_public_client = boto3.client(
            "s3",
            endpoint_url=RUSTFS_PUBLIC_ENDPOINT,
            aws_access_key_id=RUSTFS_ACCESS_KEY,
            aws_secret_access_key=RUSTFS_SECRET_KEY,
            region_name="us-east-1",
            config=s3_config,
        )
        print("Conectado a RustFS")
    except Exception as e:
        print(f"No se pudo conectar a RustFS: {e}")
        s3_client = None
        s3_public_client = None

    model = SentenceTransformer("all-MiniLM-L6-v2")
    print("Modelo cargado")


# =================================================================
# AUTENTICACIÓN
# =================================================================
def crear_token(username: str) -> str:
    expira = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {"sub": username, "exp": expira}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verificar_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="El token ha expirado, vuelve a iniciar sesión")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")


# =================================================================
# CACHE HELPERS
# =================================================================
def get_cache(key: str):
    if redis_client is None:
        return None
    try:
        data = redis_client.get(key)
        return json.loads(data) if data else None
    except Exception:
        return None


def set_cache(key: str, value: dict, ttl: int = CACHE_TTL):
    if redis_client is None:
        return
    try:
        redis_client.setex(key, ttl, json.dumps(value, ensure_ascii=False))
    except Exception:
        pass


# =================================================================
# AUTH ENDPOINTS
# =================================================================
@app.post(
    "/auth/login",
    response_model=TokenResponse,
    tags=["Autenticación"],
    summary="Inicia sesión y obtiene un token de acceso",
    description="Envía el usuario y contraseña configurados en el servidor para recibir un token JWT. "
                 "Este token debe usarse en el header Authorization de los demás endpoints."
)
def login(datos: LoginRequest):
    if pg_conn is None:
        raise HTTPException(status_code=503, detail="Postgres no conectado")

    cur = pg_conn.cursor()
    cur.execute("SELECT password_hash FROM usuarios WHERE username = %s", (datos.username,))
    row = cur.fetchone()
    cur.close()

    if not row or not bcrypt.checkpw(datos.password.encode(), row[0].encode()):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

    token = crear_token(datos.username)
    return {"access_token": token, "token_type": "bearer"}


@app.post(
    "/auth/register",
    tags=["Autenticación"],
    summary="Crea un nuevo usuario",
    description="Registra un usuario nuevo en Postgres con su contraseña encriptada (bcrypt)."
)
def register(datos: RegisterRequest):
    if pg_conn is None:
        raise HTTPException(status_code=503, detail="Postgres no conectado")
    if len(datos.password) < 4:
        raise HTTPException(status_code=400, detail="La contraseña es muy corta")

    hash_pw = bcrypt.hashpw(datos.password.encode(), bcrypt.gensalt()).decode()
    cur = pg_conn.cursor()
    try:
        cur.execute(
            "INSERT INTO usuarios (username, password_hash) VALUES (%s, %s)",
            (datos.username, hash_pw)
        )
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Ese usuario ya existe")
    finally:
        cur.close()

    return {"status": "ok", "username": datos.username}


# =================================================================
# RUTAS PÚBLICAS
# =================================================================
@app.get(
    "/health",
    tags=["General"],
    summary="Verifica el estado del servicio",
    description="Endpoint público. Verifica que MongoDB esté conectado y cuántos juegos hay en la base de datos. "
                 "No requiere autenticación."
)
def health():
    if mongo_col is None:
        raise HTTPException(status_code=503, detail="MongoDB no conectado")
    try:
        count = mongo_col.count_documents({})
        return {"status": "ok", "mongodb": "conectado", "juegos_en_db": count}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


# =================================================================
# RUTAS PROTEGIDAS
# =================================================================
@app.get(
    "/games",
    tags=["Juegos"],
    summary="Lista todos los juegos, con filtros opcionales",
    description="Requiere autenticación. Devuelve todos los juegos en MongoDB para el dashboard. "
                 "Permite filtrar por género, rango de precio (en el número que aparece en 'precio', "
                 "MXN) y año de lanzamiento. Soporta paginación con 'skip' y 'limit'."
)
def listar_games(genero: str | None = Query(None, description="Filtra por género exacto, ej: 'Acción'"),
                  precio_min: float | None = Query(None, description="Precio mínimo en MXN"),
                  precio_max: float | None = Query(None, description="Precio máximo en MXN"),
                  anio: int | None = Query(None, description="Año de lanzamiento, ej: 2023"),
                  skip: int = Query(0, ge=0),
                  limit: int = Query(100, ge=1, le=500),
                  usuario: str = Depends(verificar_token)):
    if mongo_col is None:
        raise HTTPException(status_code=503, detail="MongoDB no conectado")

    filtro = {}
    if genero:
        filtro["generos"] = {"$regex": f"^{genero}$", "$options": "i"}
    if anio:
        filtro["fecha_lanzamiento"] = {"$regex": str(anio)}

    juegos = list(mongo_col.find(filtro, {"_id": 0}).skip(skip).limit(limit))

    # El precio viene como texto formateado (ej. "$199.00 MXN" o "Gratis/N/A"),
    # así que el filtro numérico se aplica en Python extrayendo el número.
    if precio_min is not None or precio_max is not None:
        def precio_numero(j):
            txt = j.get("precio", "") or ""
            digitos = "".join(c for c in txt if c.isdigit() or c == ".")
            try:
                return float(digitos) if digitos else 0.0
            except ValueError:
                return 0.0

        juegos = [
            j for j in juegos
            if (precio_min is None or precio_numero(j) >= precio_min)
            and (precio_max is None or precio_numero(j) <= precio_max)
        ]

    total = mongo_col.count_documents(filtro)
    return {"total": total, "total_filtrado": len(juegos), "juegos": juegos}


@app.put(
    "/games/{app_id}",
    tags=["Juegos"],
    summary="Actualiza un juego existente",
    description="Requiere autenticación. Actualiza cualquier campo del juego en MongoDB y "
                 "regenera su embedding en ChromaDB para que la búsqueda semántica quede al día."
)
def actualizar_game(app_id: int, cambios: UpdateGameRequest, usuario: str = Depends(verificar_token)):
    if mongo_col is None:
        raise HTTPException(status_code=503, detail="MongoDB no conectado")

    juego_actual = mongo_col.find_one({"id": app_id})
    if not juego_actual:
        raise HTTPException(status_code=404, detail="El juego no existe")

    datos = {k: v for k, v in cambios.dict().items() if v is not None}
    if not datos:
        raise HTTPException(status_code=400, detail="No enviaste ningún campo para actualizar")

    mongo_col.update_one({"id": app_id}, {"$set": datos})
    juego_actualizado = mongo_col.find_one({"id": app_id}, {"_id": 0})

    # Regenerar embedding en ChromaDB con los datos actualizados
    if chroma_collection is not None and model is not None:
        texto = f"{juego_actualizado['nombre']} {' '.join(juego_actualizado.get('generos', []))} {' '.join(juego_actualizado.get('tags', []))}"
        embedding = model.encode(texto).tolist()
        chroma_collection.upsert(
            ids=[str(app_id)],
            embeddings=[embedding],
            documents=[texto],
            metadatas=[{"nombre": juego_actualizado["nombre"], "id": app_id}]
        )

    return {"status": "ok", "juego": juego_actualizado}


@app.delete(
    "/games/{app_id}",
    tags=["Juegos"],
    summary="Elimina un juego",
    description="Requiere autenticación. Borra el juego de MongoDB, su embedding en ChromaDB "
                 "y cualquier referencia a él en favoritos de todos los usuarios."
)
def eliminar_game(app_id: int, usuario: str = Depends(verificar_token)):
    if mongo_col is None:
        raise HTTPException(status_code=503, detail="MongoDB no conectado")

    resultado = mongo_col.delete_one({"id": app_id})
    if resultado.deleted_count == 0:
        raise HTTPException(status_code=404, detail="El juego no existe")

    if chroma_collection is not None:
        try:
            chroma_collection.delete(ids=[str(app_id)])
        except Exception:
            pass

    if pg_conn is not None:
        cur = pg_conn.cursor()
        cur.execute("DELETE FROM favoritos WHERE app_id = %s", (app_id,))
        cur.close()

    return {"status": "ok", "eliminado": app_id}


@app.post(
    "/games",
    tags=["Juegos"],
    summary="Crea un juego manualmente (sin depender de Steam)",
    description="Requiere autenticación. Inserta un juego directamente con los datos que envíes, "
                 "útil para pruebas o registros manuales. Para traer datos reales de Steam, usa "
                 "/games/add en su lugar."
)
def crear_game_manual(juego: CreateGameManualRequest, usuario: str = Depends(verificar_token)):
    if mongo_col is None:
        raise HTTPException(status_code=503, detail="MongoDB no conectado")
    if mongo_col.find_one({"id": juego.id}):
        raise HTTPException(status_code=409, detail="Ya existe un juego con ese id")

    doc = juego.dict()
    mongo_col.insert_one(doc)

    if chroma_collection is not None and model is not None:
        texto = f"{doc['nombre']} {' '.join(doc.get('generos', []))} {' '.join(doc.get('tags', []))}"
        embedding = model.encode(texto).tolist()
        chroma_collection.add(
            ids=[str(doc["id"])],
            embeddings=[embedding],
            documents=[texto],
            metadatas=[{"nombre": doc["nombre"], "id": doc["id"]}]
        )

    return {"status": "ok", "juego": {k: v for k, v in doc.items() if k != "_id"}}


@app.get(
    "/games/search",
    tags=["Juegos"],
    summary="Busca juegos por nombre",
    description="Requiere autenticación. Busca juegos en MongoDB cuyo nombre coincida parcial o totalmente "
                 "(insensible a mayúsculas). Los resultados se guardan en cache de Redis por 5 minutos."
)
def search_games(q: str = Query(..., description="Nombre o parte del nombre del juego"),
                  usuario: str = Depends(verificar_token)):
    if mongo_col is None:
        raise HTTPException(status_code=503, detail="MongoDB no conectado")

    cache_key = f"search:{q.lower()}"
    cached = get_cache(cache_key)
    if cached:
        cached["cache"] = True
        return cached

    resultados = list(mongo_col.find(
        {"nombre": {"$regex": q, "$options": "i"}},
        {"_id": 0}
    ))

    if not resultados:
        raise HTTPException(status_code=404, detail=f"No se encontraron juegos para '{q}'")

    respuesta = {"query": q, "total": len(resultados), "juegos": resultados, "cache": False}
    set_cache(cache_key, respuesta)
    return respuesta


@app.get(
    "/games/similar",
    tags=["Juegos"],
    summary="Busca juegos por concepto (búsqueda semántica)",
    description="Requiere autenticación. Convierte la consulta en un embedding y busca los 5 juegos "
                 "más cercanos en ChromaDB según similitud de significado. "
                 "Los resultados se guardan en cache de Redis por 5 minutos."
)
def similar_games(q: str = Query(..., description="Descripción o concepto, ej: 'juegos de terror'"),
                   usuario: str = Depends(verificar_token)):
    if chroma_collection is None:
        raise HTTPException(status_code=503, detail="ChromaDB no conectado")
    if model is None:
        raise HTTPException(status_code=503, detail="Modelo no cargado")

    cache_key = f"similar:{q.lower()}"
    cached = get_cache(cache_key)
    if cached:
        cached["cache"] = True
        return cached

    embedding = model.encode(q).tolist()
    resultados = chroma_collection.query(
        query_embeddings=[embedding],
        n_results=5,
        include=["metadatas", "distances"]
    )

    juegos = []
    for meta, distancia in zip(resultados["metadatas"][0], resultados["distances"][0]):
        juegos.append({"nombre": meta["nombre"], "distancia": round(distancia, 6)})

    respuesta = {"query": q, "resultados": juegos, "cache": False}
    set_cache(cache_key, respuesta)
    return respuesta


@app.get(
    "/favorites",
    tags=["Favoritos"],
    summary="Lista los favoritos del usuario logueado",
    description="Requiere autenticación. Devuelve los datos completos (desde MongoDB) de todos "
                 "los juegos que el usuario actual marcó como favorito."
)
def listar_favoritos(usuario: str = Depends(verificar_token)):
    if pg_conn is None:
        raise HTTPException(status_code=503, detail="Postgres no conectado")
    if mongo_col is None:
        raise HTTPException(status_code=503, detail="MongoDB no conectado")

    cur = pg_conn.cursor()
    cur.execute("SELECT app_id FROM favoritos WHERE username = %s ORDER BY agregado_en DESC", (usuario,))
    app_ids = [row[0] for row in cur.fetchall()]
    cur.close()

    if not app_ids:
        return {"total": 0, "juegos": []}

    juegos = list(mongo_col.find({"id": {"$in": app_ids}}, {"_id": 0}))
    # Mantener el orden de "agregado más reciente primero"
    juegos_por_id = {j["id"]: j for j in juegos}
    juegos_ordenados = [juegos_por_id[i] for i in app_ids if i in juegos_por_id]

    return {"total": len(juegos_ordenados), "juegos": juegos_ordenados}


@app.post(
    "/favorites",
    tags=["Favoritos"],
    summary="Agrega un juego a favoritos",
    description="Requiere autenticación. Marca un juego (por app_id) como favorito del usuario actual."
)
def agregar_favorito(datos: FavoriteRequest, usuario: str = Depends(verificar_token)):
    if pg_conn is None:
        raise HTTPException(status_code=503, detail="Postgres no conectado")
    if mongo_col is None:
        raise HTTPException(status_code=503, detail="MongoDB no conectado")
    if not mongo_col.find_one({"id": datos.app_id}):
        raise HTTPException(status_code=404, detail="Ese juego no existe en la base de datos")

    cur = pg_conn.cursor()
    try:
        cur.execute(
            "INSERT INTO favoritos (username, app_id) VALUES (%s, %s)",
            (usuario, datos.app_id)
        )
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Ese juego ya está en tus favoritos")
    finally:
        cur.close()

    return {"status": "ok", "app_id": datos.app_id}


@app.delete(
    "/favorites/{app_id}",
    tags=["Favoritos"],
    summary="Quita un juego de favoritos",
    description="Requiere autenticación. Elimina el juego (por app_id) de los favoritos del usuario actual."
)
def quitar_favorito(app_id: int, usuario: str = Depends(verificar_token)):
    if pg_conn is None:
        raise HTTPException(status_code=503, detail="Postgres no conectado")

    cur = pg_conn.cursor()
    cur.execute("DELETE FROM favoritos WHERE username = %s AND app_id = %s", (usuario, app_id))
    borrado = cur.rowcount
    cur.close()

    if borrado == 0:
        raise HTTPException(status_code=404, detail="Ese juego no estaba en tus favoritos")

    return {"status": "ok", "eliminado": app_id}


@app.get(
    "/favorites/similar",
    tags=["Favoritos"],
    summary="Busca por concepto dentro de los favoritos del usuario",
    description="Requiere autenticación. Igual que /games/similar, pero solo considera los juegos "
                 "que el usuario actual tiene marcados como favoritos. Útil para responder "
                 "'de mis favoritos, ¿cuáles son de terror?'."
)
def similar_en_favoritos(q: str = Query(..., description="Descripción o concepto, ej: 'juegos de terror'"),
                          usuario: str = Depends(verificar_token)):
    if pg_conn is None:
        raise HTTPException(status_code=503, detail="Postgres no conectado")
    if chroma_collection is None:
        raise HTTPException(status_code=503, detail="ChromaDB no conectado")
    if model is None:
        raise HTTPException(status_code=503, detail="Modelo no cargado")

    cur = pg_conn.cursor()
    cur.execute("SELECT app_id FROM favoritos WHERE username = %s", (usuario,))
    app_ids_favoritos = [str(row[0]) for row in cur.fetchall()]
    cur.close()

    if not app_ids_favoritos:
        return {"query": q, "resultados": []}

    embedding = model.encode(q).tolist()
    # ChromaDB permite filtrar por metadatos: solo busca entre los ids que son favoritos
    resultados = chroma_collection.query(
        query_embeddings=[embedding],
        n_results=min(10, len(app_ids_favoritos)),
        where={"id": {"$in": [int(i) for i in app_ids_favoritos]}},
        include=["metadatas", "distances"]
    )

    juegos = []
    if resultados["metadatas"] and resultados["metadatas"][0]:
        for meta, distancia in zip(resultados["metadatas"][0], resultados["distances"][0]):
            juegos.append({"nombre": meta["nombre"], "id": meta["id"], "distancia": round(distancia, 6)})

    return {"query": q, "resultados": juegos}


@app.post(
    "/mongo2chroma",
    tags=["Administración"],
    summary="Sincroniza MongoDB con ChromaDB",
    description="Requiere autenticación. Recorre todos los juegos en MongoDB, genera sus embeddings "
                 "y los carga en ChromaDB. Útil después de importar datos nuevos."
)
def mongo2chroma(usuario: str = Depends(verificar_token)):
    if mongo_col is None:
        raise HTTPException(status_code=503, detail="MongoDB no conectado")
    if chroma_collection is None:
        raise HTTPException(status_code=503, detail="ChromaDB no conectado")

    juegos = list(mongo_col.find({}, {"_id": 0}))
    if not juegos:
        raise HTTPException(status_code=404, detail="No hay juegos en MongoDB")

    cargados = 0
    saltados = 0

    for juego in juegos:
        try:
            texto = f"{juego['nombre']} {' '.join(juego.get('generos', []))} {' '.join(juego.get('tags', []))}"
            embedding = model.encode(texto).tolist()
            chroma_collection.add(
                ids=[str(juego["id"])],
                embeddings=[embedding],
                documents=[texto],
                metadatas=[{"nombre": juego["nombre"], "id": juego["id"]}]
            )
            cargados += 1
        except Exception:
            saltados += 1

    return {"status": "ok", "cargados": cargados, "saltados": saltados}


@app.get(
    "/steam/search",
    tags=["Steam"],
    summary="Busca juegos directamente en Steam",
    description="Requiere autenticación. Busca un juego por nombre en la tienda de Steam y "
                 "devuelve hasta 5 resultados con su App ID, para luego agregarlos con /games/add."
)
def steam_search(q: str = Query(..., description="Nombre del juego a buscar en Steam"),
                  usuario: str = Depends(verificar_token)):
    url = f"https://store.steampowered.com/api/storesearch/?term={q}&l=spanish&cc=MX"
    try:
        res = req_lib.get(url, timeout=15).json()
        items = res.get("items", [])[:5]
        return {"items": [{"id": i["id"], "name": i["name"]} for i in items]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/games/add",
    tags=["Juegos"],
    summary="Agrega un juego nuevo a la biblioteca",
    description="Requiere autenticación. Recibe un App ID de Steam, obtiene sus datos de la "
                 "Steam Store API y SteamSpy, lo guarda en MongoDB y genera su embedding en ChromaDB."
)
def add_game(req: AddGameRequest, usuario: str = Depends(verificar_token)):
    if mongo_col is None:
        raise HTTPException(status_code=503, detail="MongoDB no conectado")
    if mongo_col.find_one({"id": req.app_id}):
        raise HTTPException(status_code=409, detail="El juego ya existe en la base de datos.")

    store_url = f"https://store.steampowered.com/api/appdetails?appids={req.app_id}&l=spanish&cc=MX"
    spy_url = f"https://steamspy.com/api.php?request=appdetails&appid={req.app_id}"

    s_res = req_lib.get(store_url, timeout=15).json()
    time.sleep(1)
    spy_res = req_lib.get(spy_url, timeout=15).json()

    if not s_res or str(req.app_id) not in s_res or not s_res[str(req.app_id)]['success']:
        raise HTTPException(status_code=404, detail="No se encontró el juego en Steam.")

    data = s_res[str(req.app_id)]['data']
    juego = {
        "id": req.app_id,
        "nombre": data.get("name"),
        "estudio": data.get("developers", []),
        "publisher": data.get("publishers", []),
        "valoracion": f"{spy_res.get('positive', 0)} pos / {spy_res.get('negative', 0)} neg",
        "generos": [g['description'] for g in data.get("genres", [])],
        "tags": list(spy_res.get("tags", {}).keys())[:10],
        "fecha_lanzamiento": data.get("release_date", {}).get("date"),
        "precio": data.get("price_overview", {}).get("final_formatted", "Gratis/N/A"),
        "peso_estimado": "No especificado",
        "dlcs": []
    }

    mongo_col.insert_one(juego)

    texto = f"{juego['nombre']} {' '.join(juego.get('generos', []))} {' '.join(juego.get('tags', []))}"
    embedding = model.encode(texto).tolist()
    chroma_collection.add(
        ids=[str(juego["id"])],
        embeddings=[embedding],
        documents=[texto],
        metadatas=[{"nombre": juego["nombre"], "id": juego["id"]}]
    )

    # Descarga automáticamente screenshots + tráiler de Steam y los sube a RustFS,
    # reusando la respuesta de Steam que ya tenemos (sin pedirla dos veces).
    media_info = {"imagenes": 0, "videos": 0}
    if s3_client is not None:
        resultado = _sync_media_para_juego(req.app_id, data=data)
        if resultado:
            media_info = resultado

    return {"status": "ok", "nombre": juego["nombre"], "media_sincronizada": media_info}


# =================================================================
# RUSTFS: IMÁGENES Y VIDEO (catálogo + gameplay)
# =================================================================
TIPOS_VALIDOS = ("imagen", "video")


def _verificar_rustfs():
    if s3_client is None:
        raise HTTPException(status_code=503, detail="RustFS no conectado")


def _buscar_video_youtube(nombre_juego: str) -> str | None:
    """
    Busca el primer resultado de YouTube para '<nombre> official trailer' sin usar la
    YouTube Data API (no requiere API key). Hace scraping del HTML de resultados de
    búsqueda, igual que ya se hace con la tienda de Steam. Devuelve solo el videoId
    (para embeberlo luego como https://www.youtube.com/embed/{videoId}), o None si no
    se encontró nada.
    """
    try:
        query = req_lib.utils.quote(f"{nombre_juego} official trailer")
        url = f"https://www.youtube.com/results?search_query={query}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        resp = req_lib.get(url, headers=headers, timeout=10)
        resp.raise_for_status()

        match = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', resp.text)
        if match:
            return match.group(1)
        return None
    except Exception:
        return None


def _extraer_media_steam(data: dict, max_imagenes: int = 6, max_videos: int = 2):
    """De la respuesta de appdetails de Steam, saca URLs de screenshots.
    (El tráiler ya no se extrae de aquí: Steam dejó de exponer mp4 descargable en
    'movies' y ahora solo da streaming DASH/HLS, así que el video se busca aparte
    en YouTube con _buscar_video_youtube)."""
    imagenes = [
        s["path_full"] for s in data.get("screenshots", [])[:max_imagenes]
        if s.get("path_full")
    ]
    return imagenes, []


def _descargar_y_subir_a_rustfs(app_id: int, tipo: str, url: str) -> str:
    """Descarga un archivo desde una URL externa (CDN de Steam) y lo sube directo a RustFS."""
    resp = req_lib.get(url, stream=True, timeout=30)
    resp.raise_for_status()
    ext = os.path.splitext(url.split("?")[0])[1] or (".jpg" if tipo == "imagen" else ".mp4")
    key = f"{app_id}/{tipo}s/{uuid.uuid4().hex}{ext}"
    content_type = "image/jpeg" if tipo == "imagen" else "video/mp4"
    s3_client.upload_fileobj(resp.raw, RUSTFS_BUCKET, key, ExtraArgs={"ContentType": content_type})
    return key


def _sync_media_para_juego(app_id: int, data: dict = None):
    """
    Trae (o reusa) los datos de Steam de este juego, descarga sus screenshots a RustFS,
    y busca su tráiler en YouTube (Steam ya no expone un mp4 descargable para el tráiler,
    solo streaming DASH/HLS, así que el video se embebe directo desde YouTube usando su
    reproductor). Sobreescribe la media guardada para ese juego (para no ir acumulando
    duplicados si se llama varias veces). Devuelve None si el juego no existe en Steam.
    """
    if data is None:
        store_url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&l=spanish&cc=MX"
        s_res = req_lib.get(store_url, timeout=15).json()
        if not s_res or str(app_id) not in s_res or not s_res[str(app_id)]["success"]:
            # Aunque no haya datos en Steam, marcamos "intentado" para no reintentar
            # este mismo juego en cada llamada a /media/sync-all (evita un loop infinito
            # si el juego nunca va a tener media disponible).
            mongo_col.update_one(
                {"id": app_id},
                {"$set": {"media.imagenes": [], "media.youtube_video_id": None, "media.intentado": True}},
                upsert=False
            )
            return None
        data = s_res[str(app_id)]["data"]

    imagenes_urls, _ = _extraer_media_steam(data)
    nombre_juego = data.get("name", "")

    keys_imagenes = []
    for url in imagenes_urls:
        try:
            keys_imagenes.append(_descargar_y_subir_a_rustfs(app_id, "imagen", url))
        except Exception:
            pass  # si una imagen falla, seguimos con las demás

    youtube_video_id = _buscar_video_youtube(nombre_juego) if nombre_juego else None

    mongo_col.update_one(
        {"id": app_id},
        {"$set": {
            "media.imagenes": keys_imagenes,
            "media.youtube_video_id": youtube_video_id,
            "media.intentado": True,
        }},
        upsert=False
    )
    return {"imagenes": len(keys_imagenes), "youtube_video_id": youtube_video_id}



@app.post(
    "/games/{app_id}/sync-media",
    tags=["Media (RustFS)"],
    summary="Descarga automáticamente imágenes y video de Steam y los sube a RustFS",
    description="Requiere autenticación. No necesita que subas nada a mano: toma las capturas de "
                 "pantalla y el tráiler/gameplay que Steam ya tiene para ese juego, los descarga y "
                 "los guarda en RustFS. Sobreescribe la media anterior de ese juego."
)
def sync_media_juego(app_id: int, usuario: str = Depends(verificar_token)):
    _verificar_rustfs()
    if mongo_col is None:
        raise HTTPException(status_code=503, detail="MongoDB no conectado")
    if not mongo_col.find_one({"id": app_id}):
        raise HTTPException(status_code=404, detail="El juego no existe en la base de datos")

    resultado = _sync_media_para_juego(app_id)
    if resultado is None:
        raise HTTPException(status_code=404, detail="No se encontró información de este juego en Steam")

    return {"status": "ok", **resultado}


@app.post(
    "/media/sync-all",
    tags=["Media (RustFS)"],
    summary="Sincroniza automáticamente la media de todos los juegos que aún no tienen",
    description="Requiere autenticación. Recorre los juegos de MongoDB que no tienen imágenes "
                 "cargadas todavía y les descarga sus capturas y tráiler de Steam a RustFS. "
                 "Usa 'limite' para no saturar la API de Steam en una sola llamada (puedes llamarlo "
                 "varias veces hasta cubrir toda tu biblioteca)."
)
def sync_media_todos(limite: int = Query(20, ge=1, le=200), usuario: str = Depends(verificar_token)):
    _verificar_rustfs()
    if mongo_col is None:
        raise HTTPException(status_code=503, detail="MongoDB no conectado")

    juegos = list(mongo_col.find(
        {"$and": [
            {"$or": [
                {"media": {"$exists": False}},
                {"media.imagenes": {"$exists": False}},
                {"media.imagenes": {"$size": 0}},
            ]},
            {"media.intentado": {"$ne": True}},
        ]},
        {"_id": 0, "id": 1, "nombre": 1}
    ).limit(limite))

    detalle = []
    for j in juegos:
        try:
            resultado = _sync_media_para_juego(j["id"])
        except Exception as e:
            # Si un juego falla (timeout, error de red, etc.) lo marcamos como
            # intentado igual, para que no vuelva a trabar el loop de sincronización
            # en la siguiente llamada, y seguimos con el resto de la tanda.
            mongo_col.update_one(
                {"id": j["id"]},
                {"$set": {"media.imagenes": [], "media.youtube_video_id": None, "media.intentado": True}},
                upsert=False
            )
            detalle.append({"id": j["id"], "nombre": j["nombre"], "error": str(e)})
            time.sleep(0.8)
            continue

        time.sleep(0.8)  # margen para no saturar la API de Steam/SteamSpy (antes 1.5s)
        if resultado:
            detalle.append({"id": j["id"], "nombre": j["nombre"], **resultado})
        else:
            detalle.append({"id": j["id"], "nombre": j["nombre"], "error": "no encontrado en Steam"})

    return {"status": "ok", "total_procesados": len(detalle), "detalle": detalle}


@app.post(
    "/media/upload/{app_id}",
    tags=["Media (RustFS)"],
    summary="Sube una imagen o video de un juego",
    description="Requiere autenticación. Sube el archivo a RustFS (bucket S3-compatible) y guarda "
                 "la referencia dentro del documento del juego en MongoDB. 'tipo' debe ser 'imagen' o 'video'. "
                 "Los videos subidos como tipo 'video' son los que se muestran al presionar 'Reproducir'."
)
async def subir_media(app_id: int,
                       tipo: str = Form(...),
                       file: UploadFile = File(...),
                       usuario: str = Depends(verificar_token)):
    _verificar_rustfs()
    if mongo_col is None:
        raise HTTPException(status_code=503, detail="MongoDB no conectado")
    if tipo not in TIPOS_VALIDOS:
        raise HTTPException(status_code=400, detail="tipo debe ser 'imagen' o 'video'")
    if not mongo_col.find_one({"id": app_id}):
        raise HTTPException(status_code=404, detail="El juego no existe en la base de datos")

    extension = os.path.splitext(file.filename or "")[1]
    key = f"{app_id}/{tipo}s/{uuid.uuid4().hex}{extension}"

    try:
        s3_client.upload_fileobj(
            file.file,
            RUSTFS_BUCKET,
            key,
            ExtraArgs={"ContentType": file.content_type or "application/octet-stream"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error subiendo a RustFS: {e}")

    campo = "imagenes" if tipo == "imagen" else "videos"
    mongo_col.update_one(
        {"id": app_id},
        {"$push": {f"media.{campo}": key}},
        upsert=True
    )

    return {"status": "ok", "key": key, "tipo": tipo}


@app.get(
    "/media/download/{key:path}",
    tags=["Media (RustFS)"],
    summary="Descarga un objeto de RustFS",
    description="Requiere autenticación. Descarga (stream) el archivo original guardado en RustFS "
                 "a partir de su key (la misma que devuelve /media/upload o /games/{app_id}/media)."
)
def descargar_media(key: str, usuario: str = Depends(verificar_token)):
    _verificar_rustfs()
    try:
        obj = s3_client.get_object(Bucket=RUSTFS_BUCKET, Key=key)
    except ClientError:
        raise HTTPException(status_code=404, detail="Objeto no encontrado en RustFS")

    nombre_archivo = key.split("/")[-1]
    return StreamingResponse(
        obj["Body"].iter_chunks(),
        media_type=obj.get("ContentType", "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'}
    )


@app.get(
    "/games/{app_id}/media",
    tags=["Media (RustFS)"],
    summary="Lista las imágenes y videos de un juego (catálogo)",
    description="Requiere autenticación. Devuelve URLs firmadas (válidas 1 hora) para mostrar en el "
                 "navegador todas las imágenes y videos subidos para ese juego."
)
def media_del_juego(app_id: int, usuario: str = Depends(verificar_token)):
    _verificar_rustfs()
    if mongo_col is None:
        raise HTTPException(status_code=503, detail="MongoDB no conectado")

    juego = mongo_col.find_one({"id": app_id}, {"_id": 0, "media": 1})
    if not juego:
        raise HTTPException(status_code=404, detail="Juego no encontrado")

    media = juego.get("media", {})

    def firmar(key):
        return s3_public_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": RUSTFS_BUCKET, "Key": key},
            ExpiresIn=3600
        )

    return {
        "imagenes": [{"key": k, "url": firmar(k)} for k in media.get("imagenes", [])],
        "youtube_video_id": media.get("youtube_video_id"),
    }


@app.get(
    "/games/{app_id}/gameplay",
    tags=["Media (RustFS)"],
    summary="Obtiene la URL del video de gameplay para el botón Reproducir",
    description="Requiere autenticación. Devuelve una URL firmada del primer video de gameplay "
                 "subido para ese juego, lista para usarse en una etiqueta <video>."
)
def gameplay_del_juego(app_id: int, usuario: str = Depends(verificar_token)):
    if mongo_col is None:
        raise HTTPException(status_code=503, detail="MongoDB no conectado")

    juego = mongo_col.find_one({"id": app_id}, {"_id": 0, "media": 1, "nombre": 1})
    if not juego:
        raise HTTPException(status_code=404, detail="Juego no encontrado")

    youtube_video_id = juego.get("media", {}).get("youtube_video_id")
    if not youtube_video_id:
        raise HTTPException(status_code=404, detail="Este juego todavía no tiene video de gameplay")

    return {"nombre": juego.get("nombre"), "youtube_video_id": youtube_video_id}


@app.post(
    "/games/{app_id}/retry-video",
    tags=["Media (RustFS)"],
    summary="Reintenta buscar el video de YouTube para un juego",
    description="Requiere autenticación. Vuelve a intentar la búsqueda de tráiler en YouTube "
                 "para este juego (sin tocar sus imágenes). Útil cuando la primera búsqueda no "
                 "encontró nada, ya que YouTube a veces bloquea búsquedas de forma intermitente."
)
def reintentar_video(app_id: int, usuario: str = Depends(verificar_token)):
    if mongo_col is None:
        raise HTTPException(status_code=503, detail="MongoDB no conectado")

    juego = mongo_col.find_one({"id": app_id}, {"_id": 0, "nombre": 1})
    if not juego:
        raise HTTPException(status_code=404, detail="Juego no encontrado")

    youtube_video_id = _buscar_video_youtube(juego["nombre"])

    if youtube_video_id:
        mongo_col.update_one(
            {"id": app_id},
            {"$set": {"media.youtube_video_id": youtube_video_id}}
        )
        return {"status": "ok", "encontrado": True, "youtube_video_id": youtube_video_id}

    return {"status": "ok", "encontrado": False, "youtube_video_id": None}