# config/settings.py

import os
from pathlib import Path
from datetime import timedelta
from decouple import config
import dj_database_url

# ========================
# Core Setup
# ========================

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)

if not SECRET_KEY:
    raise Exception("SECRET_KEY not set")

ALLOWED_HOSTS = [
    config('RENDER_EXTERNAL_HOSTNAME', default='localhost'),
]

# Render SSL fix
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ========================
# Applications
# ========================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'corsheaders',
    'rest_framework.authtoken',
    'rest_framework_simplejwt.token_blacklist',

    'api',
]

# ========================
# Middleware
# ========================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    
    # Whitenoise MUST be right after security
    'whitenoise.middleware.WhiteNoiseMiddleware',
    
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ========================
# Database
# ========================

DATABASES = {
    'default': dj_database_url.config(
        default='sqlite:///db.sqlite3',
        conn_max_age=600
    )
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

AUTH_USER_MODEL = 'api.User'

# ========================
# Internationalization
# ========================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Lagos'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ========================
# Rest Framework & Auth
# ========================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),

    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,

    'AUTH_HEADER_TYPES': ('Bearer',),
    'SIGNING_KEY': SECRET_KEY,
}

# ========================
# CORS
# ========================

CORS_ALLOW_ALL_ORIGINS = True

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    'https://mda-backend-3exm.onrender.com',
]

CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    "https://*.onrender.com",
]

# ========================
# Security Headers
# ========================

SECURE_SSL_REDIRECT = not DEBUG

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# ========================
# Logging
# ========================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# ========================
# Python 3.14 Compatibility Patch
# ========================

import copy
from django.template.context import Context, RenderContext

def fixed_context_copy(self):
    duplicate = Context()
    duplicate.__class__ = self.__class__
    duplicate.__dict__ = copy.copy(self.__dict__)
    duplicate.dicts = self.dicts[:]
    return duplicate

Context.__copy__ = fixed_context_copy

def fixed_render_context_copy(self):
    duplicate = RenderContext()
    duplicate.__class__ = self.__class__
    duplicate.__dict__ = copy.copy(self.__dict__)
    duplicate.dicts = self.dicts[:]
    return duplicate

RenderContext.__copy__ = fixed_render_context_copy
