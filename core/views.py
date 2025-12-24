from django.shortcuts import render
# your_app/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from django.conf import settings
import google.genai as genai
import json
import requests
from rest_framework.decorators import api_view
from rest_framework.response import Response
from core.services.ai_engine import get_weighted_user_profile
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



# Initialize Gemini client
_gemini_client = None

def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        api_key = getattr(settings, 'GEMINI_API_KEY', None)
        if not api_key:
            raise ValueError("GEMINI_API_KEY not configured")
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client

# Choose an available Gemini model
def _choose_gemini_model():
    preferred = [
        "gemini-2.5-flash",
        "gemini-3-flash",
       
    ]
    # For google.genai, use the model names directly
    # These are validated at call time, so just return the first preferred model
    return preferred[0]

class AIChatView(APIView):
    def post(self, request):
        # 1. Get the user's message from the frontend
        user_query = request.data.get('message')
        if not user_query or not str(user_query).strip():
            return Response({"error": "Missing 'message' in request body"}, status=400)

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
        if is_best_query:
            for keyword, config in genre_map.items():
                if keyword in user_query_lower:
                    detected_genre = keyword
                    tmdb_top_movies = self.get_top_rated_by_genre(config.get("genre_id"), config.get("language"))
                    break

        # 3. Determine if this request needs personalized recommendations
        # Keywords that indicate wanting personalized suggestions based on taste
        personalization_keywords = [
            "for me", "based on my", "my taste", "what should i watch",
            "recommend", "suggest", "suitable for me", "like me",
            "similar to what i like", "match my", "prefer"
        ]
        needs_personalization = any(kw in user_query_lower for kw in personalization_keywords)
        
        # 4. Build user's taste profile only if needed
        user_profile = ""
        if needs_personalization:
            try:
                if getattr(request.user, 'is_authenticated', False):
                    user_profile = get_weighted_user_profile(request.user)
                else:
                    user_profile = ""  # No profile for guests asking generic questions
            except Exception as e:
                user_profile = ""  # If we fail, just continue without profile
        
        # Only add profile to prompt if it exists and is meaningful
        profile_section = f"\nYour User Profile:\n{user_profile}\n" if user_profile and "(no interactions yet)" not in user_profile else ""
        
        # Add TMDB data context if we found top-rated movies
        tmdb_context = ""
        if tmdb_top_movies:
            tmdb_list = "\n".join([f"- {m['title']} ({m.get('year', 'N/A')}) - Rating: {m.get('vote_average', 'N/A')}/10" for m in tmdb_top_movies])
            tmdb_context = f"\n\nTMDB Top-Rated {detected_genre.title()} Movies (by user scores):\n{tmdb_list}\n\nIMPORTANT: Prioritize these movies in your recommendations. These are sorted by actual user ratings."

        # 5. Validate API key presence early
        if not getattr(settings, 'GEMINI_API_KEY', None):
            return Response({
                "error": "GEMINI_API_KEY not configured",
            }, status=500)

        # 6. Choose an available model dynamically
        model_name = _choose_gemini_model()
        print("[AIChatView] using model:", model_name)
        
        # Get Gemini client
        try:
            client = _get_gemini_client()
        except ValueError as e:
            return Response({"error": str(e)}, status=500)

        # 7. System Prompt
        prompt = f"""
        You are CineMind, a friendly movie expert AI assistant.{profile_section}{tmdb_context}
        User Request: "{user_query}"

        INSTRUCTIONS:
        1. First, understand what the user is asking. Are they:
           - Just greeting you? (e.g., "hi", "hello") → Just respond warmly without recommendations
           - Asking a question about movies? → Answer directly, optionally add 2-3 recommendations if relevant
           - Explicitly asking for recommendations? → Provide 5 recommendations (use profile if available)
           - Asking for info about a specific movie? → Provide the info without recommendations
           - Asking for best movies in a genre/category? → PRIORITIZE the TMDB top-rated list provided above
        
        2. ONLY include movie recommendations if:
           - The user explicitly asks ("recommend", "suggest", "what should I watch")
           - OR the request is asking for best movies in a specific genre/category
           - DO NOT force recommendations for simple greetings or generic questions
        
        3. When using recommendations:
           - If TMDB top-rated data is provided: PRIORITIZE those movies first (they have real user scores)
           - If user profile is provided: Use it to personalize recommendations
           - If NO profile and NO TMDB data: Give objective best movies based on your knowledge
           - Do NOT recommend movies from 'HATES' category (if profile available)
        
        4. Always return valid JSON (no markdown, no code blocks).

        RESPONSE JSON FORMAT (choose based on request):
        
        For simple responses (no recommendations):
        {{
            "response_text": "Your conversational response here.",
            "recommendations": []
        }}
        
        For responses with recommendations:
        {{
            "response_text": "Your response explaining the recommendations.",
            "recommendations": [
                {{"title": "Real Movie Title 1", "year": "2023"}},
                {{"title": "Real Movie Title 2", "year": "2022"}},
                ...
            ]
        }}
        
        Remember: Empty recommendations array is perfectly fine for general conversation!
        """

        # 6. Send to Gemini requesting JSON
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
        except Exception as e:
            # Log the error for diagnostics
            print("[AIChatView] generate_content error:", str(e))
            # Fallback minimal response with error details included
            return Response({
                "response_text": "I couldn't reach the AI service right now. Try again soon.",
                "movies": [],
                "error": str(e)
            }, status=200)

        # 7. Parse JSON robustly
        ai_data = None
        try:
            ai_data = json.loads(getattr(response, 'text', '') or '{}')
        except Exception:
            # Try alternative extraction from candidates
            try:
                candidates = getattr(response, 'candidates', [])
                text = ''
                if candidates and hasattr(candidates[0], 'content'):
                    parts = getattr(candidates[0].content, 'parts', [])
                    if parts and hasattr(parts[0], 'text'):
                        text = parts[0].text
                ai_data = json.loads(text)
            except Exception:
                # Final fallback JSON
                ai_data = {
                    "response_text": "Here are some general recommendations you might enjoy.",
                    "recommendations": []
                }

        # 8. Validate with TMDB to get Posters (optional)
        final_movies = []
        for rec in ai_data.get('recommendations', []):
            title = rec.get('title') if isinstance(rec, dict) else None
            if not title:
                continue
            try:
                tmdb_data = self.fetch_tmdb_details(title)
                if tmdb_data:
                    final_movies.append(tmdb_data)
            except Exception as fetch_err:
                # Log but skip failures
                print(f"[AIChatView] TMDB search failed for '{title}': {fetch_err}")
                continue

        return Response({
            "response_text": ai_data.get('response_text', ''),
            "movies": final_movies
        })

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
            for movie in data.get('results', [])[:5]:
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
