# syntax=docker/dockerfile:1
# ============================================================
# skillhubserver — 多阶段构建 / multi-stage build
# ------------------------------------------------------------
# 构建上下文必须为仓库根目录 / build context MUST be repo root:
#   docker build -f docker/Dockerfile -t skillhubserver .
# 或通过 docker-compose（已配置 context: ..）
#   docker compose -f docker/docker-compose.yml up --build
# ============================================================

# ------------------------------------------------------------
# Stage 1: 前端构建 / Frontend build
# ------------------------------------------------------------
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend

# 先复制清单文件以利用 Docker 层缓存 / copy manifests first for layer caching.
# frontend/package-lock.json 存在，因此使用 `npm ci`（可复现安装）。
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# 复制源码并构建（产物输出到 /app/frontend/dist）。
COPY frontend/ ./
RUN npm run build

# ------------------------------------------------------------
# Stage 2: Python 运行时 / Python runtime
# ------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # 数据根目录设为绝对路径，与 compose 命名卷挂载点一致，
    # 避免依赖运行时 CWD（CMD 通过 --directory backend 切到 backend/）。
    DATA_ROOT=/app/data \
    # uv 缓存放到可写、归属非 root 用户的目录。
    UV_CACHE_DIR=/app/.uv-cache

WORKDIR /app

# 安装 uv（Python 包/环境管理器）。
RUN pip install --no-cache-dir uv

# 复制后端并按锁文件安装依赖（--frozen 要求 uv.lock 与 pyproject 一致，来自 T0.2）。
COPY backend/ /app/backend/
RUN cd backend && uv sync --frozen

# 从前端构建阶段拷贝静态产物到 /app/static（FastAPI 同源托管，见 T10.2）。
COPY --from=frontend-build /app/frontend/dist /app/static

# 创建数据卷挂载点并使用非 root 用户运行。
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data /app/.uv-cache \
    && chown -R appuser:appuser /app

VOLUME ["/app/data"]

USER appuser

EXPOSE 3000

# 运行时读取环境变量（由 compose 的 env_file 注入）。
# 通过 uv 运行 uvicorn；--directory backend 使 app 包可被导入。
CMD ["uv", "run", "--directory", "backend", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3000"]
