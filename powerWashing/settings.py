from pathlib import Path
from django.templatetags.static import static
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
import django_heroku
import dj_database_url
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-!)kk^js_66cyvlsn4dog9-4amy%il#u8l+wnju5ec9kdpy8v&^'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = ['*']

CSRF_TRUSTED_ORIGINS = [
    "https://lavandaria-production.up.railway.app",
    "https://laudrybox.up.railway.app",
    "https://lavandaria-production-temp.up.railway.app"
]

# Application definition
INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "unfold.contrib.inlines",
    "unfold.contrib.import_export",
    "unfold.contrib.simple_history",
    'django.contrib.admin',
    'django.contrib.humanize',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    "core.apps.CoreConfig",
    "crm.apps.CrmConfig",
    'import_export',
    "dashboard.apps.DashboardConfig",
    "artigos.apps.ArtigosConfig",
    "cliente.apps.ClienteConfig",
    "lavandarias.apps.LavandariasConfig",
    "funcionarios.apps.FuncionariosConfig",
    "user.apps.UserConfig",
    "pedidos.apps.PedidosConfig",
    "relatorios.apps.RelatoriosConfig"
]

# 🔥 MIDDLEWARE OTIMIZADO
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # 🔥 Adicionar para arquivos estáticos
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # 🔥 Cache middleware
    'django.middleware.cache.UpdateCacheMiddleware',
    'django.middleware.cache.FetchFromCacheMiddleware',
]

ROOT_URLCONF = 'powerWashing.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'powerWashing.wsgi.application'

# 🔥 DATABASE OTIMIZADO
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'railway',
        'USER': 'postgres',
        'PASSWORD': 'ivnCkqDIIZAOhpaRUQfvDryCvtjuMlir',
        'HOST': 'turntable.proxy.rlwy.net',
        'PORT': '55561',
        'OPTIONS': {
            'options': '-c statement_timeout=30s -c work_mem=16MB',
        },
        'CONN_MAX_AGE': 600,  # 🔥 Manter conexões abertas
        'CONN_HEALTH_CHECKS': True,
    }
}

# 🔥 CACHE PARA PRODUÇÃO
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'TIMEOUT': 300,  # 5 minutos
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
        },
    }
}

# 🔥 SESSÃO COM CACHE
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
SESSION_CACHE_ALIAS = 'default'

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

# Internationalization
LANGUAGE_CODE = 'pt-pt'  # 🔥 Mudado para português
TIME_ZONE = 'Africa/Maputo'
USE_I18N = True
USE_TZ = True

# 🔥 STATIC FILES OTIMIZADOS
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/images/service/'
MEDIA_ROOT = BASE_DIR / 'static/images/service'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# 🔥 LOGGING PARA PRODUÇÃO (opcional, ajuda a debugar)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'ERROR',  # Mudar para DEBUG para ver queries
            'propagate': False,
        },
    },
}

# 🔥 UNFOLD CONFIG
UNFOLD = {
    "SITE_TITLE": "LaundryBox",
    "SITE_URL": "/",
    "SITE_LOGO": {
        "light": lambda request: static("img/local/icon.png"),
        "dark": lambda request: static("img/local/icon.png"),
    },
    "SITE_FAVICONS": [
        {
            "rel": "icon",
            "sizes": "32x24",
            "type": "image/svg+xml",
            "href": lambda request: static("img/local/logo.jpg"),
        },
    ],
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "DASHBOARD_CALLBACK": "core.views.dashboard_callback",
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": [
            {
                "separator": False,
                "collapsible": False,
                "items": [
                    {
                        "title": _("Dashboard"),
                        "icon": "dashboard",
                        "link": reverse_lazy("admin:index"),
                    },
                ],
            },
            {
                "title": _("View applications"),
                "separator": False,
                "collapsible": False,
                "items": [
                    {
                        "title": _("Lavandaria"),
                        "icon": "store",
                        "link": reverse_lazy("admin:core_lavandaria_changelist"),
                        "permission": lambda request: request.user.has_perm("core.view_lavandaria"),
                    },
                    {
                        "title": _("Staff"),
                        "icon": "person",
                        "link": reverse_lazy("admin:core_funcionario_changelist"),
                        "permission": lambda request: request.user.has_perm("core.view_funcionario"),
                    },
                    {
                        "title": _("Artigos"),
                        "icon": "dry_cleaning",
                        "link": reverse_lazy("admin:core_itemservico_changelist"),
                        "permission": lambda request: request.user.has_perm("core.view_itemservico"),
                    },
                    {
                        "title": _("Clientes"),
                        "icon": "handshake",
                        "link": reverse_lazy("admin:core_cliente_changelist"),
                        "permission": lambda request: request.user.has_perm("core.view_cliente"),
                    },
                    {
                        "title": _("Pedidos"),
                        "icon": "shopping_cart",
                        "link": reverse_lazy("admin:core_pedido_changelist"),
                        "permission": lambda request: request.user.has_perm("core.view_pedido"),
                    },
                    {
                        "title": _("Recibos"),
                        "icon": "receipt_long",
                        "link": reverse_lazy("admin:core_recibo_changelist"),
                        "permission": lambda request: request.user.has_perm("core.view_recibo"),
                    },
                ]
            }
        ],
    },
}

# 🔥 Configuração para Railway
if 'DATABASE_URL' in os.environ:
    DATABASES['default'] = dj_database_url.config(conn_max_age=600, ssl_require=True)