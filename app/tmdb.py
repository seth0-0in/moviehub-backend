import httpx
import os
from dotenv import load_dotenv

load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
BASE_URL = "https://api.themoviedb.org/3"

async def fetch_popular_movies(page: int = 1):
    url = f"{BASE_URL}/movie/popular?api_key={TMDB_API_KEY}&language=ko-KR&page={page}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if response.status_code == 200:
            return response.json().get("results", [])
        return [] 