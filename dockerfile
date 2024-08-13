# Dockerfile

# Используем официальный образ Python в качестве базового образа
FROM python:3.12-slim

# Устанавливаем рабочую директорию в контейнере
WORKDIR /app

# Копируем файлы requirements.txt в контейнер
COPY req.txt .

# Устанавливаем зависимости проекта
RUN pip install --no-cache-dir -r req.txt

# Копируем все файлы проекта в контейнер
COPY . .


# Команда для запуска вашего бота
CMD ["sh", "-c", "python bot.py & dramatiq spam.dramatiq_tasks --processes 4 --threads 8"]
