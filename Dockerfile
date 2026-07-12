# Dockerfile
FROM python:3.12-slim

# Системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Зависимости — отдельный слой (кэшируется)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем проект
COPY . .

# collectstatic и migrate вынесены в startCommand (railway.toml)
# чтобы не зависеть от БД во время сборки образа

EXPOSE 8000
