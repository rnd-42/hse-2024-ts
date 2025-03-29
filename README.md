System for Demand Elasticity Estimating based on Time Series Analysis
HSE 2024 Project

# HSE 2024 Time Series Database

Проект базы данных временных рядов для ВШЭ.

## Настройка окружения

1. Склонируйте репозиторий:

```bash
git clone <url-репозитория>
cd hse-2024-ts
```

2. Создайте и активируйте виртуальное окружение:

```bash
python -m venv venv
source venv/bin/activate  # для Linux/macOS
venv\Scripts\activate     # для Windows
```

3. Установите зависимости:

```bash
pip install -r requirements.txt
```

4. Настройте переменные окружения:

```bash
cp .env.example .env
```

5. Отредактируйте файл `.env`, указав правильные значения для подключения к базе данных и другие настройки:

```
SECRET_KEY=<ваш-секретный-ключ>
DEBUG=False
DB_PASSWORD=<пароль-базы-данных>
# и т.д.
```

6. Запустите сервер:

```bash
python manage.py runserver
```

## Работа с проектом

Проект использует переменные окружения для хранения конфиденциальных данных и параметров конфигурации. Все настройки хранятся в файле `.env`, который не включается в репозиторий.

### Структура проекта

- `djangoproject/` - настройки Django проекта
- `databaseadmin/` - основное приложение для администрирования базы данных временных рядов
