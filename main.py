import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
import uvicorn
import os
import asyncio

app = FastAPI()

# 1. PROTECTION ANTI-ERREUR (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base de données en mémoire
db = {
    "fs_movie_all": [],
    "fs_series_all": [],
    "fs_sci_fi": [],
    "fs_fantastique": []
}

def get_live_url():
    """Détecte l'URL active du site"""
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    try:
        r = requests.get("https://fstream.net/", headers=headers, timeout=10)
        return r.url.strip('/')
    except:
        return "https://fstream.net"

def scrape_category(base_url, path, catalog_id, max_pages=50):
    """Le robot qui extrait les films/séries"""
    temp_list = []
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    
    for page in range(1, max_pages + 1):
        try:
            url = f"{base_url}/{path}/page/{page}/"
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code != 200: break
            
            soup = BeautifulSoup(res.text, 'html.parser')
            # On cible les boîtes de films (shortstory)
            for movie in soup.select('.shortstory'):
                title_el = movie.find('h2')
                img_el = movie.find('img')
                
                if title_el and img_el:
                    title = title_el.text.strip()
                    img = img_el['src']
                    if not img.startswith('http'): img = base_url + img
                    
                    # On crée l'objet pour Stremio
                    temp_list.append({
                        "id": f"fs_{title.replace(' ', '_')[:30]}",
                        "type": "series" if "series" in path else "movie",
                        "name": title,
                        "poster": img,
                        "description": f"FStream - {catalog_id.replace('fs_', '').upper()}"
                    })
        except:
            continue
    
    # On met à jour la mémoire si on a trouvé des résultats
    if temp_list:
        db[catalog_id] = temp_list

def update_all_data():
    """Mise à jour complète (200 pages au total)"""
    base = get_live_url()
    print("--- DÉBUT DU SCAN GLOBAL (50 PAGES) ---")
    scrape_category(base, "films-streaming", "fs_movie_all")
    scrape_category(base, "series-streaming", "fs_series_all")
    scrape_category(base, "science-fiction", "fs_sci_fi")
    scrape_category(base, "fantastique", "fs_fantastique")
    print("--- SCAN TERMINÉ ---")

@app.on_event("startup")
async def startup_event():
    """Action au lancement du serveur sur Render"""
    base = get_live_url()
    print("Démarrage : Scan rapide (Page 1) pour affichage immédiat...")
    # On scanne juste la page 1 de chaque pour remplir le Home en 5 secondes
    scrape_category(base, "films-streaming", "fs_movie_all", max_pages=1)
    scrape_category(base, "series-streaming", "fs_series_all", max_pages=1)
    scrape_category(base, "science-fiction", "fs_sci_fi", max_pages=1)
    scrape_category(base, "fantastique", "fs_fantastique", max_pages=1)
    
    # On lance le robot qui fera les 50 pages toutes les 2 heures
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_all_data, 'interval', hours=2)
    scheduler.start()
    
    # On lance aussi un gros scan complet 50 pages tout de suite en arrière-plan
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, update_all_data)

@app.get("/")
async def root():
    return {"status": "Online", "counts": {k: len(v) for k, v in db.items()}}

@app.get("/manifest.json")
async def manifest():
    return {
        "id": "org.fstream.expert.final",
        "version": "5.0.0",
        "name": "FStream ELITE",
        "description": "Films, Séries, Sci-Fi, Fantastique (50 Pages)",
        "resources": ["catalog"],
        "types": ["movie", "series"],
        "catalogs": [
            {"type": "movie", "id": "fs_movie_all", "name": "FStream : Films"},
            {"type": "series", "id": "fs_series_all", "name": "FStream : Séries"},
            {"type": "movie", "id": "fs_sci_fi", "name": "FStream : Science-Fiction"},
            {"type": "movie", "id": "fs_fantastique", "name": "FStream : Fantastique"}
        ]
    }

@app.get("/catalog/{type}/{id}.json")
async def catalog(type: str, id: str):
    # Renvoie immédiatement ce qu'il y a en mémoire
    return {"metas": db.get(id, [])}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
