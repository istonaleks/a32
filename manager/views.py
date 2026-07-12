# manager/views.py
import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, get_object_or_404

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from bot.models import Contact, ChatMessage

logger = logging.getLogger(__name__)


@staff_member_required
def dashboard(request):
    contacts = (
        Contact.objects
        .prefetch_related('messages', 'leads')
        .order_by('-updated_at')
    )
    for c in contacts:
        c.unread   = c.messages.filter(direction='in').exists()
        c.last_msg = c.messages.order_by('-timestamp').first()
    return render(request, 'manager/dashboard.html', {'contacts': contacts})


@staff_member_required
def chat(request, contact_id):
    contact  = get_object_or_404(Contact, pk=contact_id)
    messages = contact.messages.order_by('timestamp')
    leads    = contact.leads.order_by('-created_at')
    docs     = contact.documents.order_by('-uploaded_at')
    return render(request, 'manager/chat.html', {
        'contact':  contact,
        'messages': messages,
        'leads':    leads,
        'docs':     docs,
    })


@staff_member_required
@require_GET
def unread_count(request):
    """Возвращает количество непрочитанных сообщений от клиентов."""
    count = ChatMessage.objects.filter(direction='in').count()
    return JsonResponse({'count': count})
