iimport requests
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
import uvicorn
import os
import json
import asyncio

app = FastAPI()

# Autorise Stremio à lire les données
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "database.json"
db = {"films_all": [], "series_all": []}

GENRES = ["Action", "Animation", "Aventure", "Comédie", "Crime", "Drame", "Fantastique", "Horreur", "Mystère", "Romance", "Science-Fiction", "Thriller"]

def get_real_target():
    """Cherche l'URL active sur fstream.net (ex: fs18.lol)"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        res = requests.get("https://fstream.net", headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        # On cherche le lien qui finit par .lol, .me, .pw etc.
        for link in soup.find_all('a', href=True):
            href = link['href']
            if (".lol" in href or ".me" in href or ".pw" in href) and "fstream.net" not in href:
                target = href.strip('/')
                print(f"🔗 Nouvelle cible détectée : {target}")
                return target
    except Exception as e:
        print(f"❌ Erreur lors de la détection fstream.net : {e}")
    return "https://fs18.lol" # Repli par défaut

def scrape_category(base_url, path, is_movie=True):
    """Scanne 30 pages en gardant l'ordre du site"""
    temp_list = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    for page in range(1, 31):
        try:
            url = f"{base_url}/{path}/page/{page}/"
            res = requests.get(url, headers=headers, timeout=15)
            if res.status_code != 200: break
            
            soup = BeautifulSoup(res.text, 'html.parser')
            # Sélecteur large pour attraper les blocs de films
            items = soup.select('.shortstory, .mov-item, .movie-item, div[class*="item"]')
            
            for item in items:
                link_tag = item.find('a', href=True)
                img_tag = item.find('img')
                
                if link_tag and img_tag:
                    name = (link_tag.get('title') or img_tag.get('alt') or "Sans titre").replace("en streaming", "").strip()
                    poster = img_tag.get('data-src') or img_tag.get('src')
                    
                    if poster and not poster.startswith('http'):
                        poster = base_url + (poster if poster.startswith('/') else '/' + poster)
                    
                    # Détection des genres dans le texte du bloc
                    text_content = item.text.lower()
                    detected_genres = [g for g in GENRES if g.lower() in text_content]
                    
                    if not any(x['name'] == name for x in temp_list):
                        temp_list.append({
                            "id": f"fs_{hash(name)}",
                            "type": "movie" if is_movie else "series",
                            "name": name,
                            "poster": poster,
                            "genres": detected_genres if detected_genres else ["Divers"],
                            "description": f"Ajouté récemment sur FStream. Source: {base_url}",
                        })
            print(f"📄 Page {page} de {path} terminée...")
        except:
            continue
    return temp_list

def update_all():
    """Mission de rafraîchissement complet"""
    target = get_real_target()
    db["films_all"] = scrape_category(target, "films", True)
    db["series_all"] = scrape_category(target, "series", False)
    with open(DB_FILE, "w") as f:
        json.dump(db, f)
    print(f"✅ Base de données mise à jour : {len(db['films_all'])} Films, {len(db['series_all'])} Séries")

@app.on_event("startup")
async def startup_event():
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_all, 'interval', hours=1)
    scheduler.start()
    # Lancement du premier scan en arrière-plan pour ne pas bloquer le démarrage
    asyncio.create_task(asyncio.to_thread(update_all))

@app.get("/manifest.json")
async def manifest():
    return {
        "id": "org.fstream.full.v5",
        "version": "5.5.0",
        "name": "FStream : Elite Pro",
        "description": "Films & Séries - 30 Pages - Auto-Update",
        "resources": ["catalog"],
        "types": ["movie", "series"],
        "catalogs": [
            {
                "type": "movie", 
                "id": "films_all", 
                "name": "FStream : Films",
                "extra": [{"name": "genre", "options": GENRES, "isRequired": False}]
            },
            {
                "type": "series", 
                "id": "series_all", 
                "name": "FStream : Séries",
                "extra": [{"name": "genre", "options": GENRES, "isRequired": False}]
            }
        ]
    }

@app.get("/catalog/{type}/{id}.json")
async def catalog_default(type: str, id: str):
    return {"metas": db.get(id, [])}

@app.get("/catalog/{type}/{id}/{extra}.json")
async def catalog_extra(type: str, id: str, extra: str):
    all_items = db.get(id, [])
    if "genre=" in extra:
        selected_genre = extra.split("=")[1]
        filtered = [i for i in all_items if selected_genre in i.get("genres", [])]
        return {"metas": filtered}
    return {"metas": all_items}

@app.get("/")
async def health():
    return {"status": "Online", "films": len(db["films_all"]), "series": len(db["series_all"])}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
