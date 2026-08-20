from django.urls import path

from core.views import AIChatView, movie_detail, movies, tmdb_trending, trending, update_search

urlpatterns = [
    path("movies/", movies, name="movies"),
    path("movies/<int:movie_id>/", movie_detail, name="movie_detail"),
    path("movies/trending/", tmdb_trending, name="tmdb_trending"),
    path("search/update/", update_search, name="update_search"),
    path("search/trending/", trending, name="trending_searches"),
    # Chat endpoint lives under /api/ via project-level include, so no extra 'api/' prefix here
    path("chat/", AIChatView.as_view(), name="ai_chat"),
]
