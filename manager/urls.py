# manager/urls.py
from django.urls import path
from . import views

app_name = 'manager'

urlpatterns = [
    path('',                       views.dashboard,   name='dashboard'),
    path('chat/<int:contact_id>/', views.chat,        name='chat'),
    path('api/unread-count/',      views.unread_count, name='unread_count'),
]
