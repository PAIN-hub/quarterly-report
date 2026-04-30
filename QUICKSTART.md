# Quick Start Guide - MDA Report Portal Backend

Get the Django backend running in 5 minutes.

## 1. Setup (2 minutes)

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.template .env
```

## 2. Initialize Database (1 minute)

```bash
python manage.py migrate
python manage.py createsuperuser
```

Follow the prompts. Example:
- Access ID: `ADMIN-SYS-001`
- Password: `SecurePassword123!`

## 3. Run Server (1 minute)

```bash
python manage.py runserver
```

Server running at: `http://localhost:8000`

## 4. Test API (1 minute)

### Login
```bash
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "access_id": "ADMIN-SYS-001",
    "password": "SecurePassword123!"
  }'
```

Response:
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": "...",
    "access_id": "ADMIN-SYS-001",
    "name": "Admin",
    "role": "SYSTEM_ADMIN"
  }
}
```

### Get Current User
```bash
curl http://localhost:8000/api/v1/users/me/ \
  -H "Authorization: Bearer <access_token>"
```

## Next Steps

- Access Django Admin: `http://localhost:8000/admin/`
- Read full README: `README.md`
- Explore API endpoints: See API section in README
- Create test data: See management commands below

## Useful Commands

```bash
# Create test users
python manage.py createsuperuser

# Create backup
python manage.py shell
>>> from api.utils import create_backup
>>> from api.models import User
>>> user = User.objects.first()
>>> backup = create_backup(user, "Test backup")

# Export data
curl http://localhost:8000/api/v1/export/export_json/ \
  -H "Authorization: Bearer <token>" \
  > data_export.json

# Run migrations
python manage.py migrate

# Create migrations
python manage.py makemigrations

# Check migrations status
python manage.py showmigrations
```

## Common Issues

**Port 8000 in use:**
```bash
python manage.py runserver 8001
```

**Module not found:**
```bash
# Ensure venv is activated
source venv/bin/activate
```

**Database locked:**
- Close all database connections
- Delete `db.sqlite3` if needed and re-migrate

## Frontend Integration

Add to your frontend's `.env`:
```
REACT_APP_API_URL=http://localhost:8000/api/v1
```

Update CORS in `backend/.env`:
```
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

## Production Deployment

See README.md for:
- PostgreSQL setup
- Gunicorn configuration
- Docker deployment
- Security settings
- Environment variables

## Get Help

- Check logs: `logs/django.log`
- Django docs: `https://docs.djangoproject.com/`
- DRF docs: `https://www.django-rest-framework.org/`
