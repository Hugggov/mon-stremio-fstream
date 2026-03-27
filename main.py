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
        # On cherche l'ID IMDb via TMDB pour que Stremio reconnaisse le film
        url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={title}&language=fr-FR"
        res = requests.get(url, timeout=3).json()
        if res.get("results"):
            tid = res["results"][0]["id"]
            ext = requests.get(f"https://api.themoviedb.org/3/movie/{tid}/external_ids?api_key={TMDB_API_KEY}", timeout=3).json()
            return ext.get("imdb_id")
    except: pass
    return None

@app.get("/")
async def root():
    return {"message": "Serveur FStream V12 Actif", "instruction": "Ajoutez /manifest.json à l'URL dans Stremio"}

@app.get("/manifest.json")
async def manifest():
    return {
        "id": "org.fstream.perfect.v12",
        "version": "12.0.0",
        "name": "FStream : Listes Officielles",
        "description": "Tes listes FrenchStream sans le bug du chat bleu",
        "resources": ["catalog"],
        "types": ["movie"],
        "catalogs": [
            {"type": "movie", "id": "fs_films", "name": "FStream : Derniers Films"}
        ]
    }

@app.get("/catalog/movie/{id}.json")
async def catalog(id: str):
    target = get_real_target()
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        res = requests.get(f"{target}/films/", headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.find_all('a', title=True)
        
        metas = []
        for item in items:
            img = item.find('img')
            if not img: continue
            
            title = item['title'].replace("en streaming", "").strip()
            # On mappe sur l'ID IMDb pour éviter le "Aucun addon demandé"
            imdb_id = get_imdb(title)
            
            if imdb_id:
                poster = img.get('data-src') or img.get('src')
                if poster and not poster.startswith('http'): poster = target + poster
                
                metas.append({
                    "id": imdb_id,
                    "type": "movie",
                    "name": title,
                    "poster": poster
                })
            if len(metas) >= 40: break 
            
        return {"metas": metas}
    except:
        return {"metas": []}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
