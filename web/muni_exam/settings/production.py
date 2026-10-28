import os

from .basic import *  # pylint: disable=wildcard-import,unused-wildcard-import

DEBUG = False

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("ALLOWED_HOSTS", "muni-exam.brno.pavelstudenik.cz").split(",")
    if host.strip()
]
# Site is served over HTTPS (Apache terminates TLS); Origin is https://…
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "CSRF_TRUSTED_ORIGINS",
        "https://muni-exam.brno.pavelstudenik.cz,http://muni-exam.brno.pavelstudenik.cz",
    ).split(",")
    if origin.strip()
]

SECRET_KEY = os.environ.get("SECRET_KEY", SECRET_KEY)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("SQLITE_PATH", "/app/data/db.sqlite3"),
    }
}

# Apache SSL vhost sets X-Forwarded-Proto (see 8010-muni-exam-le-ssl.conf)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
