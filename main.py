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
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DB_FILE = "database.json"
# Chargement initial au démarrage pour une réactivité immédiate
if os.path.exists(DB_FILE):
    with open(DB_FILE, "r") as f:
        db = json.load(f)
else:
    db = {"films_all": [], "series_all": []}

GENRES = ["Action", "Animation", "Aventure", "Comédie", "Crime", "Drame", "Fantastique", "Horreur", "Mystère", "Romance", "Science-Fiction", "Thriller"]

def get_real_target():
    """Détection ultra-rapide de l'URL active"""
    try:
        res = requests.get("https://fstream.net", headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        for link in soup.find_all('a', href=True):
            href = link['href']
            if any(ext in href for ext in [".lol", ".me", ".pw", ".tf"]) and "fstream.net" not in href:
                return href.strip('/')
    except: pass
    return "https://fs18.lol"

def scrape_fast(base_url, path, is_movie=True):
    """Scraping optimisé : s'arrête si le site ne répond plus"""
    temp_list = []
    session = requests.Session() # Utilise une session pour réutiliser la connexion (plus rapide)
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    for page in range(1, 31):
        try:
            url = f"{base_url}/{path}/page/{page}/"
            res = session.get(url, headers=headers, timeout=10)
            if res.status_code != 200: break
            
            soup = BeautifulSoup(res.text, 'html.parser')
            items = soup.select('.shortstory, .mov-item, .movie-item, div[class*="item"]')
            
            if not items: break # Plus rien à lire, on arrête
            
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
                    
                    if not any(x['name'] == name for x in temp_list):
                        temp_list.append({
                            "id": f"fs_{hash(name)}",
                            "type": "movie" if is_movie else "series",
                            "name": name,
                            "poster": poster,
                            "genres": detected_genres if detected_genres else ["Divers"],
                            "description": f"Dernière mise à jour via {base_url}",
                        })
        except: continue
    return temp_list

def update_all():
    """Mise à jour en arrière-plan sans bloquer Stremio"""
    global db
    target = get_real_target()
    new_films = scrape_fast(target, "films", True)
    new_series = scrape_fast(target, "series", False)
    
    if new_films or new_series:
        db["films_all"] = new_films
        db["series_all"] = new_series
        with open(DB_FILE, "w") as f:
            json.dump(db, f)
        print("⚡ Cache mis à jour avec succès.")

@app.on_event("startup")
async def startup_event():
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_all, 'interval', minutes=30) # Plus fréquent pour être au top
    scheduler.start()
    # On lance la mise à jour sans attendre
    asyncio.create_task(asyncio.to_thread(update_all))

@app.get("/manifest.json")
async def manifest():
    return {
        "id": "org.fstream.turbo.v6",
        "version": "6.0.0",
        "name": "FStream : Turbo Mode",
        "description": "30 Pages - Instantané - Genres",
        "resources": ["catalog"],
        "types": ["movie", "series"],
        "catalogs": [
            {"type": "movie", "id": "films_all", "name": "FStream : Films", "extra": [{"name": "genre", "options": GENRES}]},
            {"type": "series", "id": "series_all", "name": "FStream : Séries", "extra": [{"name": "genre", "options": GENRES}]}
        ]
    }

# Routes de catalogue fusionnées pour éviter les erreurs 404
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
    return {"status": "Turbo Online", "count": len(db["films_all"]) + len(db["series_all"])}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
