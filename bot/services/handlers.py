# bot/services/handlers.py
"""
Обработчики апдейтов Telegram.
Все функции синхронные — вызываются напрямую из views_webhook.py.

Навигация по каталогу — гибридный подход:
  - Главное меню: ReplyKeyboard (всегда видна внизу)
  - Каталог категорий/услуг: InlineKeyboard + editMessageText (одно сообщение)
  - Сбор данных заявки: отдельные сообщения (допустимо, единичная цепочка)
"""
import logging
from django.core.files.base import ContentFile

from bot.models import Contact, UserState, Category, Product, ClientDocument, ChatMessage
from bot.services.telegram_api import (
    send_message, answer_callback_query, download_file,
    edit_message_text, delete_message,
    inline_keyboard, reply_keyboard,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Шаги диалога
# ---------------------------------------------------------------------------
STEP_START            = 'start'
STEP_MAIN_MENU        = 'main_menu'
STEP_SELECT_CATEGORY  = 'select_category'
STEP_SELECT_PRODUCT   = 'select_product'
STEP_WAITING_FULLNAME = 'waiting_fullname'
STEP_WAITING_PHONE    = 'waiting_phone'
STEP_WAITING_EMAIL    = 'waiting_email'
STEP_CHAT_MANAGER     = 'chat_manager'
STEP_WAITING_DOCUMENT = 'waiting_document'

# Ключ в state.data для хранения message_id сообщения каталога
CATALOG_MSG_KEY = 'catalog_message_id'


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _get_or_create_contact(message: dict) -> Contact:
    from_user = message.get('from', {})
    chat      = message.get('chat', {})
    chat_id   = str(chat.get('id') or from_user.get('id'))
    contact, _ = Contact.objects.get_or_create(
        telegram_chat_id=chat_id,
        defaults={
            'telegram_username':   from_user.get('username', ''),
            'telegram_first_name': from_user.get('first_name', ''),
        },
    )
    return contact


def _get_or_create_state(chat_id: str) -> UserState:
    state, _ = UserState.objects.get_or_create(
        telegram_chat_id=chat_id,
        defaults={'step': STEP_START},
    )
    return state


def _chat_id_from_message(message: dict) -> str:
    chat = message.get('chat', {})
    from_user = message.get('from', {})
    return str(chat.get('id') or from_user.get('id'))


# ---------------------------------------------------------------------------
# Reply-меню (главное)
# ---------------------------------------------------------------------------

def _send_main_menu(chat_id: str) -> None:
    send_message(
        chat_id,
        'Добро пожаловать! Выберите действие:',
        reply_markup=reply_keyboard([
            ['Категории', 'Контакты'],
            ['Задать вопрос', 'Отправить документы'],
        ]),
    )


# ---------------------------------------------------------------------------
# Каталог: сборка Inline-клавиатур
# ---------------------------------------------------------------------------

def _build_categories_keyboard() -> tuple[str, dict]:
    """Возвращает (текст, inline_keyboard) для списка категорий."""
    cats = list(Category.objects.filter(is_active=True).order_by('order', 'name'))
    if not cats:
        return 'Категорий пока нет.', inline_keyboard([[('◀️ Назад в меню', 'back_to_main')]])
    rows = [[(c.name, f'cat_{c.id}')] for c in cats]
    rows.append([('◀️ Назад в меню', 'back_to_main')])
    return 'Выберите категорию:', inline_keyboard(rows)


def _build_products_keyboard(category_id: int) -> tuple[str, dict]:
    """Возвращает (текст, inline_keyboard) для списка продуктов категории."""
    try:
        cat = Category.objects.get(id=category_id)
        cat_name = cat.name
    except Category.DoesNotExist:
        cat_name = '?'

    prods = list(
        Product.objects.filter(category_id=category_id, is_available=True).order_by('order', 'name')
    )
    if not prods:
        text = f'В категории «{cat_name}» пока нет услуг.'
        kb = inline_keyboard([
            [('◀️ Назад к категориям', 'back_to_categories')],
            [('◀️ Назад в меню',       'back_to_main')],
        ])
        return text, kb

    rows = []
    for p in prods:
        label = p.name + (f' — {p.price} грн.' if p.price else '')
        rows.append([(label, f'prod_{p.id}')])
    rows.append([
        ('◀️ Назад к категориям', 'back_to_categories'),
        ('◀️ Назад в меню',       'back_to_main'),
    ])
    return f'Выберите услугу в категории «{cat_name}»:', inline_keyboard(rows)


# ---------------------------------------------------------------------------
# Точка входа: текстовые сообщения и файлы
# ---------------------------------------------------------------------------

def handle_message(message: dict) -> None:
    chat_id = _chat_id_from_message(message)
    contact = _get_or_create_contact(message)
    state   = _get_or_create_state(chat_id)

    # Файлы — отдельная ветка
    if 'document' in message or 'photo' in message:
        _handle_file(message, chat_id, contact, state)
        return

    text = (message.get('text') or '').strip()

    # /start — сброс, удаляем сообщение каталога если висит
    if text == '/start':
        _cleanup_catalog_message(chat_id, state)
        state.step = STEP_MAIN_MENU
        state.data = {}
        state.save()
        _send_main_menu(chat_id)
        return

    step = state.step

    # --- Сбор данных заявки ---
    if step == STEP_WAITING_FULLNAME:
        state.data['full_name'] = text
        state.step = STEP_WAITING_PHONE
        state.save()
        send_message(chat_id, 'Введите ваш номер телефона:')
        return

    if step == STEP_WAITING_PHONE:
        state.data['phone'] = text
        state.step = STEP_WAITING_EMAIL
        state.save()
        send_message(chat_id, 'Введите ваш email:')
        return

    if step == STEP_WAITING_EMAIL:
        state.data['email'] = text
        _finish_request(chat_id, contact, state)
        return

    # --- Чат с менеджером ---
    if step == STEP_CHAT_MANAGER:
        if text == '← Главное меню':
            state.step = STEP_MAIN_MENU
            state.save()
            _send_main_menu(chat_id)
            return
        msg = ChatMessage.objects.create(contact=contact, text=text, direction='in')
        try:
            from manager.consumer import push_to_group
            push_to_group(contact.id, msg.id, text, 'in', msg.timestamp.strftime('%H:%M'))
        except Exception:
            pass
        send_message(
            chat_id,
            'Сообщение передано юристу. Ожидайте ответа.',
            reply_markup=reply_keyboard([['← Главное меню']]),
        )
        return

    # --- Ожидание документа ---
    if step == STEP_WAITING_DOCUMENT:
        send_message(chat_id, 'Пожалуйста, пришлите файл или фото документа.')
        return

    # --- Кнопки главного Reply-меню ---
    if text == 'Категории':
        state.step = STEP_SELECT_CATEGORY
        state.save()
        # Отправляем НОВОЕ сообщение каталога, сохраняем его message_id
        cat_text, cat_kb = _build_categories_keyboard()
        result = send_message(chat_id, cat_text, reply_markup=cat_kb)
        if result and result.get('ok'):
            state.data[CATALOG_MSG_KEY] = result['result']['message_id']
            state.save()

    elif text == 'Контакты':
        send_message(chat_id, '📞 +38 (0XX) XXX-XX-XX\n📧 info@example.ua')

    elif text == 'Задать вопрос':
        state.step = STEP_CHAT_MANAGER
        state.save()
        send_message(
            chat_id,
            'Опишите ваш вопрос — юрист ответит в ближайшее время.',
            reply_markup=reply_keyboard([['← Главное меню']]),
        )

    elif text == 'Отправить документы':
        state.step = STEP_WAITING_DOCUMENT
        state.save()
        send_message(
            chat_id,
            'Пришлите фото или скан документа.',
            reply_markup=reply_keyboard([['← Главное меню']]),
        )

    else:
        _send_main_menu(chat_id)
        state.step = STEP_MAIN_MENU
        state.save()


# ---------------------------------------------------------------------------
# Точка входа: callback_query (инлайн-кнопки каталога)
# ---------------------------------------------------------------------------

def handle_callback(callback_query: dict) -> None:
    query_id  = callback_query['id']
    from_user = callback_query['from']
    chat_id   = str(from_user['id'])
    data      = callback_query.get('data', '')
    # message_id сообщения с которого пришёл callback
    cb_message_id = callback_query.get('message', {}).get('message_id')

    answer_callback_query(query_id)

    state = _get_or_create_state(chat_id)

    # Синхронизируем catalog_message_id если его нет в state.data
    if cb_message_id and not state.data.get(CATALOG_MSG_KEY):
        state.data[CATALOG_MSG_KEY] = cb_message_id

    catalog_msg_id = state.data.get(CATALOG_MSG_KEY)

    # --- Выбор категории ---
    if data.startswith('cat_'):
        category_id = int(data.split('_')[1])
        state.data['category_id'] = category_id
        state.step = STEP_SELECT_PRODUCT
        state.save()
        prod_text, prod_kb = _build_products_keyboard(category_id)
        if catalog_msg_id:
            edit_message_text(chat_id, catalog_msg_id, prod_text, reply_markup=prod_kb)
        else:
            result = send_message(chat_id, prod_text, reply_markup=prod_kb)
            if result and result.get('ok'):
                state.data[CATALOG_MSG_KEY] = result['result']['message_id']
                state.save()

    # --- Выбор продукта ---
    elif data.startswith('prod_'):
        product_id = int(data.split('_')[1])
        state.data['product_id'] = product_id
        state.step = STEP_WAITING_FULLNAME
        state.save()

        try:
            prod = Product.objects.get(id=product_id)
            prod_name = prod.name
        except Product.DoesNotExist:
            prod_name = '?'

        # Редактируем сообщение каталога — убираем кнопки
        if catalog_msg_id:
            edit_message_text(
                chat_id, catalog_msg_id,
                f'✅ Вы выбрали «{prod_name}».\nПереходим к оформлению заявки.',
            )

        # Новое сообщение — начало диалога
        send_message(chat_id, 'Введите ваше полное ФИО:')

    # --- Назад к категориям ---
    elif data == 'back_to_categories':
        state.step = STEP_SELECT_CATEGORY
        state.data.pop('category_id', None)
        state.save()
        cat_text, cat_kb = _build_categories_keyboard()
        if catalog_msg_id:
            edit_message_text(chat_id, catalog_msg_id, cat_text, reply_markup=cat_kb)
        else:
            result = send_message(chat_id, cat_text, reply_markup=cat_kb)
            if result and result.get('ok'):
                state.data[CATALOG_MSG_KEY] = result['result']['message_id']
                state.save()

    # --- Назад в главное меню ---
    elif data == 'back_to_main':
        _cleanup_catalog_message(chat_id, state)
        state.step = STEP_MAIN_MENU
        state.data = {}
        state.save()
        # Reply-меню уже активно, просто подтверждаем возврат
        send_message(chat_id, 'Главное меню:',
                     reply_markup=reply_keyboard([
                         ['Категории', 'Контакты'],
                         ['Задать вопрос', 'Отправить документы'],
                     ]))


# ---------------------------------------------------------------------------
# Удаление сообщения каталога
# ---------------------------------------------------------------------------

def _cleanup_catalog_message(chat_id: str, state: UserState) -> None:
    """Удаляет inline-сообщение каталога если оно есть."""
    msg_id = state.data.get(CATALOG_MSG_KEY)
    if msg_id:
        delete_message(chat_id, msg_id)
        state.data.pop(CATALOG_MSG_KEY, None)


# ---------------------------------------------------------------------------
# Завершение заявки
# ---------------------------------------------------------------------------

def _finish_request(chat_id: str, contact: Contact, state: UserState) -> None:
    from bot.models import Product as Prod, Lead

    full_name  = state.data.get('full_name', '')
    phone      = state.data.get('phone', '')
    email      = state.data.get('email', '')
    product_id = state.data.get('product_id')

    if full_name:
        parts = full_name.split()
        contact.last_name   = parts[0] if len(parts) > 0 else ''
        contact.first_name  = parts[1] if len(parts) > 1 else ''
        contact.middle_name = parts[2] if len(parts) > 2 else ''
    if phone:
        contact.phone = phone
    if email:
        contact.email = email
    contact.is_lead = True
    contact.save()

    product = None
    if product_id:
        try:
            product = Prod.objects.get(id=product_id)
            state.product = product
        except Prod.DoesNotExist:
            pass

    Lead.objects.create(
        contact=contact,
        product=product,
        full_name=full_name,
        phone=phone,
        email=email,
        status='new',
    )

    state.step = STEP_MAIN_MENU
    state.data = {}
    state.save()

    send_message(chat_id, '✅ Заявка принята! Менеджер свяжется с вами.')
    _send_main_menu(chat_id)


# ---------------------------------------------------------------------------
# Обработка входящих файлов
# ---------------------------------------------------------------------------

def _handle_file(message: dict, chat_id: str, contact: Contact, state: UserState) -> None:
    if state.step != STEP_WAITING_DOCUMENT:
        send_message(chat_id, 'Сейчас не ожидается получение файлов. Воспользуйтесь меню.')
        return

    if 'document' in message:
        doc_info  = message['document']
        file_id   = doc_info['file_id']
        file_name = doc_info.get('file_name', f'doc_{chat_id}_{message["message_id"]}.bin')
    else:
        photo     = message['photo'][-1]
        file_id   = photo['file_id']
        file_name = f'photo_{chat_id}_{message["message_id"]}.jpg'

    file_bytes = download_file(file_id)
    if not file_bytes:
        send_message(chat_id, '❌ Не удалось получить файл. Попробуйте ещё раз.')
        return

    doc = ClientDocument(
        contact=contact,
        filename=file_name,
        telegram_file_id=file_id,
        description=message.get('caption', ''),
    )
    doc.file.save(file_name, ContentFile(file_bytes), save=True)

    state.step = STEP_MAIN_MENU
    state.save()

    send_message(chat_id, '✅ Документ получен и сохранён.')
    _send_main_menu(chat_id)
