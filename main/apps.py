from django.apps import AppConfig


class MainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'main'

class MyAppConfig(AppConfig):
    name = 'main'

    def ready(self):
        import signals  # Импортируйте сигнал
