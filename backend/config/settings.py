"""Réglages de la plateforme Mathnexus.

Tout ce qui change entre le poste de développement et la production passe par des
variables d'environnement (voir .env.example). Aucun secret dans le dépôt.
"""
import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(nom, defaut=False):
    return os.environ.get(nom, str(defaut)).lower() in {"1", "true", "oui", "yes"}


def env_liste(nom, defaut=""):
    return [x.strip() for x in os.environ.get(nom, defaut).split(",") if x.strip()]


DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-uniquement-ne-jamais-utiliser-en-production"
    else:
        raise RuntimeError("DJANGO_SECRET_KEY doit être défini hors du mode DEBUG.")

ALLOWED_HOSTS = env_liste("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
# Sur Vercel, les adresses du déploiement sont connues par des variables du système.
ALLOWED_HOSTS += [h for h in (os.environ.get("VERCEL_URL"), os.environ.get("VERCEL_PROJECT_PRODUCTION_URL")) if h]
CSRF_TRUSTED_ORIGINS = env_liste("DJANGO_CSRF_TRUSTED_ORIGINS", "")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "comptes",
    "organisations",
    "contenus",
    "progression",
    "evaluations",
    "devoirs",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Base de données : PostgreSQL en production (DATABASE_URL), SQLite par défaut en développement.
# Sur un hébergement sans serveur (Vercel), chaque requête peut arriver sur une nouvelle
# instance : pas de connexion gardée ouverte, et pas de curseur côté serveur derrière un
# pooler en mode transaction (Neon, PgBouncer).
SANS_SERVEUR = env_bool("SANS_SERVEUR", bool(os.environ.get("VERCEL")))
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'dev.sqlite3'}",
        conn_max_age=0 if SANS_SERVEUR else 60,
        conn_health_checks=not SANS_SERVEUR,
    )
}
if env_bool("DB_POOLER", SANS_SERVEUR):
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True

# Cache : Redis s'il existe (REDIS_URL) ; sinon, en production, une table de la base, partagée
# par toutes les instances (indispensable pour que la limitation des tentatives de connexion
# tienne sur un hébergement sans serveur) ; mémoire locale en développement.
REDIS_URL = os.environ.get("REDIS_URL")
if REDIS_URL:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}}
elif not DEBUG:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "cache_django"}}
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

AUTH_USER_MODEL = "comptes.Utilisateur"

# Argon2id en premier : c'est lui qui hache les nouveaux mots de passe.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Dakar"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- API ---------------------------------------------------------------------
REST_FRAMEWORK = {
    # Sessions par cookie HttpOnly ; DRF impose le jeton CSRF aux requêtes authentifiées.
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["comptes.permissions.EstConnecteEtActif"],
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "connexion": os.environ.get("LIMITE_CONNEXION", "5/min"),
        "inscription": os.environ.get("LIMITE_INSCRIPTION", "10/hour"),
    },
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

# --- Sessions et cookies -----------------------------------------------------
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14  # 14 jours
CSRF_COOKIE_SAMESITE = "Lax"

# --- Durcissement en production ------------------------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"

# Nombre d'appareils connectés en même temps par compte (partage de comptes).
MAX_SESSIONS_PAR_COMPTE = int(os.environ.get("MAX_SESSIONS_PAR_COMPTE", "2"))

# Empreinte SHA-256 de la clé du moteur de parcours (jamais la clé elle-même).
# Générer : python3 -c "import secrets,hashlib; k=secrets.token_urlsafe(40); print(k); print(hashlib.sha256(k.encode()).hexdigest())"
CLE_DEPLOIEMENT_SHA256 = os.environ.get("CLE_DEPLOIEMENT_SHA256", "")

# Paquets de parcours : 25 Mo au plus (vérifié aussi par contenus.paquet).
DATA_UPLOAD_MAX_MEMORY_SIZE = 26 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 26 * 1024 * 1024
