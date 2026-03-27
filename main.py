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
db = {"films_all": [], "series_all": []}

# Liste des genres supportés par FStream pour le filtrage
GENRES = ["Action", "Animation", "Aventure", "Comédie", "Crime", "Drame", "Fantastique", "Horreur", "Mystère", "Romance", "Science-Fiction", "Thriller"]

def get_target_url():
    try:
        res = requests.get("https://fstream.net", headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        for link in soup.find_all('a', href=True):
            if ".lol" in link['href'] and "fstream.net" not in link['href']:
                return link['href'].strip('/')
    except: pass
    return "https://fs18.lol"

def scrape_v5(base_url, path, is_movie=True):
    items = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    for page in range(1, 31):
        try:
            url = f"{base_url}/{path}/page/{page}/"
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code != 200: break
            soup = BeautifulSoup(res.text, 'html.parser')
            
            elements = soup.select('.shortstory, .mov-item, .movie-item')
            for el in elements:
                link_tag = el.find('a')
                img_tag = el.find('img')
                
                # Extraction des genres sur la vignette (souvent présent dans le texte)
                genre_text = el.text
                detected_genres = [g for g in GENRES if g.lower() in genre_text.lower()]

                if link_tag and img_tag:
                    name = link_tag.get('title') or img_tag.get('alt')
                    if not name: continue
                    name = name.replace("en streaming", "").strip()
                    
                    poster = img_tag.get('data-src') or img_tag.get('src')
                    if poster and not poster.startswith('http'):
                        poster = base_url + (poster if poster.startswith('/') else '/' + poster)
                    
                    page_url = link_tag['href']
                    if not page_url.startswith('http'):
                        page_url = base_url + (page_url if page_url.startswith('/') else '/' + page_url)

                    if not any(x['name'] == name for x in items):
                        items.append({
                            "id": f"fs_{hash(name)}",
                            "type": "movie" if is_movie else "series",
                            "name": name,
                            "poster": poster,
                            "genres": detected_genres if detected_genres else ["Divers"],
                            "description": f"Lien direct site : {page_url}",
                        })
        except: continue
    return items

def update_data():
    target = get_target_url()
    db["films_all"] = scrape_v5(target, "films", is_movie=True)
    db["series_all"] = scrape_v5(target, "series", is_movie=False)
    with open(DB_FILE, "w") as f: json.dump(db, f)

@app.on_event("startup")
async def startup():
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_data, 'interval', hours=1)
    scheduler.start()
    asyncio.create_task(asyncio.to_thread(update_data))

@app.get("/manifest.json")
async def manifest():
    return {
        "id": "org.fstream.genres.v5",
        "version": "5.0.0",
        "name": "FStream : Elite Genres",
        "description": "30 Pages - Filtres par Genre - Ordre Web",
        "resources": ["catalog"],
        "types": ["movie", "series"],
        "catalogs": [
            {
                "type": "movie", 
                "id": "films_all", 
                "name": "FStream : Films",
                "extra": [{"name": "genre", "options": GENRES, "isRequired": False}]
            },
            {
                "type": "series", 
                "id": "series_all", 
                "name": "FStream : Séries",
                "extra": [{"name": "genre", "options": GENRES, "isRequired": False}]
            }
        ]
    }

@app.get("/catalog/{type}/{id}/{extra}.json")
async def catalog_with_genre(type: str, id: str, extra: str = None):
    items = db.get(id, [])
    
    # Si l'utilisateur a sélectionné un genre dans Stremio
    if extra:
        try:
            # Format attendu par Stremio : genre=Action
            selected_genre = extra.split('=')[1]
            filtered = [item for item in items if selected_genre in item.get('genres', [])]
            return {"metas": filtered}
        except: pass
        
    return {"metas": items}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
