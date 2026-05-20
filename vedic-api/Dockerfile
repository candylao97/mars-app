FROM python:3.11-slim

# pyswisseph 是 C 扩展。基础镜像无 build-essential 时退路靠 wheel;先装上以防回退。
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖,利用 Docker 层缓存
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 代码
COPY app/ ./app/

# Anthropic 调用会跑 60-80 秒,前置代理(如 Nginx)的话别 buffer streaming response
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

EXPOSE 8000

# --proxy-headers:信任反向代理的 X-Forwarded-* 头
# --forwarded-allow-ips="*":允许任意上游(部署平台自身的 ingress 决定可访问性)
# 单 worker:Anthropic streaming 在单进程内逐 chunk yield,多 worker 不会加快单请求,反而占内存
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
