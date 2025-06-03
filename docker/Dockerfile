# syntax=docker/dockerfile:1
#
# ─────────────────── STAGE: builder ───────────────────
#
FROM python:3.11-slim AS builder

# 1) Устанавливаем системные утилиты для сборки
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       curl \
       build-essential \
    && rm -rf /var/lib/apt/lists/*

# 2) Обновляем pip, ставим Poetry 2 и подключаем плагин export
RUN python -m pip install --upgrade pip \
    && curl -sSL https://install.python-poetry.org | python - \
    && export PATH="/root/.local/bin:$PATH" \
    && poetry self add poetry-plugin-export

# 3) Делаем так, чтобы во всех следующих шагах PATH уже содержал /root/.local/bin
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# 4) Копируем в билд-контекст только файлы с зависимостями
COPY pyproject.toml poetry.lock ./

# 5) Экспортируем «главные» зависимости (без dev-группы) в requirements.txt
#    Используем плагин: вместо '--without-dev' — '--only main'
RUN poetry export \
      --without-hashes \
      --no-interaction \
      --format requirements.txt \
      --only main \
      -o requirements.txt

# ─────────────────── STAGE: final ───────────────────
#
FROM python:3.11-slim

# 6) Устанавливаем минимальный набор системных библиотек для рантайма
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libgl1 \
       libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 7) Копируем requirements.txt из builder-стадии и устанавливаем зависимости
COPY --from=builder /app/requirements.txt ./
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 8) Копируем весь исходный код проекта
COPY . .

# 9) Определяем команду запуска приложения
#    Замените "main.py" на вашу реальную точку входа, если она другая
CMD ["python", "main.py"]
