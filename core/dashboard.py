# core/dashboard.py
"""
Callback для главной страницы django-unfold (/admin/).
Добавляет плитки быстрого доступа.
Подключается через settings.py: UNFOLD['DASHBOARD_CALLBACK'].
"""
from django.utils.translation import gettext_lazy as _


def dashboard_callback(request, context):
    context['shortcuts'] = [
        {
            'title': 'Дашборд чата',
            'description': 'Переписка с клиентами',
            'icon': 'forum',
            'link': '/manager/',
            'color': '#4f8ef7',
        },
        {
            'title': 'Контакты',
            'description': 'Все клиенты бота',
            'icon': 'contacts',
            'link': '/admin/bot/contact/',
            'color': '#4ff7a0',
        },
        {
            'title': 'Заявки',
            'description': 'Лиды и заявки',
            'icon': 'assignment',
            'link': '/admin/bot/lead/',
            'color': '#f7c04f',
        },
        {
            'title': 'Категории',
            'description': 'Каталог услуг',
            'icon': 'category',
            'link': '/admin/bot/category/',
            'color': '#a04ff7',
        },
        {
            'title': 'Шаблоны документов',
            'description': 'Docx-шаблоны для генерации',
            'icon': 'description',
            'link': '/admin/bot/documenttemplate/',
            'color': '#f75f4f',
        },
    ]
    return context
