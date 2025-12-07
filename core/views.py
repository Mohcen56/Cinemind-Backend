from django.shortcuts import render

from rest_framework.decorators import api_view
from rest_framework.response import Response
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

