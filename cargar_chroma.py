import json
import chromadb
from sentence_transformers import SentenceTransformer

# Carga JSON
with open("biblioteca_steam_automatica.json", encoding="utf-8") as f:
    juegos = json.load(f)

# Conecta a ChromaDB
client = chromadb.HttpClient(host="localhost", port=8000)
collection = client.get_or_create_collection("juegos")

# Genera embeddings y los inserta
model = SentenceTransformer("all-MiniLM-L6-v2")

for juego in juegos:
    texto = f"{juego['nombre']} {' '.join(juego.get('generos', []))} {' '.join(juego.get('tags', []))}"
    embedding = model.encode(texto).tolist()

    collection.add(
        ids=[str(juego["id"])],
        embeddings=[embedding],
        documents=[texto],
        metadatas=[{"nombre": juego["nombre"], "id": juego["id"]}]
    )

print("Juegos cargados en ChromaDB")