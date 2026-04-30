# MDA Report Portal - Django Backend

A production-ready Django REST Framework backend for the MDA Report Portal with offline sync, conflict resolution, audit logging, and comprehensive data backup/recovery.

## Features

### Authentication & Authorization
- **Access ID Authentication**: Users login with unique Access IDs (e.g., `KTS-MDA-001`) + password
- **JWT Tokens**: Secure token-based authentication with refresh mechanism
- **Role-Based Access Control**: 4 user roles with fine-grained permissions
  - `MDA_USER`: Regular MDA staff member
  - `MDA_ADMIN`: Administrator for a specific MDA
  - `REGIONAL_OFFICER`: Regional supervisor
  - `SYSTEM_ADMIN`: Full system access

### Report Management
- **Version Tracking**: Every report change creates a version snapshot
- **Conflict Detection**: Automatic detection of concurrent edits with resolution options
- **Soft Delete**: Reports marked as deleted for audit trail preservation
- **Full History**: Complete version history with change descriptions and author tracking

### Offline Synchronization
- **Bulk Sync**: Process multiple pending actions in a single transaction
- **Conflict Resolution**: Three options when versions conflict
  - Overwrite server with local changes
  - Keep server version and discard local changes
  - Manual review and conflict modal
- **Delta Sync**: Efficient sync of only changed data since last sync

### Audit & Compliance
- **Comprehensive Audit Logging**: Every action logged with user, timestamp, IP, and changes
- **10+ Action Types**: CREATE, UPDATE, DELETE, SYNC, LOGIN, CONFLICT, EXPORT, BACKUP, RESTORE
- **Resource Tracking**: Complete history of who changed what and when
- **Audit Export**: Download audit logs as JSON for compliance

### Data Backup & Recovery
- **Manual & Automated Backups**: Create backups on-demand or schedule automatic backups
- **Complete Data Snapshots**: Users, reports, versions, and audit logs
- **Integrity Verification**: SHA-256 hashes verify backup integrity before restore
- **Point-in-Time Restore**: Restore system to any previous backup state
- **Backup Metadata**: Size, type, creation date, and restoration tracking

### Data Export
- **JSON Export**: Export all data for analysis or migration
- **Selective Export**: Include/exclude audit logs, deleted records
- **Role-Based Access**: System admins export all data, users export their own
- **Download as File**: Direct browser download of export file

### Security
- **CORS Configuration**: Secure cross-origin requests
- **Rate Limiting**: Prevent abuse (via middleware)
- **CSRF Protection**: Token-based CSRF protection
- **Password Hashing**: Strong bcrypt password hashing
- **Token Rotation**: Refresh tokens prevent token fixation
- **Security Headers**: XSS, clickjacking, and CSP protection

## Project Structure

```
backend/
├── manage.py                  # Django management script
├── requirements.txt           # Python dependencies
├── .env.template             # Environment variables template
├── config/                   # Django configuration
│   ├── __init__.py
│   ├── settings.py           # Main Django settings
│   ├── urls.py              # Root URL configuration
│   └── wsgi.py              # WSGI application
├── api/                      # Main API application
│   ├── __init__.py
│   ├── models.py            # Database models (User, Report, AuditLog, Backup, etc.)
│   ├── views.py             # API endpoints and viewsets
│   ├── serializers.py       # DRF serializers for data validation
│   ├── urls.py              # API URL routing
│   ├── utils.py             # Helper functions (audit, backup, export)
│   ├── signals.py           # Django signals for auto-logging
│   ├── apps.py              # App configuration
│   └── admin.py             # Django admin interface
├── logs/                    # Application logs
└── backups/                 # Backup storage
```

## Database Models

### User
- Custom user model with Access ID authentication
- Roles: MDA_USER, MDA_ADMIN, REGIONAL_OFFICER, SYSTEM_ADMIN
- Tracks last_login and last_sync for offline detection
- Linked to MDA for filtering and permissions

### Report
- Core report data stored as JSON for flexibility
- Version tracking with automatic increment
- Soft delete with is_deleted flag
- Full timestamp audit trail (created_at, updated_at, last_modified)
- Synced_at for tracking last server sync

### ReportVersion
- Complete snapshot of each report version
- Links changes to specific users
- Stores change descriptions for audit trail
- Unique constraint on (report, version_number)

### AuditLog
- Tracks every system action (CREATE, UPDATE, DELETE, SYNC, etc.)
- Stores IP address and user agent for security
- Records what changed with old/new values
- Indexed for efficient querying

### Backup
- Complete data snapshots with SHA-256 integrity hash
- Tracks backup type (MANUAL, SCHEDULED, AUTOMATED)
- Restoration metadata (who, when, backup used)
- Size tracking for monitoring storage

### SyncConflict
- Records conflicts when versions diverge
- Stores both local and server versions of data
- Tracks resolution (OVERWRITE, KEEP_SERVER, PENDING)
- Links to user and timestamp for audit

## API Endpoints

### Authentication
```
POST   /api/v1/auth/login/              # Login with Access ID & password
POST   /api/v1/auth/token/refresh/      # Refresh JWT token
```

### Users
```
GET    /api/v1/users/                   # List users (filtered by role)
POST   /api/v1/users/                   # Create user (SYSTEM_ADMIN only)
GET    /api/v1/users/{id}/              # Get user details
PATCH  /api/v1/users/{id}/              # Update user
DELETE /api/v1/users/{id}/              # Deactivate user
GET    /api/v1/users/me/                # Get current user
PATCH  /api/v1/users/{id}/change_password/  # Change password
```

### Reports
```
GET    /api/v1/reports/                 # List reports
POST   /api/v1/reports/                 # Create report
GET    /api/v1/reports/{id}/            # Get report details
PATCH  /api/v1/reports/{id}/            # Update report (with conflict checking)
DELETE /api/v1/reports/{id}/            # Soft delete report
GET    /api/v1/reports/{id}/versions/   # Get version history
POST   /api/v1/reports/{id}/revert/     # Revert to version
```

### Sync & Conflicts
```
POST   /api/v1/sync/bulk_sync/          # Sync multiple offline changes
GET    /api/v1/sync/changes_since/      # Get changes since timestamp
POST   /api/v1/conflicts/{id}/resolve/  # Resolve conflict
```

### Audit & Backup
```
GET    /api/v1/audit-logs/              # List audit logs
POST   /api/v1/backups/                 # Create manual backup
GET    /api/v1/backups/                 # List backups
GET    /api/v1/backups/{id}/verify/     # Verify backup integrity
POST   /api/v1/backups/{id}/restore/    # Restore from backup
```

### Data Export
```
GET    /api/v1/export/export_json/      # Download JSON export
```

## Setup & Installation

### Prerequisites
- Python 3.10+
- pip or poetry for dependency management
- SQLite (included) or PostgreSQL for production

### Installation Steps

1. **Navigate to backend directory**
   ```bash
   cd backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.template .env
   # Edit .env with your settings
   ```

5. **Run migrations**
   ```bash
   python manage.py migrate
   ```

6. **Create superuser**
   ```bash
   python manage.py createsuperuser
   ```

7. **Create initial test users** (optional)
   ```bash
   python manage.py create_test_users
   ```

8. **Run development server**
   ```bash
   python manage.py runserver
   ```

Server runs on `http://localhost:8000`

## Configuration

### Database Setup

#### SQLite (Development - Default)
Already configured in `settings.py`. No additional setup needed.

#### PostgreSQL (Production)

1. Install PostgreSQL
2. Update `settings.py`:
   ```python
   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.postgresql',
           'NAME': os.getenv('DB_NAME'),
           'USER': os.getenv('DB_USER'),
           'PASSWORD': os.getenv('DB_PASSWORD'),
           'HOST': os.getenv('DB_HOST'),
           'PORT': os.getenv('DB_PORT', '5432'),
       }
   }
   ```

3. Set environment variables in `.env`
4. Run migrations: `python manage.py migrate`

### Scheduled Backups

Add to crontab for daily backups at 2 AM:
```
0 2 * * * cd /path/to/backend && python manage.py automated_backup
```

### CORS Configuration

Edit `settings.py` CORS_ALLOWED_ORIGINS for your frontend domain:
```python
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'https://yourdomain.com',
]
```

## Authentication Flow

1. **Client sends credentials**
   ```
   POST /api/v1/auth/login/
   {
     "access_id": "KTS-MDA-001",
     "password": "securepassword"
   }
   ```

2. **Server returns tokens**
   ```json
   {
     "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
     "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
     "user": {
       "id": "uuid",
       "access_id": "KTS-MDA-001",
       "name": "John Doe",
       "role": "MDA_USER"
     }
   }
   ```

3. **Client uses access token for requests**
   ```
   Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
   ```

4. **When token expires, refresh**
   ```
   POST /api/v1/auth/token/refresh/
   {
     "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
   }
   ```

## Offline Sync Flow

1. **Client makes changes offline** (stored locally)
2. **Client reconnects** and calls bulk_sync
3. **Server processes actions atomically**
4. **For conflicts**:
   - Server detects version mismatch
   - Returns conflict details to client
   - Client shows modal with options
   - User chooses: Overwrite or Keep Server
5. **Server applies resolution** and sends back updated data
6. **Client syncs latest from server**

## Backup & Recovery

### Creating Backups

**Manual backup via API:**
```bash
curl -X POST http://localhost:8000/api/v1/backups/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Before system upgrade"
  }'
```

**Manual backup via Django command:**
```bash
python manage.py create_backup --description "Before system upgrade"
```

### Restoring from Backup

```bash
curl -X POST http://localhost:8000/api/v1/backups/<backup-id>/restore/ \
  -H "Authorization: Bearer <token>"
```

### Verifying Backup Integrity

```bash
curl http://localhost:8000/api/v1/backups/<backup-id>/verify/ \
  -H "Authorization: Bearer <token>"
```

## Admin Interface

Access at `http://localhost:8000/admin/` with superuser credentials.

Features:
- User management and password reset
- Report editing and version viewing
- Audit log browsing
- Backup management
- Conflict resolution

## Testing

Run tests:
```bash
python manage.py test
```

## Logging

Logs are written to:
- Console (development)
- `logs/django.log` (file, rotated at 10MB)

Adjust log level in `settings.py`:
```python
LOGGING['root']['level'] = 'DEBUG'  # More verbose
LOGGING['root']['level'] = 'WARNING'  # Less verbose
```

## Deployment

### Using Gunicorn

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4
```

### Using Docker

```dockerfile
FROM python:3.10
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
RUN python manage.py collectstatic --noinput
RUN python manage.py migrate
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
```

### Environment Variables for Production

```bash
DEBUG=False
SECRET_KEY=<very-secure-random-key>
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CORS_ALLOWED_ORIGINS=https://yourdomain.com
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

## API Documentation

Interactive API documentation available at:
- Swagger UI: `http://localhost:8000/api/docs/swagger/`
- ReDoc: `http://localhost:8000/api/docs/redoc/`

(Add `drf-spectacular` for full OpenAPI documentation)

## Security Best Practices

1. **Never commit `.env` files** with real secrets
2. **Use strong SECRET_KEY** in production (use `django-insecure-...` only in dev)
3. **Enable HTTPS** in production
4. **Use environment variables** for all sensitive config
5. **Regular backups** before deployments
6. **Monitor audit logs** for suspicious activity
7. **Update dependencies** regularly
8. **Use rate limiting** in production
9. **Configure CORS properly** for your domains
10. **Review logs** for errors and security issues

## Troubleshooting

### Migrations failed
```bash
python manage.py migrate --fake-initial
```

### Database locked (SQLite)
Close other database connections and try again.

### Port 8000 already in use
```bash
python manage.py runserver 8001
```

### Import errors
Ensure virtual environment is activated:
```bash
source venv/bin/activate
```

## Contributing

1. Create feature branch: `git checkout -b feature/your-feature`
2. Make changes and commit: `git commit -am 'Add your feature'`
3. Push branch: `git push origin feature/your-feature`
4. Create pull request

## Support

For issues, questions, or feature requests, contact the development team.

## License

Internal use only - MDA Report Portal Backend
# quarterly-report
# quarterly-report
# quarterly-report
# quarterly-report
