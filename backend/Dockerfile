FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 构建上下文 = 仓库根目录：
#   docker build -f backend/Dockerfile .
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app

# 版本化 Prompt 与危机脚本必须随镜像分发
# （app/main.py 的 PromptService 默认解析到 /prompts）
COPY prompts /prompts

# 不以 root 运行；/data 为容器内默认可写数据目录（docker-compose 会挂载卷）
RUN useradd --create-home mindpulse \
    && mkdir -p /data \
    && chown -R mindpulse:mindpulse /app /data
ENV MINDPULSE_DATABASE_URL=sqlite:////data/mindpulse.db
USER mindpulse

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
