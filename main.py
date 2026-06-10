from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from pydantic import BaseModel
import chromadb
from sentence_transformers import SentenceTransformer
import requests as req_lib
import time
import os

# =================================================================
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = "steam"
COLLECTION_NAME = "juegos"
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = 8000
# =================================================================

app = FastAPI(title="Steam Game Library")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

mongo_col = None
chroma_collection = None
model = None


class AddGameRequest(BaseModel):
    app_id: int


@app.on_event("startup")
def startup():
    global mongo_col, chroma_collection, model

    try:
        cliente = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
        cliente.admin.command("ping")
        mongo_col = cliente[DB_NAME][COLLECTION_NAME]
        print("✔ Conectado a MongoDB")
    except ConnectionFailure:
        print("✘ No se pudo conectar a MongoDB")

    try:
        chroma_client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        chroma_collection = chroma_client.get_or_create_collection("juegos")
        print("✔ Conectado a ChromaDB")
    except Exception as e:
        print(f"✘ No se pudo conectar a ChromaDB: {e}")

    model = SentenceTransformer("all-MiniLM-L6-v2")
    print("✔ Modelo cargado")


@app.get("/health")
def health():
    if mongo_col is None:
        raise HTTPException(status_code=503, detail="MongoDB no conectado")
    try:
        count = mongo_col.count_documents({})
        return {"status": "ok", "mongodb": "conectado", "juegos_en_db": count}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/games/search")
def search_games(q: str = Query(...)):
    if mongo_col is None:
        raise HTTPException(status_code=503, detail="MongoDB no conectado")
    resultados = list(mongo_col.find(
        {"nombre": {"$regex": q, "$options": "i"}},
        {"_id": 0}
    ))
    if not resultados:
        raise HTTPException(status_code=404, detail=f"No se encontraron juegos para '{q}'")
    return {"query": q, "total": len(resultados), "juegos": resultados}


@app.get("/games/similar")
def similar_games(q: str = Query(...)):
    if chroma_collection is None:
        raise HTTPException(status_code=503, detail="ChromaDB no conectado")
    if model is None:
        raise HTTPException(status_code=503, detail="Modelo no cargado")
    embedding = model.encode(q).tolist()
    resultados = chroma_collection.query(
        query_embeddings=[embedding],
        n_results=5,
        include=["metadatas", "distances"]
    )
    juegos = []
    for meta, distancia in zip(resultados["metadatas"][0], resultados["distances"][0]):
        juegos.append({"nombre": meta["nombre"], "distancia": round(distancia, 6)})
    return {"query": q, "resultados": juegos}


@app.post("/mongo2chroma")
def mongo2chroma():
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


@app.get("/steam/search")
def steam_search(q: str = Query(...)):
    url = f"https://store.steampowered.com/api/storesearch/?term={q}&l=spanish&cc=MX"
    try:
        res = req_lib.get(url).json()
        items = res.get("items", [])[:5]
        return {"items": [{"id": i["id"], "name": i["name"]} for i in items]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/games/add")
def add_game(req: AddGameRequest):
    if mongo_col is None:
        raise HTTPException(status_code=503, detail="MongoDB no conectado")
    if mongo_col.find_one({"id": req.app_id}):
        raise HTTPException(status_code=409, detail="El juego ya existe en la base de datos.")

    store_url = f"https://store.steampowered.com/api/appdetails?appids={req.app_id}&l=spanish&cc=MX"
    spy_url = f"https://steamspy.com/api.php?request=appdetails&appid={req.app_id}"

    s_res = req_lib.get(store_url).json()
    time.sleep(1)
    spy_res = req_lib.get(spy_url).json()

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

    return {"status": "ok", "nombre": juego["nombre"]}