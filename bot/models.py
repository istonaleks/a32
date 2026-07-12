from django.db import models


# ---------------------------------------------------------------------------
# Категория услуг
# ---------------------------------------------------------------------------

class Category(models.Model):
    name = models.CharField('Название', max_length=255)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='children',
        verbose_name='Родительская категория',
    )
    order = models.PositiveSmallIntegerField('Порядок', default=0)
    is_active = models.BooleanField('Активна', default=True)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Услуга
# ---------------------------------------------------------------------------

class Product(models.Model):
    name = models.CharField('Название', max_length=255)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='products',
        verbose_name='Категория',
    )
    description = models.TextField('Описание', blank=True)
    price = models.CharField(
        'Цена (грн.)',
        max_length=100,
        blank=True,
        help_text='Примеры: 1500, от 1000, договорная',
    )
    order = models.PositiveSmallIntegerField('Порядок', default=0)
    is_available = models.BooleanField('Доступна', default=True)

    class Meta:
        verbose_name = 'Услуга'
        verbose_name_plural = 'Услуги'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Контакт (физическое или юридическое лицо)
# ---------------------------------------------------------------------------

class Contact(models.Model):

    class ClientType(models.TextChoices):
        INDIVIDUAL   = 'individual',   'Физическое лицо'
        LEGAL_ENTITY = 'legal_entity', 'Юридическое лицо'

    # --- Тип клиента ---
    client_type = models.CharField(
        'Тип клиента',
        max_length=20,
        choices=ClientType.choices,
        default=ClientType.INDIVIDUAL,
    )

    # --- Telegram ---
    telegram_chat_id = models.CharField(
        'Telegram chat_id',
        max_length=64,
        unique=True,
        db_index=True,
    )
    telegram_username = models.CharField('Username', max_length=128, blank=True)
    telegram_first_name = models.CharField('Имя в Telegram', max_length=128, blank=True)

    # --- Общие поля ---
    phone = models.CharField('Телефон', max_length=32, blank=True)
    email = models.EmailField('Email', blank=True)
    registration_address = models.TextField('Адрес регистрации / юридический адрес', blank=True)

    # ----------------------------------------------------------------
    # Поля физического лица
    # ----------------------------------------------------------------
    last_name   = models.CharField('Фамилия',  max_length=128, blank=True)
    first_name  = models.CharField('Имя',      max_length=128, blank=True)
    middle_name = models.CharField('Отчество', max_length=128, blank=True)

    # Паспортные данные
    passport_series          = models.CharField('Серия паспорта',    max_length=10,  blank=True)
    passport_number          = models.CharField('Номер паспорта',    max_length=20,  blank=True)
    passport_issued_by       = models.CharField('Кем выдан',         max_length=512, blank=True)
    passport_issue_date      = models.DateField ('Дата выдачи',       null=True, blank=True)
    passport_department_code = models.CharField('Код подразделения', max_length=20,  blank=True)

    inn_individual = models.CharField('ИНН физлица (12 знаков)', max_length=12, blank=True)

    # ----------------------------------------------------------------
    # Поля юридического лица
    # ----------------------------------------------------------------
    company_name       = models.CharField('Полное наименование',  max_length=512, blank=True)
    company_short_name = models.CharField('Краткое наименование', max_length=255, blank=True)

    inn_legal            = models.CharField('ИНН (10 знаков)',  max_length=10, blank=True)
    kpp                  = models.CharField('КПП (9 знаков)',   max_length=9,  blank=True)
    ogrn                 = models.CharField('ОГРН (13 знаков)', max_length=13, blank=True)

    bank_name            = models.CharField('Банк',                   max_length=255, blank=True)
    bik                  = models.CharField('БИК',                    max_length=9,   blank=True)
    correspondent_account = models.CharField('Корреспондентский счёт', max_length=20,  blank=True)
    settlement_account   = models.CharField('Расчётный счёт',         max_length=20,  blank=True)

    director_name    = models.CharField(
        'ФИО руководителя (родительный падеж)',
        max_length=255,
        blank=True,
        help_text='Пример: Генерального директора Иванова И.И.',
    )
    acting_on_basis  = models.CharField(
        'Действует на основании',
        max_length=255,
        blank=True,
        help_text='Устав, Доверенность № … и т.п.',
    )

    # --- Служебные ---
    is_lead    = models.BooleanField('Лид', default=False)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Контакт'
        verbose_name_plural = 'Контакты'
        ordering = ['-created_at']

    def __str__(self):
        if self.client_type == self.ClientType.LEGAL_ENTITY:
            return self.company_short_name or self.company_name or f'Юрлицо #{self.pk}'
        full = ' '.join(filter(None, [self.last_name, self.first_name, self.middle_name]))
        return full or self.telegram_username or f'Контакт #{self.pk}'

    @property
    def display_name(self):
        """Короткое имя для отображения в чате."""
        return str(self)


# ---------------------------------------------------------------------------
# Состояние диалога
# ---------------------------------------------------------------------------

class UserState(models.Model):
    telegram_chat_id = models.CharField(
        'Telegram chat_id',
        max_length=64,
        unique=True,
        db_index=True,
    )
    step = models.CharField('Шаг диалога', max_length=64, default='start')
    product = models.ForeignKey(
        Product,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name='Выбранная услуга',
    )
    data = models.JSONField('Временные данные', default=dict, blank=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Состояние диалога'
        verbose_name_plural = 'Состояния диалогов'

    def __str__(self):
        return f'chat_id={self.telegram_chat_id} step={self.step}'


# ---------------------------------------------------------------------------
# Документ клиента (входящий файл от пользователя)
# ---------------------------------------------------------------------------

class ClientDocument(models.Model):
    contact          = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name='Контакт',
    )
    file             = models.FileField('Файл', upload_to='client_docs/%Y/%m/')
    filename         = models.CharField('Имя файла', max_length=255, blank=True)
    telegram_file_id = models.CharField('Telegram file_id', max_length=255, blank=True)
    description      = models.TextField('Описание / подпись', blank=True)
    uploaded_at      = models.DateTimeField('Загружен', auto_now_add=True)

    class Meta:
        verbose_name = 'Документ клиента'
        verbose_name_plural = 'Документы клиентов'
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.filename or f'Документ #{self.pk}'


# ---------------------------------------------------------------------------
# Шаблон юридического документа
# ---------------------------------------------------------------------------

class DocumentTemplate(models.Model):
    name          = models.CharField('Название шаблона', max_length=255)
    product       = models.ForeignKey(
        Product,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='templates',
        verbose_name='Услуга',
    )
    template_file = models.FileField(
        'Файл шаблона (.docx)',
        upload_to='templates/',
        help_text='Docx-файл с плейсхолдерами в формате {{ field_name }}',
    )
    description   = models.TextField('Описание', blank=True)
    created_at    = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'Шаблон документа'
        verbose_name_plural = 'Шаблоны документов'

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Сообщение чата
# ---------------------------------------------------------------------------

class ChatMessage(models.Model):

    class Direction(models.TextChoices):
        IN  = 'in',  'От клиента'
        OUT = 'out', 'От менеджера'

    contact   = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='Контакт',
    )
    direction = models.CharField(
        'Направление',
        max_length=3,
        choices=Direction.choices,
        default=Direction.IN,
    )
    text      = models.TextField('Текст')
    timestamp = models.DateTimeField('Время', auto_now_add=True)

    class Meta:
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'
        ordering = ['timestamp']

    def __str__(self):
        return f'[{self.get_direction_display()}] {self.contact} — {self.timestamp:%d.%m.%Y %H:%M}'


# ---------------------------------------------------------------------------
# Заявка (лид)
# ---------------------------------------------------------------------------

class Lead(models.Model):

    class Status(models.TextChoices):
        NEW        = 'new',        'Новая'
        IN_WORK    = 'in_work',    'В работе'
        DONE       = 'done',       'Завершена'
        CANCELLED  = 'cancelled',  'Отменена'

    contact  = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name='leads',
        verbose_name='Контакт',
    )
    product  = models.ForeignKey(
        Product,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name='Услуга',
    )
    status   = models.CharField(
        'Статус',
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
    )
    full_name = models.CharField('ФИО', max_length=255, blank=True)
    phone     = models.CharField('Телефон', max_length=32, blank=True)
    email     = models.EmailField('Email', blank=True)
    comment   = models.TextField('Комментарий', blank=True)
    created_at = models.DateTimeField('Создана', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)

    class Meta:
        verbose_name = 'Заявка'
        verbose_name_plural = 'Заявки'
        ordering = ['-created_at']

    def __str__(self):
        return f'Заявка #{self.pk} — {self.contact} [{self.get_status_display()}]'


# ---------------------------------------------------------------------------
# Сгенерированный документ (результат заполнения шаблона)
# ---------------------------------------------------------------------------

class GeneratedDocument(models.Model):
    contact   = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name='generated_documents',
        verbose_name='Контакт',
    )
    template  = models.ForeignKey(
        DocumentTemplate,
        on_delete=models.SET_NULL,
        null=True,
        related_name='generated_documents',
        verbose_name='Шаблон',
    )
    file      = models.FileField('Готовый документ', upload_to='generated/%Y/%m/')
    sent_to_client = models.BooleanField('Отправлен клиенту', default=False)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Сгенерировал',
    )

    class Meta:
        verbose_name = 'Сгенерированный документ'
        verbose_name_plural = 'Сгенерированные документы'
        ordering = ['-created_at']

    def __str__(self):
        tpl = self.template.name if self.template else '?'
        return f'{tpl} — {self.contact} ({self.created_at:%d.%m.%Y %H:%M})'
