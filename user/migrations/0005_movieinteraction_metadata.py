from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0004_revoke_exposed_credentials"),
    ]

    operations = [
        migrations.AddField(
            model_name="movieinteraction",
            name="movie_title",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="movieinteraction",
            name="poster_path",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
    ]
