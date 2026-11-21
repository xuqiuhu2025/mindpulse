FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# 不以 root 运行
RUN useradd --create-home mindpulse
USER mindpulse

EXPOSE 8000

# 数据目录由 docker-compose 通过卷挂载（sqlite 文件）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
