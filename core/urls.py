from django.urls import path
from core.views import movies, update_search, trending, tmdb_trending, movie_detail

urlpatterns = [
    path("movies/", movies),
    path("movies/<int:movie_id>/", movie_detail),
    path("movies/trending/", tmdb_trending),
    path("search/update/", update_search),
    path("search/trending/", trending),
]
