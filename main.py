import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
import uvicorn
import os
import json
import asyncio

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fichier de sauvegarde pour ne jamais être vide au démarrage
DB_FILE = "database.json"

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {
        "fs_movie_all": [], "fs_series_all": [],
        "fs_sci_fi_movie": [], "fs_fantastique_movie": [],
        "fs_sci_fi_series": [], "fs_fantastique_series": []
    }

db = load_db()

def save_db():
    with open(DB_FILE, "w") as f:
        json.dump(db, f)

def get_live_url():
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get("https://fstream.net/", headers=headers, timeout=10)
        return r.url.strip('/')
    except:
        return "https://fstream.net"

def scrape_category(base_url, path, catalog_id, max_pages=20):
    temp_list = []
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    is_series = "series" in path or "series" in catalog_id

    for page in range(1, max_pages + 1):
        try:
            url = f"{base_url}/{path}/page/{page}/"
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code != 200: break
            soup = BeautifulSoup(res.text, 'html.parser')
            items = soup.select('.shortstory')
            if not items: break
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
                        "description": f"FStream - {catalog_id.upper()}"
                    })
        except: continue
    if temp_list:
        db[catalog_id] = temp_list
        save_db()

def update_all_data():
    base = get_live_url()
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
    # On lance le scan en tâche de fond pour mettre à jour la sauvegarde
    asyncio.create_task(asyncio.to_thread(update_all_data))

@app.get("/manifest.json")
async def manifest():
    return {
        "id": "org.fstream.elite.v20.fix",
        "version": "20.1.0",
        "name": "FStream ELITE 20",
        "description": "Films & Séries (Scan 20p) - Stable",
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
