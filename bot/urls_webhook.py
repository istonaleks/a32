# bot/urls_webhook.py
from django.urls import path
from bot.views_webhook import telegram_webhook

urlpatterns = [
    path('', telegram_webhook, name='telegram_webhook'),
]
