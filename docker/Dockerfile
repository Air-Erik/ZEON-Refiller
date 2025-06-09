# syntax=docker/dockerfile:1
# ---------- 1. Стадия builder: собираем зависимости -----------------
FROM python:3.11-slim AS builder

# 0. Установка переменных среды
# PYTHONDONTWRITEBYTECODE - запрещаем создание *.pyc файлов на диске. Ускоряем сборку
# PIP_NO_CACHE_DIR - Запрещаем кэш для pip. Иначе кэш пакетов останеться внутри образа
# POETRY_VIRTUALENVS_CREATE - ставим пакеты сразу в системный site-packages
ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=2.1.3 \
    POETRY_VIRTUALENVS_CREATE=false

# 1. Устанавливаем системные утилиты для сборки
# Обновляем пакеты ОС
# Компилятор чтобы собирать зависимости-С. Curl нужен для установки Poetry
# Устанавливем Poetry, не сохраняя кэш
# Чистим неиспользуемые зависимости и кэш apt
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    && apt-get install -y --no-install-recommends build-essential curl \
    && pip install --no-cache-dir "poetry==$POETRY_VERSION" \
    && apt-get purge -y curl \
    && apt-get autoremove -y \
    && apt-get clean

# 2. Устанавливаем рабочую директорию
    WORKDIR /src

# 3. Копируем в билд-контекст только файлы с зависимостями
COPY pyproject.toml poetry.lock ./

# 4. Запуск Poetry-установщика зависимостей
# Только боевые зависимости из группы main
RUN poetry install --only main --no-root

# 5. Копируем весь код приложения
COPY app ./app
COPY config ./config
COPY source ./source

# ---------- 2. Стадия runtime: лёгкий образ для запуска ------------
FROM python:3.11-slim AS runtime

# 6. Создаём группу и пользователя без sudo
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# 7. Убираем лишнее — только site-packages и приложение
# Берем скомпилированные пакеты. И не берем компиляторы, установщики pip, Poetry, кэш apt
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /src/app ./app
COPY --from=builder /src/config ./config
COPY --from=builder /src/source ./source

# 8. Меняем владельца файлов (только нужных директорий, чтобы не трогать системные)
RUN chown -R appuser:appgroup /usr/local/lib/python3.11/site-packages ./app ./config ./source

# 9. Меняем директорию чтобы относительные импорты «видели» пакет app
WORKDIR /src

# 10. Отключаем бифоризацию по 4кб. Логи приходят мнгновенно. Успевают дойти логи о падении контейнера
ENV PYTHONUNBUFFERED=1

# 11. Меняем пользователя от которого стартует контейнер
USER appuser

# 12. Запускаем приложение
CMD ["python", "-m", "app"]
