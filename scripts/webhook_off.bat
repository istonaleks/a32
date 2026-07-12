@echo off
:: webhook_off.bat — удаляет вебхук из Telegram (возврат к polling)
:: Запускать из корневой папки проекта (где manage.py)

echo [Webhook] Отключение вебхука...
echo.

:: Активируем виртуальное окружение
call .venv\Scripts\activate.bat

:: Удаляем вебхук
python manage.py set_webhook --delete

echo.
echo [Webhook] Текущее состояние:
python manage.py set_webhook --info

echo.
pause
