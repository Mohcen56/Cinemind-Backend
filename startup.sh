#!/bin/bash

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --noinput

# Run migrations
python manage.py migrate --noinput

# Start Gunicorn server
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
