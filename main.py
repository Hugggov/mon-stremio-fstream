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
db = {"fs_movie_all": [], "fs_series_all": [], "fs_sci_fi_movie": [], "fs_fantastique_movie": [], "fs_sci_fi_series": [], "fs_fantastique_series": []}

def get_ephemeral_url():
    """Analyse fstream.net pour trouver le lien vers le miroir de streaming"""
    stable_page = "https://fstream.net"
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
    try:
        res = requests.get(stable_page, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # On cherche le lien dans les boutons ou les textes mis en avant
        links = soup.find_all('a', href=True)
        for link in links:
            href = link['href'].strip('/')
            # On cherche un lien qui n'est pas fstream.net lui-même
            if "fstream" in href and "fstream.net" not in href:
                print(f"🎯 Miroir détecté : {href}")
                return href
        
        # Si rien n'est trouvé, on vérifie si la page a un bouton de redirection automatique
        return res.url.strip('/')
    except:
        return stable_page

def scrape_category(base_url, path, catalog_id, max_pages=20):
    temp_list = []
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    
    for page in range(1, max_pages + 1):
        try:
            url = f"{base_url}/{path}/page/{page}/"
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code != 200: break
            
            soup = BeautifulSoup(res.text, 'html.parser')
            # FStream utilise souvent ces classes pour ses films
            items = soup.select('.shortstory, .mov-item, .movie-item')
            if not items: break
            
            for item in items:
                t = item.find('h2') or item.find('div', class_='mov-t') or item.find('div', class_='title')
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
                        "description": f"FStream - {catalog_id.upper()}"
                    })
        except: continue
    
    if temp_list:
        db[catalog_id] = temp_list
        with open(DB_FILE, "w") as f: json.dump(db, f)
        print(f"✅ {len(temp_list)} titres trouvés pour {catalog_id}")

def update_all_data():
    target = get_ephemeral_url()
    # On définit les catégories exactes du site miroir
    cats = [
        ("films", "fs_movie_all"), 
        ("series", "fs_series_all"), 
        ("science-fiction", "fs_sci_fi_movie"), 
        ("fantastique", "fs_fantastique_movie"),
        ("series/science-fiction", "fs_sci_fi_series"),
        ("series/fantastique", "fs_fantastique_series")
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
        "mirror_utilisé": get_ephemeral_url(), 
        "titres_en_mémoire": {k: len(v) for k, v in db.items()}
    }

@app.get("/manifest.json")
async def manifest():
    return {
        "id": "org.fstream.radar.v20",
        "version": "20.9.0",
        "name": "FStream ELITE 20",
        "description": "Scan 20p sur URL éphémère",
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
