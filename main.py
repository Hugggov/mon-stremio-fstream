import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
import uvicorn
import os
import json
import asyncio
import urllib.parse
import time

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DB_FILE = "database.json"
TMDB_API_KEY = "1863334617e9f45fcba4edb10d96639e"

# Chargement de la mémoire existante
if os.path.exists(DB_FILE):
    try:
        with open(DB_FILE, "r") as f:
            db = json.load(f)
    except: db = {"films_all": [], "series_all": []}
else:
    db = {"films_all": [], "series_all": []}

GENRES = ["Action", "Animation", "Aventure", "Comédie", "Crime", "Drame", "Fantastique", "Horreur", "Mystère", "Romance", "Science-Fiction", "Thriller"]

def get_real_target():
    """Trouve l'URL active (ex: fs18.lol)"""
    try:
        res = requests.get("https://fstream.net", headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
        soup = BeautifulSoup(res.text, 'html.parser')
        for link in soup.find_all('a', href=True):
            h = link['href']
            if any(ext in h for ext in [".lol", ".me", ".pw", ".tf"]) and "fstream.net" not in h:
                return h.strip('/')
    except: pass
    return "https://fs18.lol"

def get_imdb_id(title, is_movie=True):
    """Lien magique avec TMDB pour réveiller Wastream"""
    try:
        m_type = "movie" if is_movie else "tv"
        search_url = f"https://api.themoviedb.org/3/search/{m_type}?api_key={TMDB_API_KEY}&query={urllib.parse.quote(title)}&language=fr-FR"
        res = requests.get(search_url, timeout=5).json()
        if res.get("results"):
            tid = res["results"][0]["id"]
            ext_url = f"https://api.themoviedb.org/3/{m_type}/{tid}/external_ids?api_key={TMDB_API_KEY}"
            ext_res = requests.get(ext_url, timeout=5).json()
            return ext_res.get("imdb_id")
    except: pass
    return None

def update_worker():
    """Le robot qui travaille en arrière-plan"""
    global db
    target = get_real_target()
    print(f"--- Début du scan sur {target} ---")
    
    for cat in [("films", True, "films_all"), ("series", False, "series_all")]:
        path, is_movie, db_key = cat
        new_items = []
        
        for page in range(1, 31):
            try:
                url = f"{target}/{path}/page/{page}/"
                res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                if res.status_code != 200: break
                
                soup = BeautifulSoup(res.text, 'html.parser')
                elements = soup.select('.shortstory, .mov-item, .movie-item, div[class*="item"]')
                
                for el in elements:
                    link = el.find('a', href=True)
                    img = el.find('img')
                    if link and img:
                        name = (link.get('title') or img.get('alt') or "Sans titre").replace("en streaming", "").strip()
                        
                        # Si on l'a déjà en mémoire avec un ID IMDb, on ne demande pas à TMDB
                        existing = next((x for x in db[db_key] if x["name"] == name), None)
                        
                        if existing and existing["id"].startswith("tt"):
                            item_id = existing["id"]
                        else:
                            # Nouveau ou ID à trouver
                            imdb = get_imdb_id(name, is_movie)
                            item_id = imdb if imdb else f"fs_{hash(name)}"
                            time.sleep(0.15) # Sécurité pour TMDB
                        
                        poster = img.get('data-src') or img.get('src')
                        if poster and not poster.startswith('http'):
                            poster = target + (poster if poster.startswith('/') else '/' + poster)

                        item_obj = {
                            "id": item_id,
                            "type": "movie" if is_movie else "series",
                            "name": name,
                            "poster": poster,
                            "genres": [g for g in GENRES if g.lower() in el.text.lower()] or ["Divers"],
                            "description": f"FStream - Source {target}"
                        }
                        
                        if not any(x['name'] == name for x in new_items):
                            new_items.append(item_obj)
                            # MISE À JOUR EN DIRECT du compteur
                            db[db_key] = new_items 
                
                print(f"Page {page} ({path}) : {len(new_items)} items trouvés.")
                # Sauvegarde rapide toutes les 2 pages
                if page % 2 == 0:
                    with open(DB_FILE, "w") as f: json.dump(db, f)
                    
            except Exception as e:
                print(f"Erreur page {page}: {e}")
                continue

    print("--- Scan terminé avec succès ---")

@app.on_event("startup")
async def startup():
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_worker, 'interval', minutes=30)
    scheduler.start()
    asyncio.create_task(asyncio.to_thread(update_worker))

@app.get("/manifest.json")
async def manifest():
    return {
        "id": "org.fstream.progressive.v7",
        "version": "7.1.0",
        "name": "FStream : TMDB Debrid",
        "description": "Scan Progressif - Compatible Wastream",
        "resources": ["catalog"],
        "types": ["movie", "series"],
        "catalogs": [
            {"type": "movie", "id": "films_all", "name": "FStream : Films", "extra": [{"name": "genre", "options": GENRES}]},
            {"type": "series", "id": "series_all", "name": "FStream : Séries", "extra": [{"name": "genre", "options": GENRES}]}
        ]
    }

@app.get("/catalog/{type}/{id}.json")
@app.get("/catalog/{type}/{id}/{extra}.json")
async def get_catalog(type: str, id: str, extra: str = None):
    items = db.get(id, [])
    if extra and "genre=" in extra:
        g = extra.split("=")[1]
        items = [i for i in items if g in i.get("genres", [])]
    return {"metas": items}

@app.get("/")
async def status():
    return {"status": "Running", "films": len(db["films_all"]), "series": len(db["series_all"])}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
