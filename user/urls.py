from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('profile/', views.get_profile, name='get_profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('password/change/', views.change_password, name='change_password'),
    path('movies/<int:movie_id>/rate/', views.rate_movie, name='rate_movie'),
    path('movies/<int:movie_id>/save/', views.toggle_movie_save, name='toggle_movie_save'),
    path('movies/<int:movie_id>/interaction/', views.get_movie_interaction, name='get_movie_interaction'),
    path('movies/saved/', views.get_saved_movies, name='get_saved_movies'),
]
