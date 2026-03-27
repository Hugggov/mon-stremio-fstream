from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"])

@app.get("/manifest.json")
async def manifest():
    return {
        "id": "com.fstream.test.v15",
        "version": "15.0.0",
        "name": "TEST FSTREAM",
        "description": "Test de connexion directe",
        "resources": ["catalog"],
        "types": ["movie"],
        "catalogs": [{"type": "movie", "id": "fs_test", "name": "FStream : TEST"}]
    }

@app.get("/catalog/movie/{id}.json")
async def catalog(id: str):
    # On envoie 2 films fixes pour voir si Stremio les affiche
    return {
        "metas": [
            {
                "id": "tt11032374",
                "type": "movie",
                "name": "Gladiator II (TEST)",
                "poster": "https://image.tmdb.org/t/p/w500/v999pZUnXmgo9RsZ9S9vthv9S9s.jpg"
            },
            {
                "id": "tt0944947",
                "type": "movie",
                "name": "Game of Thrones (TEST)",
                "poster": "https://image.tmdb.org/t/p/w500/u3bZgnoc9vIqrYxeexD6MStYvL6.jpg"
            }
        ]
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
