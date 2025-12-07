from django.db import models

class TrendingSearch(models.Model):
    search_term = models.CharField(max_length=255)
    movie_id = models.IntegerField()
    poster_url = models.CharField(max_length=500, null=True, blank=True)
    title = models.CharField(max_length=255, null=True, blank=True)
    count = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-count', '-updated_at']

    def __str__(self):
        return f"{self.search_term} (ID: {self.movie_id})"

