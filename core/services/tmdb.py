import requests
from django.conf import settings

BASE_URL = "https://api.themoviedb.org/3"

def fetch_movies(query=None, page=1):
    headers = {
        "Authorization": f"Bearer {settings.TMDB_API_KEY}",
        "accept": "application/json",
    }

    if query:
        url = f"{BASE_URL}/search/movie"
        params = {"query": query, "page": page}
    else:
        url = f"{BASE_URL}/discover/movie"
        params = {"sort_by": "popularity.desc", "page": page}

    r = requests.get(url, headers=headers, params=params)
    r.raise_for_status()
    return r.json()

def trending_movies():
    url = f"{BASE_URL}/trending/movie/week"
    headers = {
        "Authorization": f"Bearer {settings.TMDB_API_KEY}",
        "accept": "application/json",
    }
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()

def get_movie_details(movie_id):
    """Get detailed movie info including credits, recommendations, videos, and watch providers"""
    headers = {
        "Authorization": f"Bearer {settings.TMDB_API_KEY}",
        "accept": "application/json",
    }
    
    # Fetch movie details with append_to_response for efficiency
    url = f"{BASE_URL}/movie/{movie_id}"
    params = {
        "append_to_response": "credits,recommendations,videos,watch/providers"
    }
    
    r = requests.get(url, headers=headers, params=params)
    r.raise_for_status()
    return r.json()

