# your_app/services.py

import requests
from django.conf import settings

from user.models import MovieInteraction

BASE_URL = "https://api.themoviedb.org/3"
_title_cache = {}

# Helper to turn an ID (550) into a movie title using TMDB Bearer token (v4)
def get_movie_title(movie_id: int):
    if movie_id in _title_cache:
        return _title_cache[movie_id]

    headers = {
        "Authorization": f"Bearer {settings.TMDB_API_KEY}",
        "accept": "application/json",
    }
    url = f"{BASE_URL}/movie/{movie_id}"
    try:
        r = requests.get(url, headers=headers, timeout=8)
        if r.status_code == 200:
            title = r.json().get("title")
            if title:
                _title_cache[movie_id] = title
                return title
            return None
        # Non-200: avoid noisy 'Unknown Movie' entries
        return None
    except Exception:
        return None

def get_weighted_user_profile(user):
    # 1. Fetch all interactions for this user
    interactions = MovieInteraction.objects.filter(user=user)
    total_interactions = interactions.count()
    print(f"[ai_engine] get_weighted_user_profile for user {user.username}: {total_interactions} total interactions")

    # 2. Create buckets with priority hierarchy (highest to lowest)
    loved = []   # Rating 5 (highest priority)
    saved = []   # Watchlist without high rating
    liked = []   # Rating 3-4
    hated = []   # Rating 1-2 (avoid these patterns)

    # 3. Sort movies into buckets with priority handling (skip missing titles)
    # Priority: HATED > LOVED > SAVED > LIKED (avoid duplicates across buckets)
    loved_set = set()
    saved_set = set()
    liked_set = set()
    hated_set = set()
    
    for item in interactions:
        title = get_movie_title(item.movie_id)
        if not title:
            continue
        
        # Priority 1: HATED (rating 1-2) - strongest signal to avoid
        if item.rating and item.rating <= 2:
            hated_set.add(title)
            print(f"[ai_engine]   HATED: {title} (rating {item.rating})")
        # Priority 2: LOVED (rating 5) - even if also saved
        elif item.rating == 5:
            loved_set.add(title)
            print(f"[ai_engine]   LOVED: {title}")
        # Priority 3: SAVED (watchlist without rating 5)
        elif item.is_saved:
            saved_set.add(title)
            print(f"[ai_engine]   SAVED: {title}")
        # Priority 4: LIKED (rating 3-4)
        elif item.rating and item.rating >= 3:
            liked_set.add(title)
            print(f"[ai_engine]   LIKED: {title} (rating {item.rating})")

    # 4. Convert sets to lists for consistent ordering
    loved = sorted(loved_set)
    saved = sorted(saved_set)
    liked = sorted(liked_set)
    hated = sorted(hated_set)
    
    print(f"[ai_engine] Final counts: LOVED={len(loved)}, SAVED={len(saved)}, LIKED={len(liked)}, HATED={len(hated)}")

    profile_text = "User's Taste Profile:\n"
    if loved:
        profile_text += f"- LOVES (Strongest match): {', '.join(loved)}\n"
    if saved:
        profile_text += f"- WATCHLIST (High interest): {', '.join(saved)}\n"
    if liked:
        profile_text += f"- LIKES (General interest): {', '.join(liked)}\n"
    if hated:
        profile_text += f"- HATES (Avoid similar movies): {', '.join(hated)}\n"
    if not (loved or saved or liked or hated):
        profile_text += "(no interactions yet)\n"

    return profile_text