from fastapi.exceptions import RequestValidationError
from fastapi import FastAPI, Request, Form, HTTPException  # Aggiungi HTTPException
import httpx
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Configurazione API
API_KEY = "2fa8ef75c70a212d9fd3cd51b785939f"
BASE_URL = "https://api.themoviedb.org/3"
IMG_BASE_URL = "https://image.tmdb.org/t/p/w300"  # Immagini di buona qualità


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/search", response_class=HTMLResponse)
async def search_movie(request: Request, title: str = Form(...)):
    async with httpx.AsyncClient() as client:
        # 1. Cerchiamo il film per titolo
        search_res = await client.get(
            f"{BASE_URL}/search/movie",
            params={"api_key": API_KEY, "query": title, "language": "it-IT"}
        )
        movies = search_res.json().get('results', [])

        if not movies:
            return HTMLResponse('<p class="text-center text-red-400 py-10">Film non trovato. Prova un altro titolo!</p>')

        # 2. Prendiamo il primo risultato (il più rilevante) e cerchiamo il cast
        movie = movies[0]
        movie_id = movie['id']

        credits_res = await client.get(
            f"{BASE_URL}/movie/{movie_id}/credits",
            params={"api_key": API_KEY, "language": "it-IT"}
        )
        cast = credits_res.json().get('cast', [])[:12]  # Limitiamo ai primi 12 attori

        # Restituiamo solo il "pezzo" della griglia (Partial)
        return templates.TemplateResponse("partials/cast_grid.html", {
            "request": request,
            "movie_title": movie['title'],
            "cast": cast,
            "img_base": IMG_BASE_URL
        })


@app.get("/actor/{actor_id}", response_class=HTMLResponse)
async def actor_details(request: Request, actor_id: int):
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(
                f"{BASE_URL}/person/{actor_id}",
                params={
                    "api_key": API_KEY,
                    "language": "it-IT",
                    "append_to_response": "movie_credits"
                }
            )

            # Se l'ID non esiste, TMDB restituisce 404
            if res.status_code == 404:
                raise HTTPException(
                    status_code=404, detail="Attore non trovato")

            res.raise_for_status()  # Gestisce altri errori di rete
            actor = res.json()

            # ... resto del codice per ordinare i film ...
            known_for = sorted(
                actor.get('movie_credits', {}).get('cast', []),
                key=lambda x: x.get('popularity', 0),
                reverse=True
            )[:6]

            return templates.TemplateResponse("actor.html", {
                "request": request,
                "actor": actor,
                "known_for": known_for,
                "img_base": "https://image.tmdb.org/t/p/w500"
            })

        except (httpx.HTTPStatusError, HTTPException):
            # Se l'ID è sbagliato, mostriamo una pagina 404 personalizzata
            return templates.TemplateResponse("404.html", {"request": request}, status_code=404)


# Questo handler "cattura" gli errori di validazione (come 'mmmm' al posto di un numero)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Invece del JSON, restituiamo la nostra pagina 404.html
    return templates.TemplateResponse("404.html", {"request": request}, status_code=404)

# Facciamo lo stesso per gli errori 404 generici (es. rotte che non esistono)


@app.exception_handler(404)
async def custom_404_handler(request: Request, __):
    return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
