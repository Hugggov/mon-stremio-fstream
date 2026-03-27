import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI
from cachetools import TTLCache

app = FastAPI()

# ⏳ MISE EN CACHE TOUTES LES 2 HEURES (7200 secondes)
# Le serveur garde les 50 pages en mémoire pour que Stremio s'ouvre INSTANTANÉMENT
cache = TTLCache(maxsize=10, ttl=7200)

def get_real_url():
    """ Trouve l'adresse actuelle et à jour du site de streaming """
    try:
        r = requests.get("https://fstream.net/", timeout=10)
        return r.url.strip('/')
    except:
        return "https://fstream.net"

def scrape_pages(content_type: str):
    """ Scrape les 50 premières pages du site de streaming """
    base = get_real_url()
    items = []
    
    # On définit le chemin selon si c'est un film ou une série
    path = "films-streaming" if content_type == "movie" else "series-streaming"
    
    # On boucle sur 50 pages (tu peux changer à 30 si c'est trop lourd)
    for page in range(1, 51):
        try:
            url = f"{base}/{path}/page/{page}/"
            res = requests.get(url, timeout=10)
            if res.status_code != 200:
                break # On s'arrête si la page n'existe pas
                
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # Recherche des blocs de films/séries (balise 'div' avec classe 'shortstory')
            for entry in soup.find_all('div', class_='shortstory'):
                title = entry.find('h2').text.strip()
                img = entry.find('img')['src']
                if not img.startswith('http'): 
                    img = base + img
                
                # On nettoie le titre pour créer un identifiant Stremio unique
                clean_id = f"fs_{title.replace(' ', '_').lower()}"
                
                items.append({
                    "id": clean_id,
                    "type": content_type,
                    "name": title,
                    "poster": img,
                    "description": f"Ajouté récemment sur FStream (Page {page})"
                })
        except:
            continue # Si une page bug, on passe à la suivante
            
    return items

@app.get("/manifest.json")
def manifest():
    """ Ce que Stremio lit pour comprendre ton Add-on """
    return {
        "id": "org.fstream.ultraspeed",
        "version": "1.1.0",
        "name": "FStream Expert (50 Pages)",
        "description": "Films et Séries mis à jour toutes les 2H (Ultra rapide)",
        "resources": ["catalog"],
        "types": ["movie", "series"],
        "catalogs": [
            {"type": "movie", "id": "fs_movie_all", "name": "FStream : Tous les Films (50p)"},
            {"type": "series", "id": "fs_series_all", "name": "FStream : Toutes les Séries (50p)"}
        ]
    }

@app.get("/catalog/{type}/{id}.json")
def catalog(type: str, id: str):
    """ Envoie le catalogue à Stremio """
    cache_key = f"{type}_{id}"
    
    # 🔍 1. Est-ce que la liste est déjà prête dans notre mémoire ?
    if cache_key in cache:
        return {"metas": cache[cache_key]}
    
    # ⚙️ 2. Sinon, on va chercher les 50 pages
    scraped_data = scrape_pages(type)
    
    # 💾 3. On met dans la mémoire pour les 2 prochaines heures
    cache[cache_key] = scraped_data
    
    return {"metas": scraped_data}
