# bot/services/doc_generator.py
"""
Сервис генерации юридических документов из docx-шаблонов.

Логика:
  1. Берём DocumentTemplate (docx-файл с плейсхолдерами {{ field }})
  2. Собираем словарь контекста из полей Contact
  3. docxtpl подставляет значения, сохраняем результат в GeneratedDocument

Плейсхолдеры в шаблоне должны совпадать с ключами context-словаря,
см. CONTEXT_FIELD_LABELS ниже — это справочник доступных полей.
"""
import logging
import os
from datetime import date

from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from docxtpl import DocxTemplate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Справочник доступных плейсхолдеров (для подсказки в админке/интерфейсе)
# ---------------------------------------------------------------------------

CONTEXT_FIELD_LABELS = {
    # Общие
    'client_type':           'Тип клиента (individual / legal_entity)',
    'phone':                 'Телефон',
    'email':                 'Email',
    'registration_address':  'Адрес регистрации',
    'today':                 'Сегодняшняя дата (дд.мм.гггг)',

    # Физлицо
    'last_name':             'Фамилия',
    'first_name':            'Имя',
    'middle_name':           'Отчество',
    'full_name':             'ФИО полностью',
    'passport_series':       'Серия паспорта',
    'passport_number':       'Номер паспорта',
    'passport_issued_by':    'Кем выдан паспорт',
    'passport_issue_date':   'Дата выдачи паспорта',
    'passport_department_code': 'Код подразделения',
    'inn_individual':        'ИНН физлица',

    # Юрлицо
    'company_name':          'Полное наименование организации',
    'company_short_name':    'Краткое наименование',
    'inn_legal':              'ИНН организации',
    'kpp':                    'КПП',
    'ogrn':                   'ОГРН',
    'bank_name':               'Банк',
    'bik':                     'БИК',
    'correspondent_account':   'Корр. счёт',
    'settlement_account':      'Расчётный счёт',
    'director_name':           'ФИО руководителя (родительный падеж)',
    'acting_on_basis':         'Действует на основании',
}

# Поля которые желательно иметь заполненными для физлица / юрлица
REQUIRED_FIELDS_INDIVIDUAL = ['last_name', 'first_name', 'phone']
REQUIRED_FIELDS_LEGAL      = ['company_name', 'inn_legal', 'director_name']


class DocGenerationError(Exception):
    """Базовая ошибка генерации документа — содержит понятное сообщение для UI."""
    pass


# ---------------------------------------------------------------------------
# Сборка контекста из Contact
# ---------------------------------------------------------------------------

def build_context(contact) -> dict:
    """Собирает словарь плейсхолдеров из полей Contact."""
    full_name = ' '.join(filter(None, [
        contact.last_name, contact.first_name, contact.middle_name,
    ]))

    context = {
        'client_type':              contact.get_client_type_display(),
        'phone':                    contact.phone or '',
        'email':                    contact.email or '',
        'registration_address':     contact.registration_address or '',
        'today':                    date.today().strftime('%d.%m.%Y'),

        'last_name':                contact.last_name or '',
        'first_name':               contact.first_name or '',
        'middle_name':              contact.middle_name or '',
        'full_name':                full_name,
        'passport_series':          contact.passport_series or '',
        'passport_number':          contact.passport_number or '',
        'passport_issued_by':       contact.passport_issued_by or '',
        'passport_issue_date':      contact.passport_issue_date.strftime('%d.%m.%Y') if contact.passport_issue_date else '',
        'passport_department_code': contact.passport_department_code or '',
        'inn_individual':           contact.inn_individual or '',

        'company_name':             contact.company_name or '',
        'company_short_name':       contact.company_short_name or '',
        'inn_legal':                contact.inn_legal or '',
        'kpp':                      contact.kpp or '',
        'ogrn':                     contact.ogrn or '',
        'bank_name':                contact.bank_name or '',
        'bik':                      contact.bik or '',
        'correspondent_account':    contact.correspondent_account or '',
        'settlement_account':       contact.settlement_account or '',
        'director_name':            contact.director_name or '',
        'acting_on_basis':          contact.acting_on_basis or '',
    }
    return context


# ---------------------------------------------------------------------------
# Валидация — какие поля не заполнены
# ---------------------------------------------------------------------------

def check_missing_fields(contact) -> list[str]:
    """
    Возвращает список ЧЕЛОВЕКОЧИТАЕМЫХ названий незаполненных ключевых полей.
    Не блокирует генерацию — только предупреждает.
    """
    required = (
        REQUIRED_FIELDS_LEGAL
        if contact.client_type == contact.ClientType.LEGAL_ENTITY
        else REQUIRED_FIELDS_INDIVIDUAL
    )
    missing = []
    for field in required:
        value = getattr(contact, field, None)
        if not value:
            missing.append(CONTEXT_FIELD_LABELS.get(field, field))
    return missing


# ---------------------------------------------------------------------------
# Основная функция генерации
# ---------------------------------------------------------------------------

def generate_document(contact, template, user=None):
    """
    Заполняет docx-шаблон данными контакта.

    :param contact:  экземпляр bot.models.Contact
    :param template: экземпляр bot.models.DocumentTemplate
    :param user:     django.contrib.auth.User — кто инициировал генерацию (опционально)
    :return:         экземпляр bot.models.GeneratedDocument

    :raises DocGenerationError: если шаблон повреждён, неверного формата
                                 или произошла иная ошибка заполнения.
    """
    from bot.models import GeneratedDocument

    # --- Проверка формата файла ---
    template_path = template.template_file.path
    if not template_path.lower().endswith('.docx'):
        raise DocGenerationError(
            f'Шаблон «{template.name}» имеет неверный формат. '
            f'Допускается только .docx (не .doc, .odt и т.п.).'
        )

    if not os.path.exists(template_path):
        raise DocGenerationError(
            f'Файл шаблона «{template.name}» не найден на сервере. '
            f'Возможно, файл был удалён — загрузите шаблон повторно.'
        )

    # --- Сборка контекста ---
    context = build_context(contact)

    # --- Заполнение шаблона ---
    try:
        doc = DocxTemplate(template_path)
        doc.render(context)
    except Exception as e:
        logger.exception('Ошибка заполнения шаблона %s для contact=%s', template.name, contact.id)
        raise DocGenerationError(
            f'Не удалось заполнить шаблон «{template.name}». '
            f'Проверьте корректность плейсхолдеров в файле (формат {{{{ field_name }}}}). '
            f'Техническая причина: {e}'
        )

    # --- Сохранение результата ---
    safe_contact_name = str(contact).replace('/', '_').replace('\\', '_')[:50]
    output_filename = f'{template.name}_{safe_contact_name}.docx'.replace(' ', '_')

    from io import BytesIO
    buffer = BytesIO()
    try:
        doc.save(buffer)
    except Exception as e:
        logger.exception('Ошибка сохранения документа template=%s contact=%s', template.id, contact.id)
        raise DocGenerationError(f'Не удалось сохранить готовый документ: {e}')

    buffer.seek(0)

    generated = GeneratedDocument(
        contact=contact,
        template=template,
        created_by=user,
    )
    generated.file.save(output_filename, ContentFile(buffer.read()), save=True)

    logger.info('Документ сгенерирован: template=%s contact=%s file=%s',
                template.id, contact.id, output_filename)

    return generated
