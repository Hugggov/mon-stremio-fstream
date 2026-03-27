import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
import uvicorn
import os
import json
import asyncio
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "database.json"
db = {"fs_movie_all": [], "fs_series_all": [], "fs_sci_fi_movie": [], "fs_fantastique_movie": [], "fs_sci_fi_series": [], "fs_fantastique_series": []}

def get_ephemeral_url():
    """Détecte l'URL de type fsXX.lol sur fstream.net"""
    stable_page = "https://fstream.net"
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    try:
        res = requests.get(stable_page, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        links = soup.find_all('a', href=True)
        for link in links:
            href = link['href'].strip('/')
            # LOGIQUE : On cherche un lien qui contient ".lol", ".me", ".li" 
            # et qui commence souvent par 'fs' ou contient 'stream'
            if any(ext in href for ext in [".lol", ".me", ".pw", ".site"]) and "fstream.net" not in href:
                print(f"🎯 URL Éphémère détectée : {href}")
                return href
        
        # Secours : Si rien n'est trouvé, on tente de deviner si c'est fs18, fs19...
        return "https://fs18.lol" 
    except:
        return "https://fs18.lol"

def scrape_category(base_url, path, catalog_id, max_pages=20):
    temp_list = []
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    
    for page in range(1, max_pages + 1):
        try:
            url = f"{base_url}/{path}/page/{page}/"
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code != 200: break
            
            soup = BeautifulSoup(res.text, 'html.parser')
            # On cible les conteneurs de fstream (format .lol)
            items = soup.select('.shortstory, .mov-item, .movie-item')
            if not items: break
            
            for item in items:
                t = item.find(['h2', 'h3', 'div'], class_=['mov-t', 'title', 'tt']) or item.find('h2')
                i = item.find('img')
                if t and i:
                    name = t.text.strip()
                    img = i.get('data-src') or i.get('src')
                    if img and not img.startswith('http'): 
                        img = base_url + (img if img.startswith('/') else '/' + img)
                    
                    temp_list.append({
                        "id": f"fs_{name.replace(' ', '_')[:30]}",
                        "type": "series" if "series" in catalog_id else "movie",
                        "name": name,
                        "poster": img,
                        "description": f"FStream Elite - {catalog_id.replace('fs_', '').upper()}"
                    })
        except: continue
    
    if temp_list:
        db[catalog_id] = temp_list
        with open(DB_FILE, "w") as f: json.dump(db, f)

def update_all_data():
    target = get_ephemeral_url()
    print(f"🚀 Scan en cours sur : {target}")
    # On utilise les catégories standards observées sur fs18.lol
    cats = [
        ("films-streaming", "fs_movie_all"), 
        ("series-streaming", "fs_series_all"), 
        ("science-fiction-streaming", "fs_sci_fi_movie"), 
        ("fantastique-streaming", "fs_fantastique_movie"),
        ("science-fiction-streaming", "fs_sci_fi_series"),
        ("fantastique-streaming", "fs_fantastique_series")
    ]
    for path, cid in cats:
        scrape_category(target, path, cid, 20)

@app.on_event("startup")
async def startup_event():
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_all_data, 'interval', hours=2)
    scheduler.start()
    asyncio.create_task(asyncio.to_thread(update_all_data))

@app.get("/")
@app.head("/")
async def root():
    return {
        "status": "Online", 
        "cible_active": get_ephemeral_url(), 
        "films_trouves": {k: len(v) for k, v in db.items()}
    }

@app.get("/manifest.json")
async def manifest():
    return {
        "id": "org.fstream.lol.v20",
        "version": "21.1.0",
        "name": "FStream ELITE 20",
        "description": "Scan 20p sur URL type fsXX.lol",
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
