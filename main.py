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

if os.path.exists(DB_FILE):
    with open(DB_FILE, "r") as f:
        db = json.load(f)
else:
    db = {"films_all": [], "series_all": []}

GENRES = ["Action", "Animation", "Aventure", "Comédie", "Crime", "Drame", "Fantastique", "Horreur", "Mystère", "Romance", "Science-Fiction", "Thriller"]

def get_real_target():
    try:
        res = requests.get("https://fstream.net", headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        for link in soup.find_all('a', href=True):
            href = link['href']
            if any(ext in href for ext in [".lol", ".me", ".pw", ".tf"]) and "fstream.net" not in href:
                return href.strip('/')
    except: pass
    return "https://fs18.lol"

def get_imdb_id(title, is_movie=True):
    """Interroge TMDB pour trouver le vrai ID IMDb du film/série"""
    try:
        m_type = "movie" if is_movie else "tv"
        # Cherche le film
        search_url = f"https://api.themoviedb.org/3/search/{m_type}?api_key={TMDB_API_KEY}&query={urllib.parse.quote(title)}&language=fr-FR"
        res = requests.get(search_url, timeout=5).json()
        
        if res.get("results"):
            tmdb_id = res["results"][0]["id"]
            # Récupère l'ID IMDb externe
            ext_url = f"https://api.themoviedb.org/3/{m_type}/{tmdb_id}/external_ids?api_key={TMDB_API_KEY}"
            ext_res = requests.get(ext_url, timeout=5).json()
            imdb_id = ext_res.get("imdb_id")
            
            if imdb_id:
                return imdb_id
            return f"tmdb:{tmdb_id}" # Plan B si pas d'IMDb
    except: pass
    return None

def scrape_smart(base_url, path, is_movie, current_db):
    temp_list = []
    session = requests.Session()
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for page in range(1, 31):
        try:
            url = f"{base_url}/{path}/page/{page}/"
            res = session.get(url, headers=headers, timeout=10)
            if res.status_code != 200: break
            
            soup = BeautifulSoup(res.text, 'html.parser')
            items = soup.select('.shortstory, .mov-item, .movie-item, div[class*="item"]')
            
            if not items: break
            
            for item in items:
                link_tag = item.find('a', href=True)
                img_tag = item.find('img')
                
                if link_tag and img_tag:
                    name = (link_tag.get('title') or img_tag.get('alt') or "Sans titre").replace("en streaming", "").strip()
                    poster = img_tag.get('data-src') or img_tag.get('src')
                    if poster and not poster.startswith('http'):
                        poster = base_url + (poster if poster.startswith('/') else '/' + poster)
                    
                    text_content = item.text.lower()
                    detected_genres = [g for g in GENRES if g.lower() in text_content]
                    
                    # --- LA MAGIE EST ICI ---
                    # Vérifie si on a déjà ce film en mémoire pour ne pas spammer TMDB
                    existing_item = next((x for x in current_db if x["name"] == name), None)
                    
                    if existing_item:
                        item_id = existing_item["id"] # On garde l'ancien ID
                    else:
                        # C'est un nouveau film ! On cherche son vrai ID.
                        real_id = get_imdb_id(name, is_movie)
                        item_id = real_id if real_id else f"fs_{hash(name)}"
                        time.sleep(0.1) # Petite pause pour ne pas bloquer l'API TMDB
                    
                    if not any(x['name'] == name for x in temp_list):
                        temp_list.append({
                            "id": item_id,
                            "type": "movie" if is_movie else "series",
                            "name": name,
                            "poster": poster,
                            "genres": detected_genres if detected_genres else ["Divers"],
                            "description": f"Source FStream",
                        })
        except: continue
    return temp_list

def update_all():
    global db
    target = get_real_target()
    print("Début du scan intelligent avec TMDB...")
    db["films_all"] = scrape_smart(target, "films", True, db["films_all"])
    db["series_all"] = scrape_smart(target, "series", False, db["series_all"])
    
    with open(DB_FILE, "w") as f:
        json.dump(db, f)
    print("✅ Base de données à jour et synchronisée avec TMDB.")

@app.on_event("startup")
async def startup_event():
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_all, 'interval', minutes=30)
    scheduler.start()
    asyncio.create_task(asyncio.to_thread(update_all))

@app.get("/manifest.json")
async def manifest():
    return {
        "id": "org.fstream.tmdb.v7",
        "version": "7.0.0",
        "name": "FStream : TMDB Debrid",
        "description": "Vrais ID + Compatibilité Torrentio/Debrid",
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
        genre = extra.split("=")[1]
        items = [i for i in items if genre in i.get("genres", [])]
    return {"metas": items}

@app.get("/")
async def health():
    return {"status": "TMDB Ready", "films": len(db["films_all"])}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
