import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

TMDB_API_KEY = "1863334617e9f45fcba4edb10d96639e"

def get_real_target():
    try:
        res = requests.get("https://fstream.net", timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        for link in soup.find_all('a', href=True):
            h = link['href']
            if any(ext in h for ext in [".lol", ".me", ".tf"]) and "fstream.net" not in h:
                return h.strip('/')
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

@app.get("/")
async def root():
    return {"status": "V12.1 Turbo Active", "tip": "Collez /manifest.json dans Stremio"}

@app.get("/manifest.json")
async def manifest():
    return {
        "id": "org.fstream.turbo.v12",
        "version": "12.1.0",
        "name": "FStream : Turbo",
        "description": "Listes instantanées sans bug",
        "resources": ["catalog"],
        "types": ["movie"],
        "catalogs": [{"type": "movie", "id": "fs_turbo", "name": "FStream : Derniers Films"}]
    }

@app.get("/catalog/movie/{id}.json")
async def catalog(id: str):
    target = get_real_target()
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        # On force la lecture immédiate du site
        res = requests.get(f"{target}/films/", headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.find_all('a', title=True)
        
        metas = []
        for item in items:
            img = item.find('img')
            if not img: continue
            
            title = item['title'].replace("en streaming", "").strip()
            # On cherche l'IMDb pour que Wastream s'active
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
            if len(metas) >= 30: break 
            
        return {"metas": metas}
    except:
        return {"metas": []}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
