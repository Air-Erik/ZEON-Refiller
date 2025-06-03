# syntax=docker/dockerfile:1
########################################
# 1. Builder stage: генерируем requirements.txt
########################################
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем poetry для экспорта зависимостей
RUN python -m pip install --upgrade pip \
    && pip install poetry

WORKDIR /app

# Копируем только файлы зависимостей
COPY pyproject.toml poetry.lock ./

# Экспортируем в requirements.txt
RUN poetry export \
      --without-hashes \
      --no-interaction \
      --format requirements.txt \
      --without-dev \
      -o requirements.txt

########################################
# 2. Final stage: собираем минимальный образ
########################################
FROM python:3.11-slim

WORKDIR /app

# Системные библиотеки для OpenCV и т.п.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libgl1 \
      libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements.txt из builder
COPY --from=builder /app/requirements.txt .

# Устанавливаем все runtime-зависимости
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Копируем остальной код (app/, source/, config/ и пр.)
COPY . .

# При необходимости копируем файл с переменными
# COPY config/docker.env ./.env

# Экспонируем порт, если ваш сервис слушает (например, 8080)
# EXPOSE 8080

# Запускаем через точку входа. Можно заменить на «vm-refiller»,
# если прописали его в pyproject.toml как скрипт
ENTRYPOINT ["python", "-m", "app"]
