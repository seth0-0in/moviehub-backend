FROM python:3.10-slim

WORKDIR /app

# 필수 시스템 패키지 설치 (MySQL 클라이언트 등)
RUN apt-get update && apt-get install -y default-libmysqlclient-dev build-essential pkg-config

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]