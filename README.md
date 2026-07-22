# skillhubserver

自托管的技能管理平台（self-hosted skill management platform）。Python (FastAPI) 后端 + React (Vite) 前端，构建为**单容器**部署：FastAPI 同源托管前端静态资源，无需额外的 Web 服务器。

- 多用户、管理员创建账号，admin / user 两级角色
- 技能 private / public 两级可见性，按用户命名空间（owner/name）唯一
- 发布审核流：所有者提交 → 管理员审核（draft → pending_review → published）
- 文件系统工作区 + 数据库元数据双真理源，frontmatter ↔ DB 同步
- 全文搜索（SQLite FTS5 / PostgreSQL tsvector），ZIP 导入导出，本地媒体上传
- 服务端 Session + HttpOnly Cookie + CSRF 双提交 Token 认证

## 技术栈 / Tech stack

| 层 | 技术 |
| --- | --- |
| 后端 | Python 3.12+, FastAPI, SQLAlchemy 2, Alembic, Pydantic, Argon2id, uv |
| 前端 | React 18, TypeScript, Vite, Tailwind CSS, react-i18next (en/zh) |
| 数据库 | SQLite（默认）+ PostgreSQL（可切换） |
| 测试 | pytest（双数据库参数化 fixture） |
| 部署 | Docker 单容器 |

## 环境要求 / Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)（Python 包与环境管理）
- Node.js 20+
- Docker（可选，用于容器化部署）

## 快速开始 / Quick start

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，至少设置 SECRET_KEY：
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. 后端 / Backend

```bash
cd backend
uv sync                 # 安装依赖
uv run alembic upgrade head    # 应用数据库迁移
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 3000
```

### 3. 前端 / Frontend

```bash
cd frontend
npm install
npm run dev
```

### 4. Docker（一体化部署）

```bash
docker compose -f docker/docker-compose.yml up --build
```

启动后首次访问会进入**首启引导页面**，用于创建第一个管理员账号。

### Makefile 快捷命令

项目根目录提供 `Makefile`，常用命令：

```bash
make install         # 安装后端 + 前端依赖
make dev-backend     # 启动后端开发服务器
make dev-frontend    # 启动前端开发服务器
make test            # 运行后端测试
make migrate         # 应用数据库迁移
make docker-up       # 构建并启动容器
make help            # 查看全部命令
```

## 配置 / Configuration

所有配置通过 `.env` 文件或环境变量提供，由 Pydantic Settings 解析。完整变量清单与说明见 [`.env.example`](./.env.example)，关键项：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `HOST` / `PORT` | `0.0.0.0` / `3000` | 服务监听地址与端口 |
| `DATABASE_TYPE` | `sqlite` | 数据库类型：`sqlite` \| `postgresql` |
| `DATABASE_URL` | `sqlite:///./data/db/skillhubserver.db` | 数据库连接串 |
| `DATA_ROOT` | `./data` | 技能工作区 / 数据库 / 媒体根目录 |
| `SECRET_KEY` | *(必填)* | CSRF token 签名密钥，需强随机值 |
| `SESSION_MAX_AGE` | `604800` | 会话最长有效期（秒） |
| `SESSION_IDLE_TIMEOUT` | `1800` | 会话空闲超时（秒） |
| `MAX_UPLOAD_SIZE` | `5242880` | 单文件上传上限（字节，5 MB） |
| `LOG_LEVEL` | `info` | 日志级别 |

切换到 PostgreSQL：设置 `DATABASE_TYPE=postgresql` 并将 `DATABASE_URL` 改为
`postgresql+asyncpg://user:pass@host:5432/skillhub`。

## 项目结构 / Project structure

```
skillhubserver/
├── backend/          # Python FastAPI 服务
│   ├── app/          # 应用主包（main / config / database / routers / services / repositories / models / schemas / middleware / utils）
│   ├── alembic/      # 数据库迁移
│   └── tests/        # pytest 测试（unit / integration / fixtures）
├── frontend/         # React Vite 应用（api / components / contexts / layouts / pages / locales）
├── docker/           # Dockerfile（多阶段）+ docker-compose.yml
├── docs/             # 设计文档
├── .env.example
├── Makefile
└── README.md
```

完整目录布局见 [`docs/design.md`](./docs/design.md) 第 2 节。

## API 摘要 / API overview

前缀 `/api/v1`。成功响应 `{ "data": ... }`，错误 `{ "error": { "code", "message" } }`。

| 区域 | 路径示例 |
| --- | --- |
| Bootstrap | `GET /bootstrap` · `POST /bootstrap/init` |
| Auth | `POST /auth/login` · `POST /auth/logout` · `GET /auth/me` · `PUT /auth/password` |
| Skills | `CRUD /skills` · content/versions · `POST /skills/:id/submit` · import/export |
| Hub | `GET /hub/skills` · `GET /hub/skills/:owner/:name` · download ZIP |
| Admin | users · stats · reviews approve/reject · unpublish |
| Media | `POST /media/upload` · `GET|DELETE /media/:id` |
| Health | `GET /health` |

写操作（除 login / bootstrap init）需 Cookie 会话 + `X-CSRF-Token` 请求头。

## 文档 / Docs

- [`docs/design.md`](./docs/design.md) — 技术设计（架构、数据模型、API、部署）
- [`docs/proposal.md`](./docs/proposal.md) — 决策记录
- [`docs/tasks.md`](./docs/tasks.md) — 实现任务清单
- [`CONTRIBUTING.md`](./CONTRIBUTING.md) — 开发与贡献指南
