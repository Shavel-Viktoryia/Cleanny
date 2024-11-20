# myproject/__init__.py

from __future__ import absolute_import, unicode_literals

# Это позволяет Celery запуститься при старте Django
from .celery import app as celery_app

__all__ = ('celery_app',)
