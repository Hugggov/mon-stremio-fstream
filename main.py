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
    """Va sur la page stable pour trouver le lien éphémère du moment"""
    stable_page = "https://fstream.net"
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    try:
        print(f"--- Recherche du lien éphémère sur {stable_page} ---")
        res = requests.get(stable_page, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # On cherche le lien principal (souvent dans un bouton ou une bannière)
        # On exclut les liens vers les réseaux sociaux ou les liens internes connus
        links = soup.find_all('a', href=True)
        for link in links:
            url = link['href']
            # On cherche un lien qui contient 'fstream' mais qui n'est PAS fstream.net
            if "fstream" in url and "fstream.net" not in url:
                found = url.strip('/')
                print(f"🎯 URL Éphémère détectée : {found}")
                return found
        
        # Si aucun lien spécial n'est trouvé, on regarde si fstream.net redirige
        return res.url.strip('/')
    except Exception as e:
        print(f"Erreur de détection : {e}")
        return stable_page

def scrape_category(base_url, path, catalog_id, max_pages=20):
    """Scan les pages sur le lien éphémère trouvé"""
    temp_list = []
    is_series_type = "series" in catalog_id
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    
    for page in range(1, max_pages + 1):
        try:
            url = f"{base_url}/{path}/page/{page}/"
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code != 200: break
                
            soup = BeautifulSoup(res.text, 'html.parser')
            # Cible les blocs de films/séries
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
                        "type": "series" if is_series_type else "movie",
                        "name": name,
                        "poster": img,
                        "description": f"FStream - {catalog_id.upper()}"
                    })
        except: continue
    
    if temp_list:
        db[catalog_id] = temp_list
        with open(DB_FILE, "w") as f:
            json.dump(db, f)
        print(f"✅ {len(temp_list)} éléments ajoutés pour {catalog_id}")

def update_all_data():
    """Le cycle complet : détection + scan"""
    # 1. On trouve l'adresse éphémère
    current_mirror = get_ephemeral_url()
    
    # 2. On scanne les 6 catalogues demandés (20 pages chacun)
    # Les 'paths' sont ceux généralement utilisés par les sites de streaming
    scrape_category(current_mirror, "films", "fs_movie_all", 20)
    scrape_category(current_mirror, "series", "fs_series_all", 20)
    scrape_category(current_mirror, "science-fiction", "fs_sci_fi_movie", 20)
    scrape_category(current_mirror, "fantastique", "fs_fantastique_movie", 20)
    scrape_category(current_mirror, "science-fiction", "fs_sci_fi_series", 20)
    scrape_category(current_mirror, "fantastique", "fs_fantastique_series", 20)

@app.on_event("startup")
async def startup_event():
    # Planification automatique toutes les 2h
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_all_data, 'interval', hours=2)
    scheduler.start()
    # Lancement immédiat en tâche de fond
    asyncio.create_task(asyncio.to_thread(update_all_data))

@app.get("/")
async def root():
    """Page de contrôle pour toi sur navigateur"""
    return {
        "status": "Online",
        "url_ephemere_actuelle": get_ephemeral_url(),
        "total_titres": {k: len(v) for k, v in db.items()}
    }

@app.get("/manifest.json")
async def manifest():
    return {
        "id": "org.fstream.elite.chasseur.v20",
        "version": "20.7.0",
        "name": "FStream ELITE 20",
        "description": "Scan 20 pages via l'URL éphémère de fstream.net",
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
