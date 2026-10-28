"""WSGI entry point for muni-exam.

Exposes the WSGI callable as ``application``.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "muni_exam.settings")

application = get_wsgi_application()
