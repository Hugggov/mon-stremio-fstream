import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
import uvicorn
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base de données en mémoire pour chaque catégorie
db = {
    "fs_movie_all": [],
    "fs_series_all": [],
    "fs_sci_fi": [],
    "fs_fantastique": []
}

def get_live_url():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get("https://fstream.net/", headers=headers, timeout=10)
        return r.url.strip('/')
    except:
        return "https://fstream.net"

def scrape_category(base_url, path, catalog_id):
    """Fonction robot pour scanner une catégorie précise"""
    temp_list = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # On scanne 50 pages pour chaque catégorie demandée
    for page in range(1, 51):
        try:
            url = f"{base_url}/{path}/page/{page}/"
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code != 200: break
            
            soup = BeautifulSoup(res.text, 'html.parser')
            for movie in soup.select('.shortstory'):
                title = movie.find('h2').text.strip()
                img = movie.find('img')['src']
                if not img.startswith('http'): img = base_url + img
                
                temp_list.append({
                    "id": f"fs_{title.replace(' ', '_')[:30]}",
                    "type": "movie" if "series" not in path else "series",
                    "name": title,
                    "poster": img,
                    "description": f"FStream - {catalog_id.replace('fs_', '').upper()}"
                })
        except:
            continue
    db[catalog_id] = temp_list

def update_all_data():
    """Mise à jour globale toutes les 2 heures"""
    base = get_live_url()
    print("Début du scan global...")
    
    # On définit les chemins exacts du site fstream
    scrape_category(base, "films-streaming", "fs_movie_all")
    scrape_category(base, "series-streaming", "fs_series_all")
    scrape_category(base, "science-fiction", "fs_sci_fi")
    scrape_category(base, "fantastique", "fs_fantastique")
    
    print("Mise à jour terminée !")

# Planificateur
scheduler = BackgroundScheduler()
scheduler.add_job(update_all_data, 'interval', hours=2)
scheduler.start()

@app.on_event("startup")
async def startup_event():
    update_all_data()

@app.get("/manifest.json")
async def manifest():
    return {
        "id": "org.fstream.ultraspeed.v4",
        "version": "4.0.0",
        "name": "FStream PRO+",
        "description": "Catalogue 50 pages - Inclus Sci-Fi & Fantastique",
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
    return {"metas": db.get(id, [])}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
