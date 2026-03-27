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

# Initialisation de la base de données
db = {"films_all": [], "series_all": []}
if os.path.exists(DB_FILE):
    try:
        with open(DB_FILE, "r") as f:
            db = json.load(f)
            print(f"Chargement réussi : {len(db['films_all'])} films en mémoire.")
    except: pass

GENRES = ["Action", "Animation", "Aventure", "Comédie", "Crime", "Drame", "Fantastique", "Horreur", "Mystère", "Romance", "Science-Fiction", "Thriller"]

def get_real_target():
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get("https://fstream.net", headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        for link in soup.find_all('a', href=True):
            h = link['href']
            if any(ext in h for ext in [".lol", ".me", ".pw", ".tf"]) and "fstream.net" not in h:
                return h.strip('/')
    except: pass
    return "https://fs18.lol"

def get_imdb_id(title, is_movie=True):
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
    global db
    target = get_real_target()
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    for cat_name, is_movie, db_key in [("films", True, "films_all"), ("series", False, "series_all")]:
        new_list = []
        for page in range(1, 31):
            try:
                url = f"{target}/{cat_name}/page/{page}/"
                res = requests.get(url, headers=headers, timeout=15)
                if res.status_code != 200: break
                
                soup = BeautifulSoup(res.text, 'html.parser')
                # Sélecteur large pour ne rien rater
                items = soup.find_all('a')
                
                for link in items:
                    img = link.find('img')
                    if not img: continue
                    
                    title = link.get('title') or img.get('alt') or ""
                    if len(title) < 3 or "streaming" in title.lower() and len(title) < 10: continue
                    title = title.replace("en streaming", "").strip()

                    # Vérifier si déjà en base pour gagner du temps
                    existing = next((x for x in db[db_key] if x["name"] == title), None)
                    
                    if existing and existing["id"].startswith("tt"):
                        item_obj = existing
                    else:
                        imdb = get_imdb_id(title, is_movie)
                        # CRUCIAL : Si pas d'IMDb, on met un ID temporaire propre
                        item_id = imdb if imdb else f"fs_{hash(title)}"
                        
                        poster = img.get('data-src') or img.get('src') or ""
                        if poster and not poster.startswith('http'):
                            poster = target + (poster if poster.startswith('/') else '/' + poster)

                        item_obj = {
                            "id": item_id,
                            "type": "movie" if is_movie else "series",
                            "name": title,
                            "poster": poster,
                            "genres": [g for g in GENRES if g.lower() in title.lower()] or ["Nouveauté"],
                            "description": f"FStream Ultimate - Source {target}"
                        }
                        time.sleep(0.2) # Anti-ban TMDB

                    if not any(x['name'] == title for x in new_list):
                        new_list.append(item_obj)
                
                # Sauvegarde à chaque page pour la sécurité
                db[db_key] = new_list
                with open(DB_FILE, "w") as f: json.dump(db, f)
                
            except Exception as e:
                print(f"Erreur page {page}: {e}")
                continue
    print(f"✅ Scan ULTIMATE Terminé : {len(db['films_all'])} Films")

@app.on_event("startup")
async def startup():
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_worker, 'interval', minutes=30)
    scheduler.start()
    asyncio.create_task(asyncio.to_thread(update_worker))

@app.get("/manifest.json")
async def manifest():
    return {
        "id": "org.fstream.ULTIMATE.v8",
        "version": "8.0.0",
        "name": "FStream : ULTIMATE",
        "description": "Version V8 - IDs IMDb Fixés pour Wastream",
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
    # Filtrage strict par type pour Stremio
    content = db.get(id, [])
    metas = [i for i in content if i["type"] == type]
    
    if extra and "genre=" in extra:
        g = extra.split("=")[1]
        metas = [i for i in metas if g in i.get("genres", [])]
        
    return {"metas": metas}

@app.get("/")
async def status():
    return {"status": "V8 Active", "films": len(db["films_all"]), "series": len(db["series_all"])}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    
