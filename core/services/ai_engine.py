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

    # 2. Create buckets for our "Weighted Logic"
    loved = []   # Rating 5
    saved = []   # Watchlist (Weight 4)
    liked = []   # Rating 3-4
    hated = []   # Rating 1-2 (Block list)

    # 3. Sort movies into buckets (skip missing titles)
    for item in interactions:
        title = get_movie_title(item.movie_id)
        if not title:
            continue
        if item.rating and item.rating <= 2:
            hated.append(title)
            print(f"[ai_engine]   HATED: {title} (rating {item.rating})")
        elif item.rating == 5:
            loved.append(title)
            print(f"[ai_engine]   LOVED: {title}")
        elif item.is_saved:
            saved.append(title)
            print(f"[ai_engine]   SAVED: {title}")
        elif item.rating and item.rating >= 3:
            liked.append(title)
            print(f"[ai_engine]   LIKED: {title} (rating {item.rating})")

    # 4. Construct the text for the AI (dedupe and tidy)
    def unique(seq):
        seen = set()
        out = []
        for s in seq:
            if s not in seen:
                seen.add(s)
                out.append(s)
        return out

    loved = unique(loved)

    print(f"[ai_engine] After dedup: LOVED={len(loved)}, SAVED={len(saved)}, LIKED={len(liked)}, HATED={len(hated)}")
    saved = unique(saved)
    liked = unique(liked)
    hated = unique(hated)

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