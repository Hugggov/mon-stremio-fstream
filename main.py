import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI

app = FastAPI()

def get_real_url():
    # Va chercher l'adresse actuelle du site
    try:
        r = requests.get("https://fstream.net/", timeout=10)
        return r.url.strip('/')
    except:
        return "https://fstream.net"

@app.get("/manifest.json")
def manifest():
    return {
        "id": "org.fstream.novice",
        "version": "1.0.0",
        "name": "FStream Expert",
        "description": "Mes listes FStream en direct",
        "resources": ["catalog"],
        "types": ["movie", "series"],
        "catalogs": [
            {"type": "movie", "id": "fs_films", "name": "FStream : Films"},
            {"type": "series", "id": "fs_series", "name": "FStream : Séries"}
        ]
    }

@app.get("/catalog/{type}/{id}.json")
def catalog(type: str, id: str):
    base = get_real_url()
    path = "films-streaming" if type == "movie" else "series-streaming"
    items = []
    
    # On scanne les 30 premières pages
    for page in range(1, 31):
        try:
            res = requests.get(f"{base}/{path}/page/{page}/", timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')
            # On cherche les boîtes de films
            for movie in soup.find_all('div', class_='shortstory'):
                title = movie.find('h2').text.strip()
                img = movie.find('img')['src']
                if not img.startswith('http'): img = base + img
                
                items.append({
                    "id": f"fs_{title.replace(' ', '_')}",
                    "type": type,
                    "name": title,
                    "poster": img
                })
        except:
            continue
    return {"metas": items}
