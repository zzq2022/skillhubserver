# skillhubserver — 常用命令快捷入口 / Common command shortcuts
# 用法 / Usage:  make <target>   (默认 default: help)

.DEFAULT_GOAL := help
.PHONY: help install dev-backend dev-frontend test lint build-frontend migrate docker-up

help: ## 显示可用命令 / Show available targets
	@echo "skillhubserver — 可用命令 / available targets:"
	@echo "  install         安装后端与前端依赖 / install backend + frontend deps"
	@echo "  dev-backend     启动后端开发服务器 / run backend dev server"
	@echo "  dev-frontend    启动前端开发服务器 / run frontend dev server"
	@echo "  test            运行后端测试 / run backend tests"
	@echo "  lint            代码检查 / lint code"
	@echo "  build-frontend  构建前端产物 / build frontend"
	@echo "  migrate         应用数据库迁移 / apply DB migrations"
	@echo "  docker-up       构建并启动容器 / build and start containers"

install: ## 安装后端 (uv) 与前端 (npm) 依赖
	uv sync --directory backend
	cd frontend && npm install

dev-backend: ## 启动后端开发服务器（热重载）
	uv run --directory backend uvicorn app.main:app --reload --host 0.0.0.0 --port 3000

dev-frontend: ## 启动前端开发服务器
	cd frontend && npm run dev

test: ## 运行后端 pytest
	uv run --directory backend pytest

lint: ## 代码检查（如已配置 ruff）
	uv run --directory backend ruff check . || echo "ruff 未配置，跳过 / ruff not configured, skipping"

build-frontend: ## 构建前端生产产物
	cd frontend && npm run build

migrate: ## 应用 Alembic 数据库迁移
	uv run --directory backend alembic upgrade head

docker-up: ## 使用 docker compose 构建并启动
	docker compose -f docker/docker-compose.yml up --build
