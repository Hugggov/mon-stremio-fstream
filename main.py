import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI
import uvicorn
import os

app = FastAPI()

def get_real_target():
    try:
        res = requests.get("https://fstream.net", timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        for link in soup.find_all('a', href=True):
            h = link['href']
            if any(ext in h for ext in [".lol", ".me", ".pw", ".tf"]) and "fstream.net" not in h:
                return h.strip('/')
    except: pass
    return "https://fs18.lol"

@app.get("/search")
async def search_for_aio(keyword: str):
    """Route que AIO Metadata va interroger"""
    target = get_real_target()
    # On encode la recherche pour French Stream
    search_url = f"{target}/index.php?do=search&subaction=search&story={keyword}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    results = []
    try:
        res = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        # On cherche les liens de films/séries
        items = soup.select('div.mov-t.now-e a') or soup.find_all('a', title=True)
        
        for item in items:
            title = item.get('title') or item.text
            if not title or len(title) < 3: continue
            title = title.replace("en streaming", "").strip()
            
            link = item['href']
            if not link.startswith('http'): link = target + link
            
            results.append({
                "title": title,
                "url": link,
                "source": "FrenchStream"
            })
    except: pass
    # AIO attend une liste de résultats
    return results[:10]

@app.get("/")
async def root():
    return {"message": "FStream Bridge for AIO is running"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
