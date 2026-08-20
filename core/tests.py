from unittest.mock import Mock, patch

import requests
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from core.models import TrendingSearch
from core.services.ai_engine import get_movie_title, get_weighted_user_profile
from user.models import MovieInteraction
from user.throttles import ChatRateThrottle

User = get_user_model()


class MovieDiscoveryTests(APITestCase):
    @patch("core.views.fetch_movies")
    def test_movie_search_forwards_query_and_page(self, fetch_movies):
        fetch_movies.return_value = {
            "results": [{"id": 1, "title": "Arrival"}],
            "page": 3,
            "total_pages": 8,
        }

        response = self.client.get(reverse("movies"), {"q": "arrival", "page": "3"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["page"], 3)
        fetch_movies.assert_called_once_with("arrival", 3)

    @patch("core.views.fetch_movies", side_effect=requests.Timeout)
    def test_movie_search_timeout_returns_gateway_timeout(self, _fetch_movies):
        response = self.client.get(reverse("movies"), {"q": "slow"})

        self.assertEqual(response.status_code, status.HTTP_504_GATEWAY_TIMEOUT)
        self.assertEqual(response.data["error"], "TMDB request timed out")

    @patch("core.views.fetch_movies", side_effect=requests.ConnectionError)
    def test_movie_search_failure_returns_bad_gateway(self, _fetch_movies):
        response = self.client.get(reverse("movies"), {"q": "offline"})

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)

    def test_trending_search_updates_existing_record(self):
        payload = {
            "searchTerm": "dune",
            "movie": {"id": 438631, "title": "Dune", "poster_path": "/dune.jpg"},
        }

        first = self.client.post(reverse("update_search"), payload, format="json")
        second = self.client.post(reverse("update_search"), payload, format="json")

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.data["trending"]["count"], 2)
        self.assertEqual(TrendingSearch.objects.get().count, 2)


class PersonalizationTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="taste-test",
            email="taste@example.com",
            password="correct horse battery staple",
        )

    def test_weighted_profile_uses_saved_metadata_without_tmdb_calls(self):
        MovieInteraction.objects.create(
            user=self.user,
            movie_id=1,
            movie_title="Loved Film",
            rating=5,
        )
        MovieInteraction.objects.create(
            user=self.user,
            movie_id=2,
            movie_title="Avoid Film",
            rating=1,
        )
        MovieInteraction.objects.create(
            user=self.user,
            movie_id=3,
            movie_title="Watch Later",
            is_saved=True,
        )

        with patch("core.services.ai_engine.requests.get") as tmdb_get:
            profile = get_weighted_user_profile(self.user)

        self.assertIn("LOVES (Strongest match): Loved Film", profile)
        self.assertIn("HATES (Avoid similar movies): Avoid Film", profile)
        self.assertIn("WATCHLIST (High interest): Watch Later", profile)
        tmdb_get.assert_not_called()

    @patch("core.services.ai_engine.requests.get")
    def test_title_lookup_persists_tmdb_metadata(self, tmdb_get):
        interaction = MovieInteraction.objects.create(user=self.user, movie_id=550)
        response = Mock(status_code=200)
        response.json.return_value = {"title": "Fight Club", "poster_path": "/fight.jpg"}
        tmdb_get.return_value = response

        self.assertEqual(get_movie_title(550), "Fight Club")
        interaction.refresh_from_db()
        self.assertEqual(interaction.movie_title, "Fight Club")
        self.assertEqual(interaction.poster_path, "/fight.jpg")

        cache.clear()
        self.assertEqual(get_movie_title(550), "Fight Club")
        tmdb_get.assert_called_once()


@override_settings(
    GROQ_API_KEY="groq-test",
    GROQ_MODEL="openai/gpt-oss-20b",
    GROQ_FALLBACK_MODEL="openai/gpt-oss-120b",
)
class AIChatTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="chat-test",
            email="chat@example.com",
            password="correct horse battery staple",
        )
        self.client.force_authenticate(self.user)

    def test_chat_requires_authentication(self):
        anonymous = APIClient()

        response = anonymous.post(reverse("ai_chat"), {"message": "Hello"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch.object(ChatRateThrottle, "rate", "1/min")
    @patch(
        "core.views.chat_with_groq",
        return_value='{"response_text": "Hello!", "recommendations": []}',
    )
    def test_chat_is_rate_limited(self, _groq):
        first = self.client.post(reverse("ai_chat"), {"message": "Hello"}, format="json")
        second = self.client.post(reverse("ai_chat"), {"message": "Hello again"}, format="json")

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    @patch(
        "core.views.chat_with_groq",
        side_effect=[
            RuntimeError("primary model down"),
            '{"response_text": "Fallback worked", "recommendations": []}',
        ],
    )
    def test_ai_provider_falls_back(self, groq):
        response = self.client.post(
            reverse("ai_chat"),
            {"message": "Explain a movie"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["provider"], "groq:fallback")
        self.assertEqual(response.data["response_text"], "Fallback worked")
        self.assertEqual(
            [call.kwargs["model"] for call in groq.call_args_list],
            ["openai/gpt-oss-20b", "openai/gpt-oss-120b"],
        )

    @patch("core.views.chat_with_groq", return_value="plain text from provider")
    def test_invalid_llm_json_is_handled(self, _groq):
        response = self.client.post(
            reverse("ai_chat"),
            {"message": "Hello"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["response_text"], "plain text from provider")
        self.assertEqual(response.data["movies"], [])


class MovieInteractionOwnershipTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="correct horse battery staple",
        )
        self.other_user = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="correct horse battery staple",
        )
        MovieInteraction.objects.create(
            user=self.other_user,
            movie_id=42,
            movie_title="Private Movie",
            rating=5,
            is_saved=True,
        )
        self.client.force_authenticate(self.owner)

    def test_saved_and_rated_movies_are_scoped_to_the_owner(self):
        interaction = self.client.get(reverse("get_movie_interaction", args=[42]))
        saved = self.client.get(reverse("get_saved_movies"))

        self.assertIsNone(interaction.data["rating"])
        self.assertFalse(interaction.data["is_saved"])
        self.assertEqual(saved.data["movie_ids"], [])

    def test_interaction_metadata_is_saved_with_the_rating(self):
        response = self.client.post(
            reverse("rate_movie", args=[99]),
            {
                "rating": 4.5,
                "movie": {"title": "Metadata Movie", "poster_path": "/metadata.jpg"},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        interaction = MovieInteraction.objects.get(user=self.owner, movie_id=99)
        self.assertEqual(interaction.movie_title, "Metadata Movie")
        self.assertEqual(interaction.poster_path, "/metadata.jpg")
