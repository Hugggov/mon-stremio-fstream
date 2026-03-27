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

DB_FILE = "database.json"
db = {"fs_movie_all": [], "fs_series_all": [], "fs_sci_fi_movie": [], "fs_fantastique_movie": []}

def get_ephemeral_url():
    """Tente de trouver le miroir sur fstream.net ou utilise fs18.lol"""
    try:
        res = requests.get("https://fstream.net", headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
        soup = BeautifulSoup(res.text, 'html.parser')
        for link in soup.find_all('a', href=True):
            href = link['href']
            if ("fs18" in href or ".lol" in href) and "fstream.net" not in href:
                return href.strip('/')
    except: pass
    return "https://fs18.lol"

def scrape_category(base_url, path, catalog_id):
    temp_list = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    # On scanne 10 pages pour commencer
    for page in range(1, 11):
        try:
            url = f"{base_url}/{path}/page/{page}/"
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code != 200: break
            
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # --- STRATÉGIE DE SCAN LARGE ---
            # On cherche tous les liens qui contiennent une image (structure classique des posters)
            for a in soup.find_all('a', href=True):
                img = a.find('img')
                # Un titre est souvent présent dans l'attribut 'title' ou 'alt'
                title = a.get('title') or (img.get('alt') if img else None)
                
                if img and title and len(title) > 2:
                    poster = img.get('data-src') or img.get('src')
                    if poster and not poster.startswith('http'):
                        poster = base_url + (poster if poster.startswith('/') else '/' + poster)
                    
                    # On nettoie le titre
                    clean_name = title.replace("en streaming", "").replace("Streaming", "").strip()
                    
                    if not any(item['name'] == clean_name for item in temp_list):
                        temp_list.append({
                            "id": f"fs_{hash(clean_name)}",
                            "type": "series" if "series" in catalog_id else "movie",
                            "name": clean_name,
                            "poster": poster,
                            "description": f"FStream Elite - {catalog_id.upper()}"
                        })
        except: continue
    
    if temp_list:
        db[catalog_id] = temp_list
        with open(DB_FILE, "w") as f: json.dump(db, f)
        print(f"✅ {len(temp_list)} titres capturés pour {catalog_id}")

def update_all_data():
    target = get_ephemeral_url()
    # On teste les chemins les plus courants sur ces miroirs
    cats = [
        ("films", "fs_movie_all"), 
        ("series", "fs_series_all"), 
        ("films-de-science-fiction", "fs_sci_fi_movie"), 
        ("films-fantastique", "fs_fantastique_movie")
    ]
    for path, cid in cats:
        scrape_category(target, path, cid)

@app.on_event("startup")
async def startup_event():
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_all_data, 'interval', hours=2)
    scheduler.start()
    asyncio.create_task(asyncio.to_thread(update_all_data))

@app.get("/")
@app.head("/")
async def root():
    return {"status": "Online", "target": get_ephemeral_url(), "stats": {k: len(v) for k, v in db.items()}}

@app.get("/manifest.json")
async def manifest():
    return {
        "id": "org.fstream.final.lynx",
        "version": "23.0.0",
        "name": "FStream ELITE 20",
        "description": "Scanner Ultra-Large fsXX.lol",
        "resources": ["catalog"],
        "types": ["movie", "series"],
        "catalogs": [
            {"type": "movie", "id": "fs_movie_all", "name": "FStream : Films"},
            {"type": "series", "id": "fs_series_all", "name": "FStream : Séries"},
            {"type": "movie", "id": "fs_sci_fi_movie", "name": "FStream : Sci-Fi"},
            {"type": "movie", "id": "fs_fantastique_movie", "name": "FStream : Fantastique"}
        ]
    }

@app.get("/catalog/{type}/{id}.json")
async def catalog(type: str, id: str):
    return {"metas": db.get(id, [])}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
