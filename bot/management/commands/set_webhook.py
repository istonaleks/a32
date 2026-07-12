# bot/management/commands/set_webhook.py
"""
python manage.py set_webhook                          # зарегистрировать
python manage.py set_webhook --delete                 # удалить
python manage.py set_webhook --url https://...        # явный URL
python manage.py set_webhook --info                   # текущее состояние
"""
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from bot.services.telegram_api import set_webhook, delete_webhook, get_webhook_info


class Command(BaseCommand):
    help = 'Управление вебхуком Telegram'

    def add_arguments(self, parser):
        parser.add_argument('--url',    type=str, default='', help='URL вебхука')
        parser.add_argument('--delete', action='store_true',  help='Удалить вебхук')
        parser.add_argument('--info',   action='store_true',  help='Показать текущий вебхук')

    def handle(self, *args, **options):
        if not settings.TELEGRAM_BOT_TOKEN:
            raise CommandError('TELEGRAM_BOT_TOKEN не задан.')

        if options['info']:
            info = get_webhook_info()
            self.stdout.write(str(info))
            return

        if options['delete']:
            result = delete_webhook()
            if result and result.get('ok'):
                self.stdout.write(self.style.SUCCESS('Вебхук удалён.'))
            else:
                raise CommandError(f'Ошибка: {result}')
            return

        url = options['url'] or getattr(settings, 'TELEGRAM_WEBHOOK_URL', '')
        if not url:
            raise CommandError('Укажите --url или задайте TELEGRAM_WEBHOOK_URL в .env')

        secret = getattr(settings, 'TELEGRAM_WEBHOOK_SECRET', '')
        result = set_webhook(url, secret=secret)

        if result and result.get('ok'):
            self.stdout.write(self.style.SUCCESS(f'Вебхук зарегистрирован: {url}'))
        else:
            raise CommandError(f'Ошибка: {result}')
