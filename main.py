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
    """Détecte l'URL active sur fstream.net"""
    try:
        res = requests.get("https://fstream.net", headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        for link in soup.find_all('a', href=True):
            href = link['href'].strip('/')
            if (".lol" in href or ".me" in href or ".pw" in href) and "fstream.net" not in href:
                return href
    except: pass
    return "https://fs18.lol"

def scrape_category(base_url, path, catalog_id, max_pages=15):
    temp_list = []
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
    
    for page in range(1, max_pages + 1):
        try:
            url = f"{base_url}/{path}/page/{page}/"
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code != 200: break
            
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # --- SCANNER UNIVERSEL ---
            # On cherche tous les blocs qui contiennent un lien ET une image
            # C'est la méthode la plus fiable pour n'importe quel site
            for article in soup.find_all(['div', 'article']):
                link = article.find('a')
                img = article.find('img')
                
                if link and img and link.get('title'):
                    name = link.get('title').strip()
                    poster = img.get('data-src') or img.get('src')
                    
                    if poster and not poster.startswith('http'):
                        poster = base_url + (poster if poster.startswith('/') else '/' + poster)
                    
                    # On évite les doublons
                    if not any(item['name'] == name for item in temp_list):
                        temp_list.append({
                            "id": f"fs_{hash(name)}",
                            "type": "series" if "series" in catalog_id else "movie",
                            "name": name,
                            "poster": poster,
                            "description": f"FStream - {catalog_id.upper()}"
                        })
            
            if len(temp_list) < 5: continue # Si on a rien trouvé, on teste la page suivante
            
        except Exception as e:
            print(f"Erreur sur {path}: {e}")
            continue
    
    if temp_list:
        db[catalog_id] = temp_list
        with open(DB_FILE, "w") as f: json.dump(db, f)
        print(f"✅ {len(temp_list)} titres capturés pour {catalog_id}")

def update_all_data():
    target = get_ephemeral_url()
    # On teste les deux formats de chemins possibles (avec et sans '-streaming')
    cats = [
        ("films-streaming", "fs_movie_all"), 
        ("series-streaming", "fs_series_all"), 
        ("science-fiction-streaming", "fs_sci_fi_movie"), 
        ("fantastique-streaming", "fs_fantastique_movie")
    ]
    for path, cid in cats:
        scrape_category(target, path, cid, 15)

@app.on_event("startup")
async def startup_event():
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_all_data, 'interval', hours=2)
    scheduler.start()
    asyncio.create_task(asyncio.to_thread(update_all_data))

@app.get("/")
@app.head("/")
async def root():
    return {"status": "Online", "cible": get_ephemeral_url(), "titres": {k: len(v) for k, v in db.items()}}

@app.get("/manifest.json")
async def manifest():
    return {
        "id": "org.fstream.universal.v20",
        "version": "22.0.0",
        "name": "FStream ELITE 20",
        "description": "Scanner Universel (fsXX.lol)",
        "resources": ["catalog"],
        "types": ["movie", "series"],
        "catalogs": [
            {"type": "movie", "id": "fs_movie_all", "name": "FStream : Films"},
            {"type": "series", "id": "fs_series_all", "name": "FStream : Séries"},
            {"type": "movie", "id": "fs_sci_fi_movie", "name": "FStream : Films Sci-Fi"},
            {"type": "movie", "id": "fs_fantastique_movie", "name": "FStream : Films Fantastique"}
        ]
    }

@app.get("/catalog/{type}/{id}.json")
async def catalog(type: str, id: str):
    return {"metas": db.get(id, [])}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
