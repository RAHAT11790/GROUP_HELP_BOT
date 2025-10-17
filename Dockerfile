# Dockerfile for RS-GROUP-BOT (Flask uptime server)
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

ENV PORT=5000
EXPOSE 5000

CMD [ "gunicorn", "--bind", "0.0.0.0:5000", "app:app", "--workers", "2" ]
