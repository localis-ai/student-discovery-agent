# --- Stage 1: Builder ---
FROM python:3.11-slim-bullseye AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Chỉ cài đặt build-essential để compile một số package nếu cần
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Sử dụng uv để cài đặt dependency cực nhanh
COPY requirements.txt .
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache -r requirements.txt

# --- Stage 2: Final Runtime ---
FROM python:3.11-slim-bullseye

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV ENV=production

WORKDIR /app

# Tạo user hệ thống để bảo mật
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Cài đặt runtime dependencies (bỏ các gói -dev và build tool không cần thiết)
# Chỉ giữ lại các thư viện shared object cần cho ứng dụng (ví dụ: WeasyPrint/Pango)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    sudo \
    libpango-1.0-0 \
    libharfbuzz0b \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libfontconfig1 \
    shared-mime-info \
    libglib2.0-0 \
    libopenjp2-7 \
    libmagic1 \
    ffmpeg \
    fonts-dejavu-core \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy python packages từ builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy source code và set quyền sở hữu 1 lần duy nhất để tối ưu layer
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser main.py start.sh ./

# Fix line endings và phân quyền thực thi
RUN chmod +x start.sh && sed -i 's/\r$//' start.sh

# Tạo thư mục config và gán quyền
RUN mkdir -p /app/config && chown appuser:appuser /app/config
VOLUME ["/app/config"]

USER root

EXPOSE 8000

# Sử dụng ENTRYPOINT để handle signal tốt hơn (ví dụ: SIGTERM khi stop container)
ENTRYPOINT ["/bin/bash", "/app/start.sh"]
