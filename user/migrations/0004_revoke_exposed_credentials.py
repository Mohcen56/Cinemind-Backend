from datetime import datetime, timezone

from django.contrib.auth.hashers import make_password
from django.db import migrations


# The last distinct db.sqlite3 snapshot in Git was committed on 2026-01-07.
EXPOSURE_CUTOFF = datetime(2026, 1, 8, tzinfo=timezone.utc)


def revoke_exposed_credentials(apps, schema_editor):
    Token = apps.get_model("authtoken", "Token")
    Session = apps.get_model("sessions", "Session")
    User = apps.get_model("user", "User")

    Token.objects.all().delete()
    Session.objects.all().delete()

    # Password hashes from the leaked snapshot can be attacked offline. Make
    # affected passwords unusable so recovery must happen through a trusted
    # admin/password-reset process.
    unusable_password = make_password(None)
    User.objects.filter(date_joined__lt=EXPOSURE_CUTOFF).update(password=unusable_password)


class Migration(migrations.Migration):
    dependencies = [
        ("authtoken", "0004_alter_tokenproxy_options"),
        ("sessions", "0001_initial"),
        ("user", "0003_remove_movieinteraction_movie_inter_user_id_ca0ecd_idx_and_more"),
    ]

    operations = [
        migrations.RunPython(revoke_exposed_credentials, migrations.RunPython.noop),
    ]
