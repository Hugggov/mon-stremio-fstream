import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
import uvicorn
import os
import json
import asyncio
import random

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "database.json"

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except: pass
    return {
        "fs_movie_all": [], "fs_series_all": [],
        "fs_sci_fi_movie": [], "fs_fantastique_movie": [],
        "fs_sci_fi_series": [], "fs_fantastique_series": []
    }

db = load_db()

def get_headers():
    """Génère des headers de navigation humaine pour éviter le blocage"""
    user_agents = [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]
    return {
        'User-Agent': random.choice(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }

def scrape_category(base_url, path, catalog_id, max_pages=20):
    temp_list = []
    is_series = "series" in path or "series" in catalog_id

    for page in range(1, max_pages + 1):
        try:
            url = f"{base_url}/{path}/page/{page}/"
            # On utilise une session pour garder les cookies comme un humain
            session = requests.Session()
            res = session.get(url, headers=get_headers(), timeout=15)
            
            if res.status_code != 200:
                print(f"Erreur {res.status_code} sur {url}")
                continue
                
            soup = BeautifulSoup(res.text, 'html.parser')
            items = soup.select('.shortstory')
            
            if not items:
                print(f"Aucun élément trouvé sur {url}. Le site a peut-être changé de structure.")
                break
                
            for item in items:
                t = item.find('h2')
                i = item.find('img')
                if t and i:
                    name = t.text.strip()
                    img = i['src']
                    if not img.startswith('http'): img = base_url + (img if img.startswith('/') else '/' + img)
                    
                    temp_list.append({
                        "id": f"fs_{name.replace(' ', '_')[:30]}",
                        "type": "series" if is_series else "movie",
                        "name": name,
                        "poster": img,
                        "description": f"FStream Elite - {catalog_id.replace('fs_', '').upper()}"
                    })
            # Petite pause entre les pages pour ne pas se faire repérer
            asyncio.run(asyncio.sleep(random.uniform(0.5, 1.5)))
        except Exception as e:
            print(f"Erreur : {e}")
            continue
    
    if temp_list:
        db[catalog_id] = temp_list
        with open(DB_FILE, "w") as f:
            json.dump(db, f)

def update_all_data():
    base = "https://fstream.net" # Fixé pour éviter les erreurs de redirection
    # Dossiers mis à jour selon fstream.net
    scrape_category(base, "films-streaming", "fs_movie_all", 20)
    scrape_category(base, "series-streaming", "fs_series_all", 20)
    scrape_category(base, "science-fiction-streaming", "fs_sci_fi_movie", 20)
    scrape_category(base, "fantastique-streaming", "fs_fantastique_movie", 20)
    scrape_category(base, "science-fiction-streaming", "fs_sci_fi_series", 20)
    scrape_category(base, "fantastique-streaming", "fs_fantastique_series", 20)

@app.on_event("startup")
async def startup_event():
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_all_data, 'interval', hours=2)
    scheduler.start()
    asyncio.create_task(asyncio.to_thread(update_all_data))

@app.get("/manifest.json")
async def manifest():
    return {
        "id": "org.fstream.elite.v20.stealth",
        "version": "20.2.0",
        "name": "FStream ELITE 20",
        "description": "Films & Séries (Mode Stealth) - 20 pages",
        "resources": ["catalog"],
        "types": ["movie", "series"],
        "catalogs": [
            {"type": "movie", "id": "fs_movie_all", "name": "FStream : Films"},
            {"type": "series", "id": "fs_series_all", "name": "FStream : Séries"},
            {"type": "movie", "id": "fs_sci_fi_movie", "name": "FStream : Films Sci-Fi"},
            {"type": "movie", "id": "fs_fantastique_movie", "name": "FStream : Films Fantastique"},
            {"type": "series", "id": "fs_sci_fi_series", "name": "FStream : Séries Sci-Fi"},
            {"type": "series", "id": "fs_fantastique_series", "name": "FStream : Séries Fantastique"}
        ]
    }

@app.get("/catalog/{type}/{id}.json")
async def catalog(type: str, id: str):
    return {"metas": db.get(id, [])}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
