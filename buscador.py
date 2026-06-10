import json
import requests
import time
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import chromadb
from sentence_transformers import SentenceTransformer

# =================================================================
# CONFIGURACIÓN
# =================================================================
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "steam"
COLLECTION_NAME = "juegos"
CHROMA_HOST = "localhost"
CHROMA_PORT = 8000
STEAM_API_KEY = "343F3FD068494C7A0ABC2AC8E2B6F2BF"
# =================================================================


def conectar_mongo():
    try:
        cliente = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
        cliente.admin.command("ping")
        col = cliente[DB_NAME][COLLECTION_NAME]
        print("Conectado a MongoDB")
        return col
    except ConnectionFailure:
        print("No se pudo conectar a MongoDB.")
        exit(1)


def conectar_chroma():
    try:
        client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        collection = client.get_or_create_collection("juegos")
        print("Conectado a ChromaDB")
        return collection
    except Exception as e:
        print(f"No se pudo conectar a ChromaDB: {e}")
        exit(1)


def buscar_por_nombre(col, texto):
    resultados = col.find(
        {"nombre": {"$regex": texto, "$options": "i"}},
        {"_id": 0}
    )
    return list(resultados)


def buscar_semantico(collection, model, query):
    embedding = model.encode(query).tolist()
    resultados = collection.query(
        query_embeddings=[embedding],
        n_results=5,
        include=["metadatas", "distances"]
    )
    juegos = []
    for meta, distancia in zip(resultados["metadatas"][0], resultados["distances"][0]):
        juegos.append({
            "nombre": meta["nombre"],
            "distancia": round(distancia, 6)
        })
    return juegos


def buscar_appid_por_nombre(nombre_juego):
    """Busca el AppID de un juego en Steam por nombre."""
    print(f"  Buscando '{nombre_juego}' en Steam...")
    url = f"https://store.steampowered.com/api/storesearch/?term={nombre_juego}&l=spanish&cc=MX"
    try:
        res = requests.get(url).json()
        items = res.get("items", [])
        if not items:
            return None, None

        # Muestra los primeros 5 resultados para que elijas
        print(f"\n  Resultados encontrados:\n")
        for i, item in enumerate(items[:5], 1):
            print(f"  {i}. {item['name']}  (ID: {item['id']})")

        opcion = input("\n  Elige un número (o 0 para cancelar): ").strip()
        if opcion == "0" or not opcion.isdigit():
            return None, None

        idx = int(opcion) - 1
        if 0 <= idx < len(items[:5]):
            return items[idx]["id"], items[idx]["name"]

        return None, None
    except Exception as e:
        print(f"  Error buscando en Steam: {e}")
        return None, None


def scrapear_juego(app_id):
    """Obtiene los detalles de un juego desde Steam y SteamSpy."""
    store_url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&l=spanish&cc=MX"
    spy_url = f"https://steamspy.com/api.php?request=appdetails&appid={app_id}"

    try:
        s_res = requests.get(store_url).json()
        time.sleep(1)
        spy_res = requests.get(spy_url).json()

        if not s_res or str(app_id) not in s_res or not s_res[str(app_id)]['success']:
            return None

        data = s_res[str(app_id)]['data']

        requisitos = data.get("pc_requirements", {}).get("minimum", "")
        peso = "No especificado"
        if "GB" in requisitos:
            partes = requisitos.split("GB")
            peso = partes[0].split()[-1] + " GB"

        juego_info = {
            "id": app_id,
            "nombre": data.get("name"),
            "estudio": data.get("developers", []),
            "publisher": data.get("publishers", []),
            "valoracion": f"{spy_res.get('positive', 0)} pos / {spy_res.get('negative', 0)} neg",
            "generos": [g['description'] for g in data.get("genres", [])],
            "tags": list(spy_res.get("tags", {}).keys())[:10],
            "fecha_lanzamiento": data.get("release_date", {}).get("date"),
            "precio": data.get("price_overview", {}).get("final_formatted", "Gratis/N/A"),
            "requerimientos": {
                "minimos": requisitos,
                "recomendados": data.get("pc_requirements", {}).get("recommended", "N/A")
            },
            "peso_estimado": peso,
            "dlcs": []
        }

        if "dlc" in data:
            for dlc_id in data["dlc"][:3]:
                d_url = f"https://store.steampowered.com/api/appdetails?appids={dlc_id}&cc=MX"
                d_res = requests.get(d_url).json()
                if d_res and str(dlc_id) in d_res and d_res[str(dlc_id)]['success']:
                    dd = d_res[str(dlc_id)]['data']
                    juego_info["dlcs"].append({
                        "nombre": dd.get("name"),
                        "fecha": dd.get("release_date", {}).get("date"),
                        "precio": dd.get("price_overview", {}).get("final_formatted", "N/A")
                    })
                time.sleep(1)

        return juego_info
    except Exception as e:
        print(f"  Error scrapeando juego: {e}")
        return None


def agregar_juego(col, chroma_collection, model):
    """Busca un juego en Steam, lo scrapea y lo agrega a MongoDB y ChromaDB."""
    nombre = input("  Nombre del juego a agregar: ").strip()
    if not nombre:
        return

    app_id, nombre_encontrado = buscar_appid_por_nombre(nombre)
    if not app_id:
        print("  Cancelado.\n")
        return

    # Verificar si ya existe en MongoDB
    if col.find_one({"id": app_id}):
        print(f"\n  '{nombre_encontrado}' ya existe en la base de datos.\n")
        return

    print(f"\n  Scrapeando '{nombre_encontrado}'...")
    juego = scrapear_juego(app_id)

    if not juego:
        print("  No se pudieron obtener los datos del juego.\n")
        return

    # Insertar en MongoDB
    col.insert_one(juego)
    print(f"Agregado a MongoDB")

    # Insertar en ChromaDB
    texto = f"{juego['nombre']} {' '.join(juego.get('generos', []))} {' '.join(juego.get('tags', []))}"
    embedding = model.encode(texto).tolist()
    chroma_collection.add(
        ids=[str(juego["id"])],
        embeddings=[embedding],
        documents=[texto],
        metadatas=[{"nombre": juego["nombre"], "id": juego["id"]}]
    )
    print(f"Agregado a ChromaDB")
    print(f"\n  '{juego['nombre']}' agregado exitosamente.\n")


def main():
    print("Cargando modelos y conexiones...\n")
    col = conectar_mongo()
    collection = conectar_chroma()
    model = SentenceTransformer("all-MiniLM-L6-v2")
    print()

    while True:
        print("=" * 50)
        print("  [1] Buscar por nombre exacto  (MongoDB)")
        print("  [2] Buscar por concepto       (ChromaDB)")
        print("  [3] Agregar juego")
        print("  [0] Salir")
        print("=" * 50)
        opcion = input("  Elige una opción: ").strip()

        if opcion == "0":
            print("bye")
            break

        elif opcion == "1":
            nombre = input("  Nombre del juego: ").strip()
            if not nombre:
                continue
            resultados = buscar_por_nombre(col, nombre)
            if not resultados:
                print(f"\n  Sin resultados para '{nombre}'.\n")
            else:
                print(f"\n  {len(resultados)} juego(s) encontrado(s):\n")
                for juego in resultados:
                    print(json.dumps(juego, ensure_ascii=False, indent=4))
                    print("-" * 50)

        elif opcion == "2":
            query = input("  Describe qué buscas: ").strip()
            if not query:
                continue
            resultados = buscar_semantico(collection, model, query)
            print(f"\n  Top 5 resultados para '{query}':\n")
            for i, juego in enumerate(resultados, 1):
                print(f"  {i}. {juego['nombre']}    distancia: {juego['distancia']}")
            print()

        elif opcion == "3":
            agregar_juego(col, collection, model)

        else:
            print("  Opción no válida.\n")


if __name__ == "__main__":
    main()