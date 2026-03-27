import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"])

TMDB_API_KEY = "1863334617e9f45fcba4edb10d96639e"

def get_real_target():
    return "https://fs18.lol" # On force l'URL pour gagner du temps au démarrage

def get_imdb(title):
    try:
        url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={title}&language=fr-FR"
        res = requests.get(url, timeout=2).json()
        if res.get("results"):
            tid = res["results"][0]["id"]
            ext = requests.get(f"https://api.themoviedb.org/3/movie/{tid}/external_ids?api_key={TMDB_API_KEY}", timeout=2).json()
            return ext.get("imdb_id")
    except: pass
    return None

@app.get("/manifest.json")
async def manifest():
    return {
        "id": "org.fstream.instant.v13",
        "version": "13.0.0",
        "name": "FStream : Instant",
        "description": "Affichage immédiat des listes",
        "resources": ["catalog", "meta"],
        "types": ["movie"],
        "catalogs": [{"type": "movie", "id": "fs_instant", "name": "FStream : Films"}]
    }

@app.get("/catalog/movie/{id}.json")
async def catalog(id: str):
    target = get_real_target()
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(f"{target}/films/", headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.find_all('a', title=True)
        
        metas = []
        for item in items:
            img = item.find('img')
            if not img: continue
            title = item['title'].replace("en streaming", "").strip()
            poster = img.get('data-src') or img.get('src')
            if poster and not poster.startswith('http'): poster = target + poster
            
            # On utilise un ID temporaire ultra-rapide pour que Stremio affiche la liste direct
            metas.append({
                "id": f"fstr_{title.replace(' ', '_')}", 
                "type": "movie",
                "name": title,
                "poster": poster
            })
            if len(metas) >= 50: break
        return {"metas": metas}
    except:
        return {"metas": []}

@app.get("/meta/movie/{id}.json")
async def meta(id: str):
    # Quand tu cliques sur le film, ON CHERCHE LE VRAI ID IMDB
    title = id.replace("fstr_", "").replace("_", " ")
    imdb_id = get_imdb(title)
    
    if imdb_id:
        # On redirige Stremio vers la fiche officielle IMDb
        return {"meta": {"id": imdb_id, "type": "movie", "name": title}}
    
    return {"meta": {"id": id, "type": "movie", "name": title}}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
