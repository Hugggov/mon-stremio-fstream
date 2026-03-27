import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import asyncio

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"])

TMDB_API_KEY = "1863334617e9f45fcba4edb10d96639e"

def get_real_target():
    try:
        res = requests.get("https://fstream.net", timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        for link in soup.find_all('a', href=True):
            if any(ext in link['href'] for ext in [".lol", ".me", ".tf"]) and "fstream.net" not in link['href']:
                return link['href'].strip('/')
    except: pass
    return "https://fs18.lol"

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
        "id": "org.fstream.clone.v11",
        "version": "11.0.0",
        "name": "FStream : Listes Identiques",
        "description": "Scan direct de French Stream avec IDs IMDb fixes",
        "resources": ["catalog"],
        "types": ["movie"],
        "catalogs": [{"type": "movie", "id": "fs_latest", "name": "FStream : Derniers Ajouts"}]
    }

@app.get("/catalog/movie/{id}.json")
async def catalog(id: str):
    target = get_real_target()
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        res = requests.get(f"{target}/films/", headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        # On cible exactement les blocs de films du site
        items = soup.find_all('a', title=True)
        
        metas = []
        for item in items:
            img = item.find('img')
            if not img: continue
            
            title = item['title'].replace("en streaming", "").strip()
            # On cherche l'ID IMDb pour que Stremio reconnaisse le film
            imdb_id = get_imdb(title)
            
            if imdb_id:
                poster = img.get('data-src') or img.get('src')
                if poster and not poster.startswith('http'): poster = target + poster
                
                metas.append({
                    "id": imdb_id, # C'est ici qu'on tue le chat bleu
                    "type": "movie",
                    "name": title,
                    "poster": poster
                })
            if len(metas) >= 40: break # Limite pour éviter les lags
            
        return {"metas": metas}
    except Exception as e:
        return {"metas": []}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
