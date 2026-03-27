import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
import uvicorn
import os
import asyncio

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base de données pour les 6 listes demandées
db = {
    "fs_movie_all": [],
    "fs_series_all": [],
    "fs_sci_fi_movie": [],
    "fs_fantastique_movie": [],
    "fs_sci_fi_series": [],
    "fs_fantastique_series": []
}

def get_live_url():
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    try:
        r = requests.get("https://fstream.net/", headers=headers, timeout=5, allow_redirects=True)
        return r.url.strip('/')
    except:
        return "https://fstream.net"

def scrape_category(base_url, path, catalog_id, max_pages=20):
    temp_list = []
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    is_series_cat = "series" in path or "series" in catalog_id

    for page in range(1, max_pages + 1):
        try:
            url = f"{base_url}/{path}/page/{page}/"
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code != 200: break
            
            soup = BeautifulSoup(res.text, 'html.parser')
            items = soup.select('.shortstory')
            if not items: break
            
            for item in items:
                title_el = item.find('h2')
                img_el = item.find('img')
                if title_el and img_el:
                    name = title_el.text.strip()
                    img = img_el['src']
                    if not img.startswith('http'): img = base_url + (img if img.startswith('/') else '/' + img)
                    
                    temp_list.append({
                        "id": f"fs_{name.replace(' ', '_')[:30]}",
                        "type": "series" if is_series_cat else "movie",
                        "name": name,
                        "poster": img,
                        "description": f"FStream - {catalog_id.upper()}"
                    })
        except:
            continue
    
    if temp_list:
        db[catalog_id] = temp_list

def update_all_data():
    base = get_live_url()
    # On scanne 20 pages pour chaque catégorie
    scrape_category(base, "films-streaming", "fs_movie_all", 20)
    scrape_category(base, "series-streaming", "fs_series_all", 20)
    scrape_category(base, "science-fiction-streaming", "fs_sci_fi_movie", 20)
    scrape_category(base, "fantastique-streaming", "fs_fantastique_movie", 20)
    # Note: fstream mélange souvent les types dans les catégories, 
    # mais ces filtres assurent la séparation dans Stremio
    scrape_category(base, "science-fiction-streaming", "fs_sci_fi_series", 20)
    scrape_category(base, "fantastique-streaming", "fs_fantastique_series", 20)

@app.on_event("startup")
async def startup_event():
    base = get_live_url()
    # Charge la page 1 de tout en 5 secondes pour le "Home"
    cats = [
        ("films-streaming", "fs_movie_all"),
        ("series-streaming", "fs_series_all"),
        ("science-fiction-streaming", "fs_sci_fi_movie"),
        ("fantastique-streaming", "fs_fantastique_movie"),
        ("science-fiction-streaming", "fs_sci_fi_series"),
        ("fantastique-streaming", "fs_fantastique_series")
    ]
    for path, cid in cats:
        scrape_category(base, path, cid, max_pages=1)
    
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_all_data, 'interval', hours=2)
    scheduler.start()
    asyncio.create_task(asyncio.to_thread(update_all_data))

@app.get("/manifest.json")
async def manifest():
    return {
        "id": "org.fstream.expert.v20",
        "version": "20.0.0",
        "name": "FStream ELITE 20",
        "description": "Films & Séries (20 pages) - Sci-Fi & Fantastique",
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
