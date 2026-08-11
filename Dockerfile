FROM python:3.11-slim

WORKDIR /app

COPY requierements.txt .
RUN pip install --no-cache-dir -r requierements.txt

COPY . .

CMD ["python", "telegram-movie-bot.py"]
