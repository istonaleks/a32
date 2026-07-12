# manager/consumer.py
"""
WebSocket consumer для чата менеджера.

Каждый контакт имеет свою группу: chat_<contact_id>.
Участники группы:
  - браузер менеджера (этот consumer)
  - bot/services/handlers.py (пушит входящие от клиента)

Сообщения в обе стороны имеют формат JSON:
  { "type": "chat_message", "id": 1, "text": "...", "direction": "in"|"out", "time": "14:05" }
"""
import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)


def _group_name(contact_id: int | str) -> str:
    return f'chat_{contact_id}'


class ChatConsumer(AsyncWebsocketConsumer):

    # ------------------------------------------------------------------ #
    # Подключение / отключение
    # ------------------------------------------------------------------ #

    async def connect(self):
        # Только авторизованные staff-пользователи
        if not self.scope['user'].is_authenticated or not self.scope['user'].is_staff:
            await self.close()
            return

        self.contact_id = self.scope['url_route']['kwargs']['contact_id']
        self.group = _group_name(self.contact_id)

        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        logger.debug('WS connect: %s group=%s', self.channel_name, self.group)

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group, self.channel_name)
        logger.debug('WS disconnect: %s', self.channel_name)

    # ------------------------------------------------------------------ #
    # Входящее от браузера → сохранить в БД → отправить в Telegram
    # ------------------------------------------------------------------ #

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data)
            text = data.get('text', '').strip()
        except (json.JSONDecodeError, AttributeError):
            return

        if not text:
            return

        msg, contact = await self._save_outgoing(self.contact_id, text)
        await self._send_telegram(contact, text)

        # Рассылаем всем в группе (включая себя)
        await self.channel_layer.group_send(
            self.group,
            {
                'type':      'chat_message',
                'id':        msg.id,
                'text':      text,
                'direction': 'out',
                'time':      msg.timestamp.strftime('%H:%M'),
            },
        )

    # ------------------------------------------------------------------ #
    # Обработчик группового события — отправляет данные в браузер
    # ------------------------------------------------------------------ #

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'id':        event['id'],
            'text':      event['text'],
            'direction': event['direction'],
            'time':      event['time'],
        }))

    # ------------------------------------------------------------------ #
    # Синхронные DB-операции (выполняются в thread pool)
    # ------------------------------------------------------------------ #

    @database_sync_to_async
    def _save_outgoing(self, contact_id, text):
        from bot.models import Contact, ChatMessage
        contact = Contact.objects.get(pk=contact_id)
        msg = ChatMessage.objects.create(contact=contact, text=text, direction='out')
        return msg, contact

    @database_sync_to_async
    def _send_telegram(self, contact, text):
        from bot.services.telegram_api import send_message as tg_send
        tg_send(chat_id=int(contact.telegram_chat_id), text=text)


# ------------------------------------------------------------------ #
# Хелпер для push из синхронного кода (handlers.py)
# ------------------------------------------------------------------ #

def push_to_group(contact_id: int, message_id: int, text: str, direction: str, time: str):
    """
    Вызывается из bot/services/handlers.py при получении сообщения от клиента.
    Синхронная обёртка над async channel_layer.group_send.
    """
    import asyncio
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    payload = {
        'type':      'chat_message',
        'id':        message_id,
        'text':      text,
        'direction': direction,
        'time':      time,
    }

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Уже в async-контексте (Channels worker)
            asyncio.ensure_future(
                channel_layer.group_send(_group_name(contact_id), payload)
            )
        else:
            loop.run_until_complete(
                channel_layer.group_send(_group_name(contact_id), payload)
            )
    except RuntimeError:
        # Нет event loop — создаём новый (Django runserver / WSGI)
        asyncio.run(channel_layer.group_send(_group_name(contact_id), payload))
