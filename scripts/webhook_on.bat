@echo off
:: webhook_on.bat — регистрирует вебхук в Telegram
:: Запускать из корневой папки проекта (где manage.py)

echo [Webhook] Включение вебхука...
echo.

:: Активируем виртуальное окружение
call .venv\Scripts\activate.bat

:: Регистрируем вебхук (URL берётся из .env -> TELEGRAM_WEBHOOK_URL)
python manage.py set_webhook

echo.
echo [Webhook] Проверка текущего состояния:
python manage.py set_webhook --info

echo.
pause
