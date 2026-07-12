# bot/views_webhook.py
"""
Эндпоинт /telegram/webhook/
Telegram шлёт POST при каждом апдейте.
"""
import json
import logging

from django.conf import settings
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from bot.services.handlers import handle_message, handle_callback

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def telegram_webhook(request):
    # Проверка секретного токена (если задан в .env)
    secret = getattr(settings, 'TELEGRAM_WEBHOOK_SECRET', '')
    if secret:
        incoming = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
        if incoming != secret:
            logger.warning('Webhook: неверный секретный токен')
            return HttpResponseForbidden('Forbidden')

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.error('Webhook: не удалось разобрать JSON')
        return JsonResponse({'error': 'invalid json'}, status=400)

    try:
        if 'message' in data:
            handle_message(data['message'])
        elif 'callback_query' in data:
            handle_callback(data['callback_query'])
        else:
            logger.debug('Webhook: неизвестный тип апдейта: %s', list(data.keys()))
    except Exception:
        # Всегда возвращаем 200 — иначе Telegram будет повторять апдейт
        logger.exception('Webhook: необработанная ошибка')

    return JsonResponse({'ok': True})
