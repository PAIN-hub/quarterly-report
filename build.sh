#!/usr/bin/env bash
# exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Collect static files for Whitenoise
python manage.py collectstatic --no-input

# Run migrations automatically on deploy
python manage.py migrate
