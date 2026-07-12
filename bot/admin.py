from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from unfold.admin import ModelAdmin, TabularInline

from django.contrib import messages as django_messages
from django.shortcuts import redirect
from django.urls import path

from .models import (
    Category, Product, Contact,
    UserState, ClientDocument, DocumentTemplate, ChatMessage, Lead,
    GeneratedDocument,
)
from .services.doc_generator import generate_document, check_missing_fields, DocGenerationError


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------

class ProductInline(TabularInline):
    model = Product
    extra = 0
    fields = ('name', 'price', 'order', 'is_available')
    show_change_link = True


class ClientDocumentInline(TabularInline):
    model = ClientDocument
    extra = 0
    fields = ('filename', 'file', 'description', 'uploaded_at')
    readonly_fields = ('uploaded_at',)


class ChatMessageInline(TabularInline):
    model = ChatMessage
    extra = 0
    fields = ('direction', 'text', 'timestamp')
    readonly_fields = ('direction', 'text', 'timestamp')
    ordering = ('timestamp',)

    def has_add_permission(self, request, obj=None):
        return False


class LeadInline(TabularInline):
    model = Lead
    extra = 0
    fields = ('product', 'status', 'full_name', 'phone', 'created_at')
    readonly_fields = ('created_at',)
    show_change_link = True


class GeneratedDocumentInline(TabularInline):
    model = GeneratedDocument
    extra = 0
    fields = ('template', 'file', 'sent_to_client', 'send_link', 'created_by', 'created_at')
    readonly_fields = ('created_by', 'created_at', 'send_link')

    def has_add_permission(self, request, obj=None):
        # Документы создаются только через action "Сгенерировать документ"
        return False

    @admin.display(description='Отправить')
    def send_link(self, obj):
        if not obj.pk:
            return '—'
        if obj.sent_to_client:
            return format_html('<span style="color:#4ff7a0;">✅ Отправлено</span>')
        url = reverse('admin:bot_generateddocument_send', args=[obj.pk])
        return format_html('<a class="button" href="{}">📤 Отправить клиенту</a>', url)


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------

@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display  = ('name', 'parent', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    list_filter   = ('is_active',)
    search_fields = ('name',)
    inlines       = [ProductInline]


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------

@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display  = ('name', 'category', 'price', 'order', 'is_available')
    list_editable = ('order', 'is_available')
    list_filter   = ('category', 'is_available')
    search_fields = ('name', 'description')


# ---------------------------------------------------------------------------
# Contact
# ---------------------------------------------------------------------------

@admin.register(Contact)
class ContactAdmin(ModelAdmin):
    list_display  = ('__str__', 'client_type', 'telegram_chat_id', 'phone', 'email', 'is_lead', 'created_at')
    list_filter   = ('client_type', 'is_lead')
    search_fields = ('telegram_chat_id', 'telegram_username', 'last_name', 'first_name', 'company_name', 'phone', 'email')
    readonly_fields = ('created_at', 'updated_at')
    inlines       = [LeadInline, GeneratedDocumentInline, ClientDocumentInline, ChatMessageInline]
    actions       = ['generate_document_action']

    fieldsets = (
        ('Telegram', {
            'fields': ('telegram_chat_id', 'telegram_username', 'telegram_first_name'),
        }),
        ('Тип клиента', {
            'fields': ('client_type',),
        }),
        ('Общие реквизиты', {
            'fields': ('phone', 'email', 'registration_address', 'is_lead'),
        }),
        ('Физическое лицо', {
            'classes': ('collapse',),
            'fields': (
                'last_name', 'first_name', 'middle_name',
                'passport_series', 'passport_number',
                'passport_issued_by', 'passport_issue_date',
                'passport_department_code', 'inn_individual',
            ),
        }),
        ('Юридическое лицо', {
            'classes': ('collapse',),
            'fields': (
                'company_name', 'company_short_name',
                'inn_legal', 'kpp', 'ogrn',
                'bank_name', 'bik', 'correspondent_account', 'settlement_account',
                'director_name', 'acting_on_basis',
            ),
        }),
        ('Служебное', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at'),
        }),
    )

    @admin.action(description='📄 Сгенерировать документ из шаблона')
    def generate_document_action(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request,
                'Выберите ровно одного контакта для генерации документа.',
                level=django_messages.WARNING,
            )
            return
        contact = queryset.first()
        return redirect(f'/admin/bot/contact/{contact.id}/generate-document/')

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<int:contact_id>/generate-document/',
                self.admin_site.admin_view(self.generate_document_view),
                name='bot_contact_generate_document',
            ),
        ]
        return custom + urls

    def generate_document_view(self, request, contact_id):
        from django.shortcuts import render, get_object_or_404

        contact = get_object_or_404(Contact, pk=contact_id)
        templates = DocumentTemplate.objects.all()
        missing_fields = check_missing_fields(contact)

        if request.method == 'POST':
            template_id = request.POST.get('template_id')
            template = get_object_or_404(DocumentTemplate, pk=template_id)
            try:
                generated = generate_document(contact, template, user=request.user)
                self.message_user(
                    request,
                    f'Документ «{generated.file.name.split("/")[-1]}» успешно сгенерирован.',
                    level=django_messages.SUCCESS,
                )
            except DocGenerationError as e:
                self.message_user(request, str(e), level=django_messages.ERROR)
            return redirect(f'/admin/bot/contact/{contact.id}/change/')

        context = {
            **self.admin_site.each_context(request),
            'contact': contact,
            'templates': templates,
            'missing_fields': missing_fields,
            'title': f'Генерация документа — {contact}',
            'opts': self.model._meta,
        }
        return render(request, 'admin/bot/generate_document.html', context)


# ---------------------------------------------------------------------------
# Lead
# ---------------------------------------------------------------------------

@admin.register(Lead)
class LeadAdmin(ModelAdmin):
    list_display   = ('id', 'contact_link', 'product', 'status', 'full_name', 'phone', 'created_at')
    list_filter    = ('status', 'product__category', 'created_at')
    list_editable  = ('status',)
    search_fields  = ('full_name', 'phone', 'email', 'contact__telegram_chat_id')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Заявка', {
            'fields': ('contact', 'product', 'status'),
        }),
        ('Данные клиента', {
            'fields': ('full_name', 'phone', 'email'),
        }),
        ('Комментарий', {
            'fields': ('comment',),
        }),
        ('Служебное', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at'),
        }),
    )

    @admin.display(description='Контакт')
    def contact_link(self, obj):
        url = reverse('admin:bot_contact_change', args=[obj.contact_id])
        return format_html('<a href="{}">{}</a>', url, obj.contact)


# ---------------------------------------------------------------------------
# UserState
# ---------------------------------------------------------------------------

@admin.register(UserState)
class UserStateAdmin(ModelAdmin):
    list_display  = ('telegram_chat_id', 'step', 'product', 'updated_at')
    list_filter   = ('step',)
    search_fields = ('telegram_chat_id',)
    readonly_fields = ('updated_at',)


# ---------------------------------------------------------------------------
# ClientDocument
# ---------------------------------------------------------------------------

@admin.register(ClientDocument)
class ClientDocumentAdmin(ModelAdmin):
    list_display  = ('filename', 'contact', 'description', 'uploaded_at')
    list_filter   = ('uploaded_at',)
    search_fields = ('filename', 'contact__telegram_chat_id', 'contact__last_name')
    readonly_fields = ('uploaded_at',)


# ---------------------------------------------------------------------------
# DocumentTemplate
# ---------------------------------------------------------------------------

@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(ModelAdmin):
    list_display  = ('name', 'product', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at',)


# ---------------------------------------------------------------------------
# GeneratedDocument
# ---------------------------------------------------------------------------

@admin.register(GeneratedDocument)
class GeneratedDocumentAdmin(ModelAdmin):
    list_display  = ('__str__', 'contact', 'template', 'sent_to_client', 'created_by', 'created_at')
    list_filter   = ('sent_to_client', 'template', 'created_at')
    search_fields = ('contact__telegram_chat_id', 'contact__last_name', 'contact__company_name')
    readonly_fields = ('created_at', 'created_by')
    actions       = ['send_to_client_action']

    @admin.action(description='📤 Отправить клиенту в Telegram')
    def send_to_client_action(self, request, queryset):
        from .services.telegram_api import send_document

        sent, failed = 0, 0
        for doc in queryset.select_related('contact'):
            result = send_document(
                chat_id=int(doc.contact.telegram_chat_id),
                file_path=doc.file.path,
                caption=f'Документ: {doc.template.name if doc.template else "—"}',
            )
            if result and result.get('ok'):
                doc.sent_to_client = True
                doc.save(update_fields=['sent_to_client'])
                sent += 1
            else:
                failed += 1

        if sent:
            self.message_user(
                request, f'Отправлено клиентам: {sent}.',
                level=django_messages.SUCCESS,
            )
        if failed:
            self.message_user(
                request,
                f'Не удалось отправить: {failed}. Проверьте chat_id контакта и доступность Telegram API.',
                level=django_messages.ERROR,
            )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<int:doc_id>/send/',
                self.admin_site.admin_view(self.send_one_view),
                name='bot_generateddocument_send',
            ),
        ]
        return custom + urls

    def send_one_view(self, request, doc_id):
        from django.shortcuts import get_object_or_404
        from .services.telegram_api import send_document

        doc = get_object_or_404(GeneratedDocument, pk=doc_id)
        result = send_document(
            chat_id=int(doc.contact.telegram_chat_id),
            file_path=doc.file.path,
            caption=f'Документ: {doc.template.name if doc.template else "—"}',
        )
        if result and result.get('ok'):
            doc.sent_to_client = True
            doc.save(update_fields=['sent_to_client'])
            self.message_user(request, 'Документ отправлен клиенту в Telegram.', level=django_messages.SUCCESS)
        else:
            self.message_user(
                request,
                'Не удалось отправить документ. Проверьте chat_id контакта.',
                level=django_messages.ERROR,
            )
        return redirect(f'/admin/bot/contact/{doc.contact_id}/change/')


# ---------------------------------------------------------------------------
# ChatMessage
# ---------------------------------------------------------------------------

@admin.register(ChatMessage)
class ChatMessageAdmin(ModelAdmin):
    list_display  = ('contact', 'direction', 'short_text', 'timestamp')
    list_filter   = ('direction', 'timestamp')
    search_fields = ('contact__telegram_chat_id', 'contact__last_name', 'text')
    readonly_fields = ('timestamp',)

    @admin.display(description='Текст')
    def short_text(self, obj):
        return obj.text[:80] + '…' if len(obj.text) > 80 else obj.text
