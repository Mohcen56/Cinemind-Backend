from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    email = models.EmailField(unique=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, help_text='User profile picture')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email

    class Meta:
        db_table = 'users'


class MovieInteraction(models.Model):
    """
    Tracks user interactions with movies (rating and saves)
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='movie_interactions')
    movie_id = models.IntegerField()  # TMDB movie ID
    rating = models.DecimalField(max_digits=2, decimal_places=1, null=True, blank=True, help_text='User rating (0-5 with 0.5 increments)')
    is_saved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'movie_interactions'
        unique_together = ('user', 'movie_id')
        indexes = [
            models.Index(fields=['user', 'movie_id']),
            models.Index(fields=['user', 'rating']),
            models.Index(fields=['user', 'is_saved']),
        ]

    def __str__(self):
        return f"{self.user.email} - Movie {self.movie_id}"
