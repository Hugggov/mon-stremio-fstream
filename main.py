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
        "id": "org.fstream.bypass.v17",
        "version": "17.0.0",
        "name": "FStream : ANTI-BUG",
        "description": "Chargement forcé des films",
        "resources": ["catalog"],
        "types": ["movie"],
        "catalogs": [{"type": "movie", "id": "fs_bypass", "name": "FStream : Films"}]
    }

@app.get("/catalog/movie/{id}.json")
async def catalog(id: str):
    # On imite un iPhone pour ne pas être bloqué par le site
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Referer': 'https://google.com'
    }
    
    metas = []
    try:
        # On tente de lire le site
        res = requests.get("https://fs18.lol/films/", headers=headers, timeout=8)
        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.find_all('a', title=True)
        
        for item in items:
            img = item.find('img')
            if not img: continue
            title = item['title'].replace("en streaming", "").strip()
            poster = img.get('data-src') or img.get('src')
            
            # Réparation de l'URL de l'image
            if poster and not poster.startswith('http'):
                poster = "https://fs18.lol" + poster
            
            metas.append({
                "id": f"tt_fs_{title.replace(' ', '')}",
                "type": "movie",
                "name": title,
                "poster": poster
            })
            if len(metas) >= 40: break
    except Exception as e:
        print(f"Erreur : {e}")
    
    # SI LE SITE BLOQUE : On envoie au moins 3 films récents en dur pour ne pas avoir le chat bleu
    if not metas:
        metas = [
            {"id": "tt11032374", "type": "movie", "name": "Gladiator II", "poster": "https://image.tmdb.org/t/p/w500/v999pZUnXmgo9RsZ9S9vthv9S9s.jpg"},
            {"id": "tt12637874", "type": "movie", "name": "Moana 2", "poster": "https://image.tmdb.org/t/p/w500/m0S38v9V5577D9opM693vYvY88S.jpg"},
            {"id": "tt14661022", "type": "movie", "name": "Sonic 3", "poster": "https://image.tmdb.org/t/p/w500/d8R0u4YUIO9Cu9IBv98oI9u4M9X.jpg"}
        ]
        
    return {"metas": metas}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    
