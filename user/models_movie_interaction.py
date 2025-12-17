from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class MovieInteraction(models.Model):
    """
    Tracks user interactions with movies (likes and saves)
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='movie_interactions')
    movie_id = models.IntegerField()  # TMDB movie ID
    is_liked = models.BooleanField(default=False)
    is_saved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'movie_interactions'
        unique_together = ('user', 'movie_id')
        indexes = [
            models.Index(fields=['user', 'movie_id']),
            models.Index(fields=['user', 'is_liked']),
            models.Index(fields=['user', 'is_saved']),
        ]

    def __str__(self):
        return f"{self.user.email} - Movie {self.movie_id}"
