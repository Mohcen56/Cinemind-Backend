from django.shortcuts import render
# your_app/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from django.conf import settings
import json
import requests
import re
import os
from rest_framework.decorators import api_view
from rest_framework.response import Response
from core.services.ai_engine import get_weighted_user_profile, get_movie_title
from core.services.llm_providers import (
    chat_with_groq,
    chat_with_github_models,
    choose_provider,
)
from user.models import MovieInteraction
from core.services.tmdb import fetch_movies, trending_movies, get_movie_details
from core.models import TrendingSearch



@api_view(["GET"])
def movies(request):
    q = request.GET.get("q")
    page = request.GET.get("page", "1")
    
    try:
        page_num = int(page)
    except ValueError:
        page_num = 1
    
    data = fetch_movies(q, page_num)
    return Response(data)

@api_view(["GET"])
def movie_detail(request, movie_id):
    """Get detailed information for a specific movie"""
    try:
        data = get_movie_details(movie_id)
        return Response(data)
    except Exception as e:
        return Response({"error": str(e)}, status=400)

@api_view(["GET"])
def tmdb_trending(request):
    data = trending_movies()
    # TMDB returns results in a 'results' array
    return Response(data.get("results", []))

@api_view(["POST"])
def update_search(request):
    search_term = request.data.get("searchTerm")
    movie = request.data.get("movie", {})
    
    if not search_term or not movie:
        return Response({"error": "Missing searchTerm or movie"}, status=400)
    
    # Get or create trending search entry
    trending, created = TrendingSearch.objects.get_or_create(
        search_term=search_term,
        movie_id=movie.get("id"),
        defaults={
            "poster_url": movie.get("poster_path", ""),
            "title": movie.get("title"),
            "count": 1
        }
    )
    
    # Increment count if it already exists
    if not created:
        trending.count += 1
        trending.save()
    
    return Response({"status": "ok", "trending": {
        "id": trending.id,
        "search_term": trending.search_term,
        "count": trending.count
    }})

@api_view(["GET"])
def trending(request):
    # Get top 10 trending searches
    trending_searches = TrendingSearch.objects.all()[:10]
    
    data = []
    for search in trending_searches:
        data.append({
            "$id": str(search.id),
            "searchTerm": search.search_term,
            "count": search.count,
            "movie_id": search.movie_id,
            "poster_url": search.poster_url,
            "title": search.title
        })
    
    return Response(data)

#using Groq (fast) and GitHub Models (smart)

class AIChatView(APIView):
    def post(self, request):
        # 1. Get the user's message and conversation history from the frontend
        user_query = request.data.get('message')
        conversation_history = request.data.get('history', [])  # List of {role, content, movies}
        
        if not user_query or not str(user_query).strip():
            return Response({"error": "Missing 'message' in request body"}, status=400)

        # Build conversation context from history
        history_context = ""
        last_recommended_movies = []  # Track last recommendations for explanation requests
        if conversation_history:
            history_lines = []
            for msg in conversation_history[-6:]:  # Last 6 messages for context
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                movies = msg.get('movies', [])
                if role == 'user':
                    history_lines.append(f"User: {content}")
                else:
                    movie_titles = [m.get('title', '') for m in movies] if movies else []
                    if movie_titles:
                        last_recommended_movies = movie_titles  # Track for explanations
                        history_lines.append(f"Assistant: {content}")
                        history_lines.append(f"   >> MOVIES RECOMMENDED: {', '.join(movie_titles)}")
                    else:
                        history_lines.append(f"Assistant: {content}")
            history_context = "\n".join(history_lines)
            print(f"[AIChatView] History context built: {history_context[:200]}...")
            print(f"[AIChatView] Last recommended movies: {last_recommended_movies}")

        # 2. Check if asking for "best/top" movies - should use TMDB data
        best_query_keywords = ["best", "top", "highest rated", "most popular", "top rated", "highest scoring"]
        user_query_lower = user_query.lower()
        is_best_query = any(kw in user_query_lower for kw in best_query_keywords)
        
        # Extract genre/category for TMDB lookup
        genre_map = {
            "anime": {"genre_id": 16, "language": "ja"},
            "action": {"genre_id": 28},
            "comedy": {"genre_id": 35},
            "drama": {"genre_id": 18},
            "horror": {"genre_id": 27},
            "sci-fi": {"genre_id": 878},
            "thriller": {"genre_id": 53},
            "romance": {"genre_id": 10749},
            "animation": {"genre_id": 16},
        }
        
        tmdb_top_movies = []
        detected_genre = None
        saved_watchlist_ids = set()
        rated_exclusion_titles = []
        rated_exclusion_ids = set()

        if is_best_query:
            # First try to find a specific genre
            for keyword, config in genre_map.items():
                if keyword in user_query_lower:
                    detected_genre = keyword
                    tmdb_top_movies = self.get_top_rated_by_genre(config.get("genre_id"), config.get("language"))
                    break
            # If no specific genre found, fetch top-rated movies across all genres
            if not detected_genre:
                tmdb_top_movies = self.get_top_rated_movies()

        # 3. Determine if this request needs personalized recommendations
        personalization_keywords = [
            "for me", "based on my", "my taste", "what should i watch",
            "recommend", "suggest", "suitable for me", "like me",
            "similar to what i like", "match my", "prefer"
        ]
        needs_personalization = any(kw in user_query_lower for kw in personalization_keywords)
        
        # Also detect general discovery requests (need TMDB suggestions)
        discovery_keywords = [
            "get me", "find me", "something to watch", "movie to watch",
            "what to watch", "show me", "give me", "i want to watch"
        ]
        is_discovery = any(kw in user_query_lower for kw in discovery_keywords) or needs_personalization
        
        # ALWAYS fetch TMDB top movies for discovery/recommendation requests
        if is_discovery and not tmdb_top_movies:
            # Check for genre-specific discovery
            for keyword, config in genre_map.items():
                if keyword in user_query_lower:
                    detected_genre = keyword
                    tmdb_top_movies = self.get_top_rated_by_genre(config.get("genre_id"), config.get("language"))
                    break
            if not detected_genre:
                tmdb_top_movies = self.get_top_rated_movies()
        
        # Detect saved/watchlist requests and extract genre keyword
        watchlist_request = any(k in user_query_lower for k in ["saved", "watchlist"])
        watchlist_keyword = next((k for k in genre_map if k in user_query_lower), None)

        # 4. Build user's taste profile and saved watchlist for ALL authenticated users
        user_profile = ""
        saved_watchlist = []
        if getattr(request.user, 'is_authenticated', False):
            # Load saved watchlist (for "saved later" requests)
            try:
                saved_items = (
                    MovieInteraction.objects
                    .filter(user=request.user, is_saved=True)
                    .only("movie_id")
                )
                for item in saved_items:
                    title = get_movie_title(item.movie_id)
                    if title:
                        saved_watchlist.append({"id": item.movie_id, "title": title})
                        saved_watchlist_ids.add(item.movie_id)
            except Exception:
                saved_watchlist = []

            # ALWAYS compute taste profile for authenticated users (not just on keywords)
            try:
                user_profile = get_weighted_user_profile(request.user)
                print(f"[AIChatView] User profile loaded: {len(user_profile)} chars")
            except Exception as e:
                print(f"[AIChatView] Error loading profile: {e}")
                user_profile = ""

            # Collect rated movies to exclude from recommendations (use as preference only)
            try:
                rated_items = (
                    MovieInteraction.objects
                    .filter(user=request.user)
                    .exclude(rating__isnull=True)
                )
                for item in rated_items:
                    if item.is_saved:
                        continue
                    rated_exclusion_ids.add(item.movie_id)
                    title = get_movie_title(item.movie_id)
                    if title:
                        rated_exclusion_titles.append(title)
            except Exception:
                rated_exclusion_titles = []
                rated_exclusion_ids = set()

        rated_section = ""
        if rated_exclusion_titles:
            formatted = ", ".join(rated_exclusion_titles[:20])
            rated_section = (
                "\nRated movies (DO NOT recommend these; use only as preference signals):\n"
                f"{formatted}\n"
            )
        
        # Only add profile to prompt if it exists and is meaningful
        profile_section = f"\nUser Taste Profile:\n{user_profile}\n" if user_profile and "(no interactions yet)" not in user_profile else ""
        if profile_section:
            print(f"[AIChatView] Profile included in prompt ({len(profile_section)} chars)")
        else:
            print(f"[AIChatView] No profile included (user has no interactions or not authenticated)")

        # Handle saved/watchlist requests with genre filtering
        if watchlist_request:
            if saved_watchlist:
                # Filter by genre if keyword detected
                filtered_saved = saved_watchlist
                if watchlist_keyword and watchlist_keyword in genre_map:
                    genre_id = genre_map[watchlist_keyword]["genre_id"]
                    required_language = genre_map[watchlist_keyword].get("language")
                    filtered_saved = []
                    for m in saved_watchlist:
                        movie_genres = self.get_movie_genres(m["id"])
                        if genre_id not in movie_genres:
                            continue
                        # If language required (e.g., anime needs Japanese), check it too
                        if required_language:
                            movie_language = self.get_movie_language(m["id"])
                            if movie_language != required_language:
                                continue
                        filtered_saved.append(m)
                
                if filtered_saved:
                    # Return filtered saved movies
                    saved_movies_details = []
                    for m in filtered_saved[:10]:
                        tmdb_data = self.fetch_tmdb_details(m["title"])
                        if tmdb_data:
                            saved_movies_details.append(tmdb_data)
                    
                    return Response({
                        "response_text": "Here are picks from your saved list.",
                        "movies": saved_movies_details,
                        "provider": "rule-based",
                        "model": "saved-filtered"
                    })
                else:
                    # No matches for this genre in saved list
                    fallback_movies = []
                    genre_label = watchlist_keyword if watchlist_keyword else ""
                    if watchlist_keyword and watchlist_keyword in genre_map:
                        cfg = genre_map[watchlist_keyword]
                        fallback_movies = self.get_top_rated_by_genre(cfg.get("genre_id"), cfg.get("language")) or []
                    else:
                        fallback_movies = self.get_top_rated_movies() or []
                    
                    # Filter out already rated movies (user has watched them)
                    filtered_fallback = [m for m in fallback_movies if m.get("id") not in rated_exclusion_ids]
                    
                    message = f"You don't have any {genre_label} movies saved, but here are some you may like:" if genre_label else "You haven't saved any movies that match your request, but here are some you may like:"
                    
                    return Response({
                        "response_text": message,
                        "movies": filtered_fallback[:5],
                        "provider": "rule-based",
                        "model": "saved-fallback"
                    })
            else:
                # No saved movies at all
                fallback_movies = self.get_top_rated_movies() or []
                # Filter out already rated movies
                filtered_fallback = [m for m in fallback_movies if m.get("id") not in rated_exclusion_ids]
                
                return Response({
                    "response_text": "You haven't saved any movies yet, but here are some you may like:",
                    "movies": filtered_fallback[:5],
                    "provider": "rule-based",
                    "model": "saved-empty"
                })
        
        watchlist_section = ""
        if saved_watchlist:
            formatted = "\n".join([f"- {m['title']} (id: {m['id']})" for m in saved_watchlist[:20]])
            watchlist_section = (
                "\nUser Saved/Watchlist movies (MAX 2 from here for discovery requests, rest must be new):\n"
                f"{formatted}\n"
            )
        
        # Add TMDB data context if we found top-rated movies
        tmdb_context = ""
        if tmdb_top_movies:
            tmdb_list = "\n".join([f"- {m['title']} ({m.get('vote_average', 'N/A')}/10)" for m in tmdb_top_movies])
            heading = detected_genre.title() if detected_genre else "Popular"
            tmdb_context = f"\n\nTMDB {heading} Movies (PICK FROM THIS LIST for new discoveries):\n{tmdb_list}\n\nCRITICAL: For new recommendations, you MUST pick movies from this TMDB list above. These titles are verified to exist."

        # Build conversation history section
        history_section = ""
        last_movies_section = ""
        if history_context:
            history_section = f"\n\n### CONVERSATION HISTORY (use this for context):\n{history_context}\n"
        if last_recommended_movies:
            last_movies_section = f"\n\n### YOUR LAST RECOMMENDATIONS (reference these when asked 'why'):\n{', '.join(last_recommended_movies)}\n"

        # 5. Validate that at least one provider is configured
        if not (getattr(settings, 'GROQ_API_KEY', None) or getattr(settings, 'GITHUB_API_KEY', None)):
            return Response({"error": "No AI provider configured (GROQ_API_KEY or GITHUB_API_KEY)."}, status=500)

        # 7. System Prompt
        # Build TMDB movie list for JSON format
        tmdb_json_movies = ""
        if tmdb_top_movies:
            tmdb_json_movies = ",".join([
                f'{{"title": "{m["title"]}", "year": "{m.get("vote_average", "N/A")}"}}'
                for m in tmdb_top_movies
            ])
        
        prompt = f"""
### ROLE & OBJECTIVE
You are CineMind, a friendly but concise movie expert AI. Your goal is to understand user intent and provide movie data strictly in JSON format.
You have memory of the conversation and can reference previous recommendations.
{history_section}{last_movies_section}
### INPUT DATA CONTEXT
{profile_section}
{watchlist_section}
{rated_section}
{tmdb_context}

### INTENT CLASSIFICATION RULES
Analyze the user's request "{user_query}" and strictly follow the matching rule:

1. GREETING / CHIT-CHAT (e.g., "Hi", "Hello", "How are you?")
   - ACTION: Respond warmly.
   - DATA SOURCE: None.
   - RECOMMENDATIONS: Return an empty list [].

2. FETCH SAVED / WATCHLIST (e.g., "Show me my saved movies", "What's in my watchlist?")
    - ACTION: Retrieve movies explicitly listed in the watchlist above.
    - DATA SOURCE: Watchlist above ONLY.
   - CONSTRAINT: Do NOT add new movies. If list is empty, say so in response_text.

3. DISCOVERY / SUGGESTIONS (e.g., "Suggest something new", "Movies like my saved ones", "Comedy movies", "get me something to watch")
    - ACTION: Generate EXACTLY 5 recommendations based on user taste and TMDB data.
    - DATA SOURCE: MUST use the "TMDB Movies" list provided above. Pick titles EXACTLY as they appear in that list.
    - KEY RULE: When User Taste Profile exists, pick movies from TMDB list that match their LOVES/LIKES categories. Avoid their HATES.
    - WATCHLIST LIMIT: Include AT MOST 2 movies from the user's watchlist. The remaining 3+ MUST be from the TMDB list above.
    - MANDATORY: You MUST return exactly 5 movie recommendations. Never return fewer than 5.
    - CONSTRAINTS:
         * Maximum 2 movies from watchlist - remaining 3+ MUST come from the TMDB list provided.
         * Copy movie titles EXACTLY as shown in the TMDB list (spelling matters for lookup).
         * Do NOT recommend any movie listed in "Rated movies" above.

4. SPECIFIC MOVIE INFO (e.g., "Who directed Inception?", "Rating of The Godfather")
   - ACTION: Answer the specific question.
   - RECOMMENDATIONS: Return an empty list [] unless explicitly asked "and suggest similar ones."

5. EXPLANATION REQUEST (e.g., "why", "why this movie?", "why did you choose", "explain", "specify", "reason")
   - ACTION: Explain why EACH of the movies listed in "YOUR LAST RECOMMENDATIONS" was chosen.
   - DATA SOURCE: Look at "YOUR LAST RECOMMENDATIONS" section above for the movie names.
   - EXPLANATION FORMAT: For EACH movie, explain why it matches the User Taste Profile (their LOVES/LIKES). Be specific: "Movie X was chosen because you love [genre] and it features [specific element]."
   - RESPONSE MUST: Name each movie explicitly and give a unique reason for each one.
   - RECOMMENDATIONS: Return an empty list [].

### RESPONSE FORMAT (STRICT JSON)
Output MUST be a single valid JSON object. Do not include markdown formatting (like ```json).

JSON SCHEMA:
{{
  "response_text": "String. Friendly tone. For explanations, name each movie and reason. Max 300 chars.",
  "recommendations": [
    {{ "title": "Exact Movie Title", "year": "YYYY" }},
    {{ "title": "Exact Movie Title", "year": "YYYY" }}
  ]
}}

### FEW-SHOT EXAMPLES (Follow this logic)
User: "Hi there"
Output: {{ "response_text": "Hello! I'm CineMind. Ready to find your next favorite movie?", "recommendations": [] }}

User: "Show my watchlist"
Output: {{ "response_text": "Here are the movies you've saved so far:", "recommendations": [ {{ "title": "Dune", "year": "2021" }} ] }}

User: "Recommend something new like Dune"
Output: {{ "response_text": "If you loved Dune, you might enjoy these sci-fi epics:", "recommendations": [ {{ "title": "Blade Runner 2049", "year": "2017" }}, {{ "title": "Arrival", "year": "2016" }}, {{ "title": "Interstellar", "year": "2014" }}, {{ "title": "The Matrix", "year": "1999" }}, {{ "title": "Ex Machina", "year": "2014" }} ] }}

User: "get me something to watch"
Output: {{ "response_text": "Here are 5 picks based on your taste:", "recommendations": [ {{ "title": "Inception", "year": "2010" }}, {{ "title": "The Dark Knight", "year": "2008" }}, {{ "title": "Parasite", "year": "2019" }}, {{ "title": "Whiplash", "year": "2014" }}, {{ "title": "Mad Max: Fury Road", "year": "2015" }} ] }}

User: "why did you choose those movies"
Output: {{ "response_text": "I picked Inception because you love mind-bending thrillers. The Dark Knight fits your love for action. Parasite matches your interest in drama. Whiplash was chosen for its intensity. Mad Max fits your action taste!", "recommendations": [] }}

User: "explain why you recommended those"
Output: {{ "response_text": "1) Movie A - matches your love for sci-fi. 2) Movie B - fits your action preference. 3) Movie C - you enjoy thrillers. 4) Movie D - based on your drama interest. 5) Movie E - matches your comedy likes!", "recommendations": [] }}

### FINAL USER REQUEST
User Request: "{user_query}"
"""

        print(f"[AIChatView] About to call AI provider...")
        print(f"[AIChatView] Prompt summary: profile={bool(profile_section)} watchlist={bool(watchlist_section)} tmdb={bool(tmdb_context)}")
        
        # 6. Send to selected provider requesting JSON
        raw_text = ""
        provider = choose_provider(user_query, needs_personalization)
        provider_used = None
        model_used = None
        try:
            if provider == "github" and getattr(settings, 'GITHUB_API_KEY', None):
                raw_text = chat_with_github_models(prompt)
                provider_used = "github"
                model_used = os.getenv("GITHUB_MODEL", "gpt-4o")
            else:
                raw_text = chat_with_groq(prompt)
                provider_used = "groq"
                model_used = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        except Exception as primary_err:
            # Fallback to the other provider if available
            try:
                if provider == "github" and getattr(settings, 'GROQ_API_KEY', None):
                    raw_text = chat_with_groq(prompt)
                    provider_used = "groq:fallback"
                    model_used = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
                elif provider == "groq" and getattr(settings, 'GITHUB_API_KEY', None):
                    raw_text = chat_with_github_models(prompt)
                    provider_used = "github:fallback"
                    model_used = os.getenv("GITHUB_MODEL", "gpt-4o")
                else:
                    raise primary_err
            except Exception as fallback_err:
                print("[AIChatView] provider errors:", primary_err, fallback_err)
                return Response({
                    "response_text": "I couldn't reach the AI service right now. Try again soon.",
                    "movies": [],
                    "error": str(primary_err)
                }, status=200)

        print(f"[AIChatView] provider={provider_used or provider} model={model_used}")

        # 7. Parse JSON robustly; avoid repeating the generic fallback message
        print(f"[AIChatView] AI response received ({len(raw_text)} chars), parsing JSON...")
        raw_text = raw_text or ''

        ai_data = None

        def try_parse_json(payload: str):
            try:
                return json.loads(payload)
            except Exception:
                return None

        # First try direct parse
        ai_data = try_parse_json(raw_text)

        # If that fails, attempt to extract the first JSON object from the text
        if ai_data is None and raw_text:
            match = re.search(r"\{[\s\S]*\}", raw_text)
            if match:
                ai_data = try_parse_json(match.group(0))

        # Final fallback: at least return the raw text so the user sees variety
        if ai_data is None:
            ai_data = {
                "response_text": raw_text.strip() or "I couldn't parse the AI response.",
                "recommendations": []
            }

        # 8. Validate with TMDB to get Posters (optional), and filter out rated exclusions unless saved
        final_movies = []
        for rec in ai_data.get('recommendations', []):
            title = rec.get('title') if isinstance(rec, dict) else None
            if not title:
                continue
            try:
                tmdb_data = self.fetch_tmdb_details(title)
                if tmdb_data:
                    tmdb_id = tmdb_data.get('id')
                    if tmdb_id in rated_exclusion_ids and tmdb_id not in saved_watchlist_ids:
                        # Skip recommending rated (non-saved) movies
                        continue
                    final_movies.append(tmdb_data)
            except Exception as fetch_err:
                # Log but skip failures
                print(f"[AIChatView] TMDB search failed for '{title}': {fetch_err}")
                continue

        return Response({
            "response_text": ai_data.get('response_text', ''),
            "movies": final_movies,
            "provider": provider_used or provider,
            "model": model_used
        })

    def get_movie_genres(self, movie_id):
        """Get genre IDs for a movie from TMDB"""
        headers = {
            "Authorization": f"Bearer {settings.TMDB_API_KEY}",
            "accept": "application/json",
        }
        url = f"https://api.themoviedb.org/3/movie/{movie_id}"
        
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            return [g["id"] for g in data.get("genres", [])]
        except Exception as e:
            print(f"[AIChatView.get_movie_genres] error: {e}")
            return []

    def get_movie_language(self, movie_id):
        """Get original language for a movie from TMDB (e.g., 'ja' for Japanese)"""
        headers = {
            "Authorization": f"Bearer {settings.TMDB_API_KEY}",
            "accept": "application/json",
        }
        url = f"https://api.themoviedb.org/3/movie/{movie_id}"
        
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            return data.get("original_language", "")
        except Exception as e:
            print(f"[AIChatView.get_movie_language] error: {e}")
            return ""

    def fetch_tmdb_details(self, title):
        """Fetch movie details from TMDB using Bearer token to get poster and ID"""
        headers = {
            "Authorization": f"Bearer {settings.TMDB_API_KEY}",
            "accept": "application/json",
        }
        url = f"https://api.themoviedb.org/3/search/movie"
        params = {"query": title}
        
        try:
            resp = requests.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            if data.get('results'):
                movie = data['results'][0]
                return {
                    "id": movie.get('id'),
                    "title": movie.get('title'),
                    "poster_path": movie.get('poster_path'),
                    "overview": movie.get('overview')
                }
        except Exception as e:
            print(f"[AIChatView.fetch_tmdb_details] error: {e}")
        return None

    def get_top_rated_by_genre(self, genre_id, language=None):
        """Fetch top-rated movies from TMDB by genre and optional language"""
        headers = {
            "Authorization": f"Bearer {settings.TMDB_API_KEY}",
            "accept": "application/json",
        }
        url = "https://api.themoviedb.org/3/discover/movie"
        
        params = {
            "with_genres": genre_id,
            "sort_by": "vote_average.desc",
            "vote_count.gte": 1000,  # Minimum votes for credibility
            "page": 1
        }
        
        # Add language filter if specified (e.g., "ja" for anime)
        if language:
            params["with_original_language"] = language
        
        try:
            resp = requests.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            
            results = []
            for movie in data.get('results', [])[:20]:  # Fetch 20 to ensure 5 unrated after filtering
                results.append({
                    "id": movie.get('id'),
                    "title": movie.get('title'),
                    "poster_path": movie.get('poster_path'),
                    "overview": movie.get('overview'),
                    "vote_average": movie.get('vote_average')
                })
            return results
        except Exception as e:
            print(f"[AIChatView.get_top_rated_by_genre] error: {e}")
            return []
    def get_top_rated_movies(self):
        """Fetch top-rated movies across all genres when no specific genre is provided"""
        headers = {
            "Authorization": f"Bearer {settings.TMDB_API_KEY}",
            "accept": "application/json",
        }
        url = "https://api.themoviedb.org/3/discover/movie"
        
        params = {
            "sort_by": "vote_average.desc",
            "vote_count.gte": 2000,  # Higher threshold for quality
            "page": 1
        }
        
        try:
            resp = requests.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            
            results = []
            for movie in data.get('results', [])[:20]:  # Fetch 20 to ensure 5 unrated after filtering
                results.append({
                    "id": movie.get('id'),
                    "title": movie.get('title'),
                    "poster_path": movie.get('poster_path'),
                    "overview": movie.get('overview'),
                    "vote_average": movie.get('vote_average')
                })
            return results
        except Exception as e:
            print(f"[AIChatView.get_top_rated_movies] error: {e}")
            return []