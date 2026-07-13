"""
Django settings for core project.
"""
from pathlib import Path
import os
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Пути и переменные окружения
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

# ---------------------------------------------------------------------------
# Безопасность
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me-in-production')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

# ALLOWED_HOSTS и CSRF_TRUSTED_ORIGINS берутся из .env
# Локально: ALLOWED_HOSTS=localhost 127.0.0.1
# Railway:  ALLOWED_HOSTS=yourdomain.up.railway.app
_allowed = os.environ.get('ALLOWED_HOSTS', 'localhost 127.0.0.1')
ALLOWED_HOSTS = _allowed.split() if _allowed != '*' else ['*']

# CSRF — перечислите все домены через пробел
# Пример: https://yourdomain.up.railway.app https://xxxx.ngrok-free.dev
_csrf = os.environ.get('CSRF_TRUSTED_ORIGINS', 'http://localhost:8000')
CSRF_TRUSTED_ORIGINS = _csrf.split()

# ---------------------------------------------------------------------------
# Приложения
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    # django-unfold — должен быть ВЫШЕ django.contrib.admin
    'unfold',
    'unfold.contrib.import_export',
    'unfold.contrib.inlines',

    # Django core
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Сторонние
    'import_export',
    'channels',

    # Наши приложения
    'appbet',
    'bot',
    'manager',
]

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ---------------------------------------------------------------------------
# URLs и WSGI/ASGI
# ---------------------------------------------------------------------------
ROOT_URLCONF = 'core.urls'
WSGI_APPLICATION = 'core.wsgi.application'
ASGI_APPLICATION  = 'core.asgi.application'

# ---------------------------------------------------------------------------
# Шаблоны
# ---------------------------------------------------------------------------
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],   # глобальная папка шаблонов
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# База данных — PostgreSQL
# Поддерживает два формата:
#   1. DATABASE_URL=postgresql://user:pass@host:port/dbname  (Railway)
#   2. DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT       (локально / docker-compose)
# ---------------------------------------------------------------------------
_database_url = os.environ.get('DATABASE_URL')
if _database_url:
    # Railway-формат — разбираем URL вручную (без dj-database-url)
    from urllib.parse import urlparse
    _db = urlparse(_database_url)
    DATABASES = {
        'default': {
            'ENGINE':   'django.db.backends.postgresql',
            'NAME':     _db.path.lstrip('/'),
            'USER':     _db.username,
            'PASSWORD': _db.password,
            'HOST':     _db.hostname,
            'PORT':     _db.port or 5432,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE':   'django.db.backends.postgresql',
            'NAME':     os.environ.get('DB_NAME'),
            'USER':     os.environ.get('DB_USER'),
            'PASSWORD': os.environ.get('DB_PASSWORD'),
            'HOST':     os.environ.get('DB_HOST', 'localhost'),
            'PORT':     int(os.environ.get('DB_PORT', 5432)),
        }
    }

# ---------------------------------------------------------------------------
# Redis — кэш и channels
# Поддерживает два формата:
#   1. REDIS_URL=redis://host:port  (Railway)
#   2. REDIS_HOST, REDIS_PORT       (локально / docker-compose)
# ---------------------------------------------------------------------------
REDIS_URL = os.environ.get('REDIS_URL', '')
if not REDIS_URL:
    REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
    REDIS_URL  = f'redis://{REDIS_HOST}:{REDIS_PORT}'
else:
    from urllib.parse import urlparse as _urlparse
    _r = _urlparse(REDIS_URL)
    REDIS_HOST = _r.hostname
    REDIS_PORT = _r.port or 6379

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'{REDIS_URL}/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'appbet',
        'TIMEOUT': 300,  # 5 минут
    }
}

# Сессии через Redis (быстрее чем DB-сессии)
SESSION_ENGINE = os.environ.get('SESSION_ENGINE', 'django.contrib.sessions.backends.cache')
SESSION_CACHE_ALIAS = 'default'

# Django Channels — слой каналов через Redis
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [(REDIS_HOST, REDIS_PORT)],
        },
    },
}

# ---------------------------------------------------------------------------
# Пароли
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ---------------------------------------------------------------------------
# Интернационализация
# ---------------------------------------------------------------------------
LANGUAGE_CODE = 'ru'
TIME_ZONE = 'Europe/Kyiv'
USE_I18N      = True
USE_TZ        = True

# ---------------------------------------------------------------------------
# Статика и медиа
# ---------------------------------------------------------------------------
STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'   # для collectstatic в продакшене

MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'          # загруженные файлы клиентов

# ---------------------------------------------------------------------------
# Прочее
# ---------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# django-unfold
# ---------------------------------------------------------------------------
UNFOLD = {
    'SITE_TITLE':  'Юридические услуги – Админка',
    'SITE_HEADER': 'Юридическая платформа',

    # Плитки быстрого доступа на главной странице /admin/
    'DASHBOARD_CALLBACK': 'core.dashboard.dashboard_callback',

    # Навигация в сайдбаре
    'SIDEBAR': {
        'show_search': True,
        'show_all_applications': True,
        'navigation': [
            {
                'title': 'Менеджер',
                'icon': 'chat',
                'items': [
                    {
                        'title': 'Дашборд чата',
                        'icon': 'forum',
                        'link': '/manager/',
                    },
                ],
            },
            {
                'title': 'CRM',
                'icon': 'work',
                'items': [
                    {
                        'title': 'Контакты',
                        'icon': 'contacts',
                        'link': '/admin/bot/contact/',
                    },
                    {
                        'title': 'Заявки',
                        'icon': 'assignment',
                        'link': '/admin/bot/lead/',
                    },
                    {
                        'title': 'Сообщения',
                        'icon': 'message',
                        'link': '/admin/bot/chatmessage/',
                    },
                    {
                        'title': 'Документы клиентов',
                        'icon': 'folder',
                        'link': '/admin/bot/clientdocument/',
                    },
                ],
            },
            {
                'title': 'Каталог',
                'icon': 'category',
                'items': [
                    {
                        'title': 'Категории',
                        'icon': 'list',
                        'link': '/admin/bot/category/',
                    },
                    {
                        'title': 'Услуги',
                        'icon': 'inventory',
                        'link': '/admin/bot/product/',
                    },
                    {
                        'title': 'Шаблоны документов',
                        'icon': 'description',
                        'link': '/admin/bot/documenttemplate/',
                    },
                ],
            },
            {
                'title': 'Система',
                'icon': 'settings',
                'items': [
                    {
                        'title': 'Пользователи',
                        'icon': 'person',
                        'link': '/admin/auth/user/',
                    },
                    {
                        'title': 'Состояния диалогов',
                        'icon': 'psychology',
                        'link': '/admin/bot/userstate/',
                    },
                ],
            },
        ],
    },
}

# ---------------------------------------------------------------------------
# Telegram Bot
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN      = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_WEBHOOK_URL    = os.environ.get('TELEGRAM_WEBHOOK_URL', '')
