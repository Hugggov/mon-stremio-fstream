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

def get_ephemeral_url():
    """Analyse la page stable pour extraire l'URL éphémère du moment"""
    stable_url = "https://fstream.net"
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    try:
        print(f"Recherche de l'URL éphémère sur {stable_url}...")
        res = requests.get(stable_url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # On cherche tous les liens sur la page
        links = soup.find_all('a', href=True)
        for link in links:
            href = link['href']
            # On cherche un lien qui ressemble à un nouveau domaine (différent de fstream.net)
            # ou un lien mis en avant dans un encadré/bouton
            if "fstream" in href and href.strip('/') != stable_url:
                target = href.strip('/')
                print(f"🎯 URL Éphémère trouvée : {target}")
                return target
        
        # Si pas de lien trouvé, on vérifie si l'URL actuelle a changé par redirection
        return res.url.strip('/')
    except Exception as e:
        print(f"Erreur détection : {e}")
        return stable_url

def scrape_category(base_url, path, catalog_id, max_pages=20):
    temp_list = []
    is_series = "series" in catalog_id
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    
    for page in range(1, max_pages + 1):
        try:
            url = f"{base_url}/{path}/page/{page}/"
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code != 200: break
                
            soup = BeautifulSoup(res.text, 'html.parser')
            items = soup.select('.shortstory, .mov-item')
            if not items: break
                
            for item in items:
                t = item.find('h2') or item.find('div', class_='mov-t')
                i = item.find('img')
                if t and i:
                    name = t.text.strip()
                    img = i.get('data-src') or i.get('src')
                    if img and not img.startswith('http'): 
                        img = base_url + (img if img.startswith('/') else '/' + img)
                    
                    temp_list.append({
                        "id": f"fs_{name.replace(' ', '_')[:30]}",
                        "type": "series" if is_series else "movie",
                        "name": name,
                        "poster": img,
                        "description": f"Source: {base_url.split('//')[1]}"
                    })
        except: continue
    
    if temp_list:
        db[catalog_id] = temp_list
        with open(DB_FILE, "w") as f:
            json.dump(db, f)

def update_all_data():
    # 1. On va chercher l'URL éphémère affichée sur fstream.net
    target_url = get_ephemeral_url()
    
    # 2. On scanne les 20 pages sur ce nouveau domaine
    categories = [
        ("films", "fs_movie_all"),
        ("series", "fs_series_all"),
        ("science-fiction", "fs_sci_fi_movie"),
        ("fantastique", "fs_fantastique_movie"),
        ("science-fiction", "fs_sci_fi_series"),
        ("fantastique", "fs_fantastique_series")
    ]
    
    for path, cid in categories:
        scrape_category(target_url, path, cid, 20)
    
    print("✅ Mise à jour terminée sur l'URL éphémère.")

@app.on_event("startup")
async def startup_event():
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_all_data, 'interval', hours=2)
    scheduler.start()
    asyncio.create_task(asyncio.to_thread(update_all_data))

@app.get("/")
async def root():
    return {
        "status": "Online",
        "detected_ephemeral_url": get_ephemeral_url(),
        "stats": {k: len(v) for k, v in db.items()}
    }

@app.get("/manifest.json")
async def manifest():
    return {
        "id": "org.fstream.elite.auto.mirror",
        "version": "20.6.0",
        "name": "FStream ELITE 20",
        "description": "Scan Auto sur URL Éphémère (20p)",
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
