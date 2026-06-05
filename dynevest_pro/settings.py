"""
Django settings for dynevest_pro project.
"""

from pathlib import Path
import os
import dj_database_url
from dotenv import load_dotenv

# Load the .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-g56m*g=j@5eyur#(=i)+j03%s)0nb58lnrrg#3-sia+x419c*f'

# SECURITY WARNING: changed to True for local debugging to fix 500 errors!
DEBUG = True  

ALLOWED_HOSTS = ['dynevest.onrender.com', 'localhost', '127.0.0.1', '*']

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.ComplianceLockMiddleware',
]

ROOT_URLCONF = 'dynevest_pro.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'dynevest_pro.wsgi.application'

# Database configuration for Render (PostgreSQL)
DATABASES = {
    'default': dj_database_url.config(
        default='sqlite:///db.sqlite3',
        conn_max_age=600
    )
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'

# FIXED: Removed the extra underscore so Django recognizes your static folder path asset array!
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

# This tells Django where to compile assets for production
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Redirects
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

# Security: Required for Render HTTPS
CSRF_TRUSTED_ORIGINS = ['https://dynevest.onrender.com']


# --- AUTOMATED ADMIN CREATION & RECOVERY ---
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.contrib.auth import get_user_model

@receiver(post_migrate)
def create_admin_account(sender, **kwargs):
    User = get_user_model()
    try:
        username = 'batman'
        password = 'Password2026!'
        email = 'samuelsuperguy@gmail.com'

        user, created = User.objects.get_or_create(username=username)
        
        user.set_password(password)
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.save()

        if created:
            print(f"✅ SUCCESS: {username} created as Live Admin.")
        else:
            print(f"✅ SUCCESS: {username} credentials verified/reset.")
            
    except Exception as e:
        print(f"⚠️ Admin creation skipped: {e}")

# Tell Django where your custom login route is located
LOGIN_URL = 'login'