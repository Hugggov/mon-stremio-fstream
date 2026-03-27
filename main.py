import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"])

# Cache simple pour ne pas ralentir le serveur
CACHE_DATA = []

def get_movies():
    target = "https://fs18.lol"
    headers = {'User-Agent': 'Mozilla/5.0'}
    movies = []
    try:
        res = requests.get(f"{target}/films/", headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.find_all('a', title=True)
        for item in items:
            img = item.find('img')
            if not img: continue
            title = item['title'].replace("en streaming", "").strip()
            poster = img.get('data-src') or img.get('src')
            if poster and not poster.startswith('http'): poster = target + poster
            
            movies.append({
                "id": f"fs_{title.replace(' ', '_')}",
                "type": "movie",
                "name": title,
                "poster": poster
            })
            if len(movies) >= 40: break
    except: pass
    return movies

@app.get("/")
async def health():
    return {"status": "ready"}

@app.get("/manifest.json")
async def manifest():
    return {
        "id": "org.fstream.final.v16",
        "version": "16.0.0",
        "name": "FStream : ULTIMATE",
        "description": "Flux direct FrenchStream - Rapide & Stable",
        "resources": ["catalog"],
        "types": ["movie"],
        "catalogs": [{"type": "movie", "id": "fs_full", "name": "FStream : Films"}]
    }

@app.get("/catalog/movie/{id}.json")
async def catalog(id: str):
    # On renvoie les vrais films du site
    metas = get_movies()
    return {"metas": metas}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
