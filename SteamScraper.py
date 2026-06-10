# SteamScraper.py - sin API key
import requests
import json
import time

LIMITE_JUEGOS = 100
ARCHIVO_SALIDA = "biblioteca_steam_automatica.json"

def obtener_top_appids():
    print("-> Obteniendo juegos más populares de Steam...")
    url = "https://steamspy.com/api.php?request=top100in2weeks"
    try:
        res = requests.get(url).json()
        return list(res.keys())[:LIMITE_JUEGOS]
    except Exception as e:
        print(f"Error: {e}")
        return []

def get_game_details(app_id):
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

        return {
            "id": int(app_id),
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
    except:
        return None

def main():
    ids = obtener_top_appids()
    if not ids:
        print("No se pudieron obtener IDs.")
        return

    juegos = []
    guardados = 0
    saltados = 0

    print(f"-> Procesando {len(ids)} juegos...\n")

    for i, app_id in enumerate(ids):
        print(f"[{i+1}/{len(ids)}] ID: {app_id}...", end=" ", flush=True)
        detalle = get_game_details(app_id)
        if detalle:
            juegos.append(detalle)
            print(f"OK -> {detalle['nombre']}")
            guardados += 1
        else:
            print("SALTADO")
            saltados += 1
        time.sleep(1.5)

    with open(ARCHIVO_SALIDA, 'w', encoding='utf-8') as f:
        json.dump(juegos, f, ensure_ascii=False, indent=4)

    print(f"\n¡LISTO!")
    print(f"  Guardados : {guardados}")
    print(f"  Saltados  : {saltados}")
    print(f"  Archivo   : {ARCHIVO_SALIDA}")

if __name__ == "__main__":
    main()