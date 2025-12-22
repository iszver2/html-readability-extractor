# HTML Readability Extractor - Knowledge Base

## Обзор проекта

Flask-микросервис для извлечения чистого текста из HTML-страниц. Основное применение — обработка чеков ОФД (Оператор Фискальных Данных) для последующего парсинга GPT-4 nano с минимальным расходом токенов.

## Ключевые особенности

- **Basic Authentication** — защита эндпоинтов
- **OFD-специфичная обработка** — извлечение данных из HTML-закодированных контейнеров чеков
- **Фильтрация URL** — удаление tracking-ссылок, сохранение важных (PDF чека, ФНС)
- **Удаление рекламы** — очистка от промо-блоков и шума
- **Multi-platform Docker** — поддержка amd64 и arm64 (MacBook)

## Архитектура OFD-извлечения

### Контейнеры чеков (приоритет)
```python
OFD_CONTENT_SELECTORS = [
    '#fido_cheque_container',  # Основной контейнер (HTML-encoded)
    '.check_ctn',              # Контейнер чека
    '.js__cheque_fido_constructor',  # Альтернативный контейнер
]
```

### Особенность `#fido_cheque_container`
Содержимое чека хранится как HTML-закодированный текст внутри элемента. Требуется:
1. Получить текстовое содержимое контейнера
2. Декодировать HTML entities (`html.unescape`)
3. Распарсить результат как новый HTML

### Важные ссылки для сохранения
- `/cheque/pdf` — PDF чека (исключая oferta)
- `nalog.gov.ru` — проверка ФНС

### URL для фильтрации (tracking)
- `urlstats.platformaofd.ru`
- `share.floctory.com`
- `cdn1.platformaofd.ru/checkmarketing`
- `mc.yandex.ru`
- `jivosite.com`

## Запуск

### Локально (разработка)
```bash
# Создать venv (на Mac обязательно)
python3 -m venv /tmp/test-venv
source /tmp/test-venv/bin/activate
pip install -r requirements.txt

# Запуск
python app.py
```

### Docker
```bash
# Собрать локально
docker build -t html-extractor .

# Запустить (порт 5000 на Mac занят AirPlay, используй 5001)
docker run -d --name html-extractor \
  -p 5001:5000 \
  -e BASIC_AUTH_USERNAME=admin \
  -e BASIC_AUTH_PASSWORD=password \
  html-extractor

# Или из GHCR
docker pull ghcr.io/iszver2/html-readability-extractor:latest
docker run -d --name html-extractor \
  -p 5001:5000 \
  -e BASIC_AUTH_USERNAME=admin \
  -e BASIC_AUTH_PASSWORD=password \
  ghcr.io/iszver2/html-readability-extractor:latest
```

## Тестирование

### Unit-тесты
```bash
pytest test_app.py -v
```

### Ручное тестирование API

Health check (без авторизации):
```bash
curl http://localhost:5001/health
```

Извлечение текста:
```bash
curl -X POST http://localhost:5001/extract-text \
  -u admin:password \
  -H "Content-Type: application/json" \
  -d '{"html": "<html><body><h1>Test</h1><p>Content</p></body></html>"}'
```

Тест с файлом OFD:
```bash
curl -X POST http://localhost:5001/extract-text \
  -u admin:password \
  -H "Content-Type: application/json" \
  -d @example.ofd-page.json
```

## API Endpoints

### GET /health
Проверка состояния сервиса. Без аутентификации.

**Response:**
```json
{"status": "healthy"}
```

### POST /extract-text
Извлечение текста из HTML. Требует Basic Auth.

**Request:**
```json
{"html": "<html>...</html>"}
```

**Response:**
```json
{
  "text": "Извлечённый текст чека...",
  "length": 3125,
  "links": {
    "pdf": "https://platformaofd.ru/.../cheque/pdf?...",
    "fns": "https://nalog.gov.ru/..."
  }
}
```

## Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `BASIC_AUTH_USERNAME` | admin | Логин для Basic Auth |
| `BASIC_AUTH_PASSWORD` | password | Пароль для Basic Auth |
| `FLASK_HOST` | 0.0.0.0 | Хост для bind |
| `FLASK_PORT` | 5000 | Порт сервиса |
| `FLASK_DEBUG` | False | Debug режим |

## CI/CD

GitHub Actions workflow (`.github/workflows/docker-build.yml`):

1. **test** — запуск pytest
2. **build-and-push** — сборка multi-platform образа и push в GHCR

### Multi-platform сборка
Используется QEMU + Buildx для сборки под:
- `linux/amd64` — стандартные серверы
- `linux/arm64` — Apple Silicon Mac

## Библиотеки

| Библиотека | Назначение |
|------------|------------|
| Flask | Web framework |
| BeautifulSoup4 | HTML parsing |
| lxml | HTML parser backend |
| inscriptis | HTML → text с сохранением структуры таблиц |
| readability-lxml | Извлечение основного контента (legacy) |
| pytest | Тестирование |

## Известные проблемы

### Порт 5000 на Mac
macOS использует порт 5000 для AirPlay Receiver. Решение:
- Использовать другой порт (5001)
- Отключить AirPlay Receiver в System Preferences

### externally-managed-environment на Mac
Python на Mac требует venv. Решение:
```bash
python3 -m venv /tmp/test-venv
source /tmp/test-venv/bin/activate
```

## Метрики эффективности

Тестовый файл OFD чека:
- **Вход:** 77,956 символов (сырой HTML)
- **Выход:** 3,125 символов (чистый текст + ссылки)
- **Сокращение:** ~25x

## Структура проекта

```
html-readability-extractor/
├── .claude/
│   └── agents.md          # Этот файл
├── .github/
│   └── workflows/
│       └── docker-build.yml
├── app.py                 # Основное приложение
├── test_app.py            # Unit-тесты
├── requirements.txt       # Зависимости Python
├── Dockerfile             # Multi-stage build
└── .dockerignore          # Исключения для Docker
```
