# manager/routing.py
from django.urls import re_path
from manager import consumer

websocket_urlpatterns = [
    # ws://host/ws/chat/3/
    re_path(r'^ws/chat/(?P<contact_id>\d+)/$', consumer.ChatConsumer.as_asgi()),
]
