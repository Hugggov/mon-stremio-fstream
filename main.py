import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"])

@app.get("/manifest.json")
async def manifest():
    return {
        "id": "com.fstream.new.v14", # Nouvel ID pour forcer Stremio à oublier l'ancien
        "version": "14.0.0",
        "name": "FStream : FINAL TEST",
        "description": "Chargement forcé des listes",
        "resources": ["catalog"],
        "types": ["movie"],
        "catalogs": [{"type": "movie", "id": "fs_final", "name": "FStream : Flux Direct"}]
    }

@app.get("/catalog/movie/{id}.json")
async def catalog(id: str):
    target = "https://fs18.lol"
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
            
            metas.append({
                "id": f"movie_{title.replace(' ', '')}", # ID ultra simple
                "type": "movie",
                "name": title,
                "poster": poster
            })
            if len(metas) >= 20: break
        return {"metas": metas}
    except:
        return {"metas": []}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
