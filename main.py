from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

app = FastAPI()

# Autorise Stremio à lire les données
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def health():
    return {"status": "ok", "message": "Serveur de TEST actif"}

@app.get("/manifest.json")
async def manifest():
    return {
        "id": "com.fstream.test.v151",
        "version": "15.1.0",
        "name": "FSTREAM DIAGNOSTIC",
        "description": "Si vous voyez ce message, la connexion fonctionne",
        "resources": ["catalog"],
        "types": ["movie"],
        "catalogs": [{"type": "movie", "id": "fs_test_diag", "name": "FStream : TEST"}]
    }

@app.get("/catalog/movie/{id}.json")
async def catalog(id: str):
    return {
        "metas": [
            {
                "id": "tt11032374",
                "type": "movie",
                "name": "Gladiator II (TEST)",
                "poster": "https://image.tmdb.org/t/p/w500/v999pZUnXmgo9RsZ9S9vthv9S9s.jpg"
            }
        ]
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
