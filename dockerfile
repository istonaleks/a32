# Dockerfile
# Django + Daphne/Gunicorn+Uvicorn контейнер

FROM python:3.12-slim

# Системные зависимости
# libpq-dev — для psycopg2-binary
# gcc       — компиляция некоторых пакетов
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Устанавливаем зависимости отдельным слоем (кэшируется если requirements.txt не менялся)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Собираем статику
RUN python manage.py collectstatic --noinput

# Порт
EXPOSE 8000

# Команда запуска — gunicorn с uvicorn workers (ASGI, поддерживает WebSocket)
# -w 2 — два воркера (Railway Free имеет ограничения по RAM, не ставьте больше 2-3)
# --bind 0.0.0.0:8000 — слушаем все интерфейсы
CMD ["gunicorn", "core.asgi:application", \
     "-w", "2", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
