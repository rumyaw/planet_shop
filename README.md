# Дипломный проект интернет-магазин «Планета» 

## Технологии

- **Backend**: Python + Flask
- **ORM/БД**: Flask‑SQLAlchemy + SQLite (`instance/planeta_shop.db`)
- **Аутентификация**: Flask‑Login
- **UI**: Jinja2 + Bootstrap 5 (локально, без CDN), шрифт **Inter** и иконки Bootstrap Icons — локальные
- **Изображения**: загрузка файлов товаров в `static/uploads/products/` (Pillow)
- **PDF**: стилизованные чеки и отчёты на **reportlab** (`pdf_utils.py`)

## Требования

- Python 3.10+
- pip

## Установка и запуск

```bash
pip install -r requirements.txt
python app.py
```
Приложение будет доступно по адресу `http://localhost:5000`.

## База данных и первый запуск

При запуске `app.py` приложение:

- создаёт таблицы в SQLite (если их ещё нет);
- создаёт администратора по умолчанию (если он отсутствует).
- Файл БД создаётся в `instance/planeta_shop.db`.

## Доступ администратора

- **Email**: `admin@planeta.ru`
- **Пароль**: `admin123`
После входа откройте админ‑панель: `http://localhost:5000/admin` (или пункт **«Админ»** в меню).

## Доступ пользователей

- **Email**: `ivanov@example.com`
- **Пароль**: `user123`
- **Почты пользователей и их пароли**
=============================
ivanov@example.com	user123
petrov@example.com	user123
sidorov@example.com	user123
smirnova@example.com	user123
kozlov@example.com	user123
=============================