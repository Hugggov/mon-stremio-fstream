import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"])

TMDB_API_KEY = "1863334617e9f45fcba4edb10d96639e"

def get_imdb(title):
    try:
        url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={title}&language=fr-FR"
        res = requests.get(url, timeout=3).json()
        if res.get("results"):
            tid = res["results"][0]["id"]
            ext = requests.get(f"https://api.themoviedb.org/3/movie/{tid}/external_ids?api_key={TMDB_API_KEY}", timeout=3).json()
            return ext.get("imdb_id")
    except: pass
    return None

@app.get("/manifest.json")
async def manifest():
    return {
        "id": "org.fstream.ultimate.v18",
        "version": "18.0.0",
        "name": "FStream : ULTIMATE",
        "description": "Films FrenchStream avec compatibilité Debrid",
        "resources": ["catalog"],
        "types": ["movie"],
        "catalogs": [{"type": "movie", "id": "fs_ultimate", "name": "FStream : Films"}]
    }

@app.get("/catalog/movie/{id}.json")
async def catalog(id: str):
    headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15'}
    metas = []
    try:
        res = requests.get("https://fs18.lol/films/", headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.find_all('a', title=True)
        
        for item in items:
            img = item.find('img')
            if not img: continue
            title = item['title'].replace("en streaming", "").strip()
            
            # On cherche l'ID IMDb pour activer Wastream
            imdb_id = get_imdb(title)
            
            if imdb_id:
                poster = img.get('data-src') or img.get('src')
                if poster and not poster.startswith('http'): poster = "https://fs18.lol" + poster
                
                metas.append({
                    "id": imdb_id,
                    "type": "movie",
                    "name": title,
                    "poster": poster
                })
            if len(metas) >= 35: break
    except: pass

    # Secours si le site est lent
    if not metas:
        metas = [{"id": "tt11032374", "type": "movie", "name": "Gladiator II", "poster": "
