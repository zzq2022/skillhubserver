# 技术设计：skillhubserver

> 状态：草稿（基于 proposal.md 29 项已确认决策）
> 变更关键字：migrate-web-backend-to-python-skillhubserver

## 1. 系统概述

skillhubserver 是一个独立的自托管技能管理平台，由 Python (FastAPI) 后端和 React (Vite) 前端组成，部署为单容器服务。

**核心能力**：技能 CRUD 与版本管理、公开目录与审核、用户认证与账号管理、导入导出、基础媒体上传。

**不包含**：AI 安全扫描、WebDAV 多设备同步、设备管理。

## 2. 仓库目录布局

```
skillhubserver/
├── backend/                      # Python FastAPI 服务
│   ├── pyproject.toml            # uv 项目配置
│   ├── uv.lock                   # 锁文件
│   ├── alembic.ini               # Alembic 配置
│   ├── alembic/                  # 数据库迁移
│   │   ├── env.py
│   │   └── versions/
│   ├── app/                      # 应用主包
│   │   ├── __init__.py
│   │   ├── main.py               # FastAPI 应用入口 + 静态文件托管
│   │   ├── config.py             # Pydantic Settings 配置
│   │   ├── database.py           # SQLAlchemy engine/session 工厂
│   │   ├── models/               # SQLAlchemy ORM 模型
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── session.py
│   │   │   ├── skill.py
│   │   │   ├── skill_version.py
│   │   │   ├── review.py
│   │   │   └── media.py
│   │   ├── schemas/              # Pydantic 请求/响应 schema
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── user.py
│   │   │   ├── skill.py
│   │   │   ├── review.py
│   │   │   └── media.py
│   │   ├── routers/              # FastAPI 路由模块
│   │   │   ├── __init__.py
│   │   │   ├── bootstrap.py
│   │   │   ├── auth.py
│   │   │   ├── admin.py
│   │   │   ├── skills.py
│   │   │   ├── skillhub.py
│   │   │   ├── import_export.py
│   │   │   └── media.py
│   │   ├── services/             # 业务逻辑层
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py
│   │   │   ├── user_service.py
│   │   │   ├── skill_service.py
│   │   │   ├── skill_workspace.py
│   │   │   ├── review_service.py
│   │   │   ├── import_export_service.py
│   │   │   └── media_service.py
│   │   ├── repositories/         # 数据访问层
│   │   │   ├── __init__.py
│   │   │   ├── user_repo.py
│   │   │   ├── session_repo.py
│   │   │   ├── skill_repo.py
│   │   │   ├── review_repo.py
│   │   │   ├── media_repo.py
│   │   │   └── search/
│   │   │       ├── __init__.py
│   │   │       ├── base.py       # SearchRepository 抽象
│   │   │       ├── sqlite_fts.py # SQLite FTS5 实现
│   │   │       └── pg_tsvector.py# PostgreSQL tsvector 实现
│   │   ├── middleware/           # 中间件
│   │   │   ├── __init__.py
│   │   │   ├── session_auth.py   # Session 认证
│   │   │   ├── csrf.py           # CSRF 双提交校验
│   │   │   └── security_headers.py
│   │   └── utils/                # 工具函数
│   │       ├── __init__.py
│   │       ├── password.py       # Argon2id 哈希
│   │       └── skill_name.py     # 技能名验证/slugify
│   └── tests/                    # pytest 测试
│       ├── conftest.py           # 双数据库 fixture
│       ├── unit/
│       ├── integration/
│       └── fixtures/
├── frontend/                     # React Vite 应用
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── api/                  # 新 API 客户端层
│   │   ├── components/
│   │   ├── contexts/
│   │   ├── layouts/
│   │   ├── pages/
│   │   ├── locales/              # en.json, zh.json
│   │   ├── i18n.ts
│   │   └── index.css
│   └── public/
├── docker/
│   ├── Dockerfile                # 多阶段构建：前端build → Python运行时
│   └── docker-compose.yml
├── .env.example
├── README.md
└── Makefile                      # 常用命令快捷入口
```

## 3. 数据模型（SQLAlchemy ORM）

### 3.1 users 表

| 列 | 类型 | 约束 |
|----|------|------|
| id | UUID (String 36) | PK |
| username | String(50) | UNIQUE, NOT NULL |
| password_hash | String(255) | NOT NULL |
| role | Enum('admin','user') | NOT NULL, DEFAULT 'user' |
| is_active | Boolean | NOT NULL, DEFAULT true |
| created_at | DateTime(timezone=True) | NOT NULL |
| updated_at | DateTime(timezone=True) | NOT NULL |

- username 大小写不敏感唯一（存储保留原始大小写，查询 lower）。
- password_hash 使用 Argon2id。

### 3.2 sessions 表

| 列 | 类型 | 约束 |
|----|------|------|
| id | String(64) | PK（随机 token） |
| user_id | UUID | FK → users.id ON DELETE CASCADE |
| csrf_token | String(64) | NOT NULL |
| created_at | DateTime | NOT NULL |
| expires_at | DateTime | NOT NULL |
| last_active_at | DateTime | NOT NULL |

- Session 过期策略：绝对过期 7 天 + 滑动 idle 30 分钟。
- 清理：后台定时任务或每次认证时惰性清理。

### 3.3 skills 表

| 列 | 类型 | 约束 |
|----|------|------|
| id | UUID | PK |
| owner_id | UUID | FK → users.id ON DELETE CASCADE |
| name | String(100) | NOT NULL |
| slug | String(100) | NOT NULL |
| description | Text | |
| visibility | Enum('private','public') | NOT NULL, DEFAULT 'private' |
| publish_status | Enum('draft','pending_review','published','rejected') | NOT NULL, DEFAULT 'draft' |
| version | Integer | NOT NULL, DEFAULT 1 |
| tags | JSON | DEFAULT [] |
| author | String(100) | |
| model | String(100) | |
| created_at | DateTime | NOT NULL |
| updated_at | DateTime | NOT NULL |

- UNIQUE(owner_id, slug)：按用户唯一。
- slug 由 name 派生，用于文件系统目录名和 URL。

### 3.4 skill_versions 表

| 列 | 类型 | 约束 |
|----|------|------|
| id | UUID | PK |
| skill_id | UUID | FK → skills.id ON DELETE CASCADE |
| version_number | Integer | NOT NULL |
| snapshot_path | String(500) | NOT NULL |
| created_at | DateTime | NOT NULL |
| notes | Text | |

- UNIQUE(skill_id, version_number)。
- snapshot_path 指向工作区 versions 目录下的快照文件。

### 3.5 reviews 表

| 列 | 类型 | 约束 |
|----|------|------|
| id | UUID | PK |
| skill_id | UUID | FK → skills.id ON DELETE CASCADE |
| submitter_id | UUID | FK → users.id |
| reviewer_id | UUID | FK → users.id, NULLABLE |
| status | Enum('pending','approved','rejected') | NOT NULL, DEFAULT 'pending' |
| comment | Text | |
| submitted_at | DateTime | NOT NULL |
| reviewed_at | DateTime | |

### 3.6 media 表

| 列 | 类型 | 约束 |
|----|------|------|
| id | UUID | PK |
| owner_id | UUID | FK → users.id ON DELETE CASCADE |
| filename | String(255) | NOT NULL |
| content_type | String(100) | NOT NULL |
| size_bytes | Integer | NOT NULL |
| storage_path | String(500) | NOT NULL |
| created_at | DateTime | NOT NULL |

- 允许类型：image/jpeg, image/png, image/webp, image/svg+xml。
- 单文件上限 5MB。

### 3.7 全文搜索

**SQLite**：创建 FTS5 虚拟表 `skills_fts(name, description, tags, content=skills)`，通过触发器与 skills 表同步。

**PostgreSQL**：在 skills 表增加 `search_vector tsvector` 列，GIN 索引，通过触发器维护。

统一契约接口 `SearchRepository.search(query, owner_id?, visibility?) → list[SkillSearchResult]`。


## 4. API 路由设计

所有 API 使用前缀 `/api/v1`。响应统一包络：
- 成功：`{ "data": ... }` 或 `{ "data": [...], "pagination": {...} }`
- 失败：`{ "error": { "code": "...", "message": "..." } }`

### 4.1 Bootstrap

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /api/v1/bootstrap | 无 | 返回 `{initialized, registrationClosed}` |
| POST | /api/v1/bootstrap/init | 无 | 创建首个管理员（仅 initialized=false 时可用） |

### 4.2 Auth

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| POST | /api/v1/auth/login | 无 | 用户名+密码登录，Set-Cookie session |
| POST | /api/v1/auth/logout | Session | 删除 session，清除 cookie |
| GET | /api/v1/auth/me | Session | 当前用户信息 |
| PUT | /api/v1/auth/password | Session+CSRF | 修改密码 |

### 4.3 Admin

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /api/v1/admin/users | Admin | 用户列表 |
| POST | /api/v1/admin/users | Admin+CSRF | 创建用户 |
| PUT | /api/v1/admin/users/:id/role | Admin+CSRF | 修改角色 |
| PUT | /api/v1/admin/users/:id/status | Admin+CSRF | 启用/禁用用户 |
| DELETE | /api/v1/admin/users/:id | Admin+CSRF | 删除用户 |
| GET | /api/v1/admin/stats | Admin | 实例统计 |

### 4.4 Skills（私有，当前用户）

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /api/v1/skills | Session | 列出当前用户技能（分页、搜索） |
| POST | /api/v1/skills | Session+CSRF | 创建技能 |
| GET | /api/v1/skills/:id | Session | 获取技能详情 |
| PUT | /api/v1/skills/:id | Session+CSRF | 更新技能元数据 |
| DELETE | /api/v1/skills/:id | Session+CSRF | 删除技能 |
| GET | /api/v1/skills/:id/content | Session | 获取 SKILL.md 内容 |
| PUT | /api/v1/skills/:id/content | Session+CSRF | 更新 SKILL.md 内容 |
| GET | /api/v1/skills/:id/versions | Session | 列出版本历史 |
| POST | /api/v1/skills/:id/versions | Session+CSRF | 创建新版本快照 |
| POST | /api/v1/skills/:id/submit | Session+CSRF | 提交审核 |

### 4.5 SkillHub（公开目录）

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /api/v1/hub/skills | 无 | 公开技能列表（分页、搜索、标签过滤） |
| GET | /api/v1/hub/skills/:owner/:name | 无 | 公开技能详情 |
| GET | /api/v1/hub/skills/:owner/:name/download | 无 | 下载技能包（ZIP） |

### 4.6 Reviews（管理员审核）

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | /api/v1/admin/reviews | Admin | 待审列表 |
| PUT | /api/v1/admin/reviews/:id/approve | Admin+CSRF | 批准 |
| PUT | /api/v1/admin/reviews/:id/reject | Admin+CSRF | 驳回（含 comment） |

### 4.7 Import/Export

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| POST | /api/v1/skills/import | Session+CSRF | 上传 ZIP 导入技能 |
| GET | /api/v1/skills/:id/export | Session | 导出技能为 ZIP |

### 4.8 Media

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| POST | /api/v1/media/upload | Session+CSRF | 上传文件（multipart/form-data） |
| GET | /api/v1/media/:id | Session | 获取/展示媒体文件 |
| DELETE | /api/v1/media/:id | Session+CSRF | 删除媒体 |

## 5. 认证与会话流程

### 5.1 登录

```
POST /api/v1/auth/login
Body: { "username": "admin", "password": "..." }
→ 200: Set-Cookie: session_id=<random64>; HttpOnly; SameSite=Lax; Path=/; [Secure]
       Body: { "data": { "user": {...}, "csrfToken": "<random64>" } }
```

前端收到 csrfToken 后存入内存，后续写操作在 `X-CSRF-Token` 头中回传。

### 5.2 Session 验证

每个需认证的请求：
1. 从 Cookie 中取 `session_id`
2. 查 sessions 表，验证存在 + 未过期 + user.is_active
3. 更新 `last_active_at`（滑动续期）
4. 写操作额外校验 `X-CSRF-Token` == session.csrf_token

### 5.3 登出

```
POST /api/v1/auth/logout
→ 200: Set-Cookie: session_id=; Max-Age=0
```

删除 sessions 表中对应记录。

## 6. 技能工作区（文件系统）

### 6.1 目录布局

```
$DATA_ROOT/
├── skills/                           # 技能工作区根目录
│   └── <slug>__<skill_id>/           # 单个技能包
│       ├── SKILL.md                  # 内容真理源
│       ├── skill.json                # 元数据缓存（frontmatter 镜像）
│       ├── versions/
│       │   ├── 0001/
│       │   │   └── SKILL.md          # 版本快照
│       │   └── 0002/
│       │       └── SKILL.md
│       └── assets/                   # 技能附带文件（脚本、模板等）
├── media/                            # 上传媒体文件
│   └── <year>/<month>/<uuid>.<ext>
└── db/                               # SQLite 数据库文件（SQLite 模式下）
    └── skillhubserver.db
```

### 6.2 Frontmatter↔DB 同步规则

- **写入方向**：
  - 通过 API 修改元数据 → 更新 DB + 同步写入 SKILL.md frontmatter
  - 外部修改 SKILL.md → 通过扫描/事件检测 → 更新 DB
- **同步键**：`name`, `description`, `version`, `tags`, `author`, `model`
- **冲突策略**：API 写入为主（与现有系统一致）；外部修改在下次读取时合并

## 7. 配置管理

通过 `.env` 文件或环境变量配置，Pydantic Settings 解析：

```python
class Settings(BaseSettings):
    # 服务
    HOST: str = "0.0.0.0"
    PORT: int = 3000
    
    # 数据库
    DATABASE_TYPE: Literal["sqlite", "postgresql"] = "sqlite"
    DATABASE_URL: str = "sqlite:///./data/db/skillhubserver.db"
    
    # 数据目录
    DATA_ROOT: str = "./data"
    
    # Session
    SESSION_MAX_AGE: int = 604800        # 7 天（秒）
    SESSION_IDLE_TIMEOUT: int = 1800     # 30 分钟（秒）
    SESSION_COOKIE_NAME: str = "session_id"
    SECRET_KEY: str                      # 必填，用于 CSRF token 签名验证
    
    # Media
    MAX_UPLOAD_SIZE: int = 5_242_880     # 5MB
    
    # 日志
    LOG_LEVEL: str = "info"
    
    model_config = SettingsConfigDict(env_file=".env")
```

## 8. 部署架构

### 8.1 Docker 多阶段构建

```dockerfile
# Stage 1: 前端构建
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/ .
RUN npm ci && npm run build

# Stage 2: Python 运行时
FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=frontend-build /app/frontend/dist /app/static
COPY backend/ /app/backend/
RUN pip install uv && cd backend && uv sync --frozen
EXPOSE 3000
CMD ["uv", "run", "--directory", "backend", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3000"]
```

### 8.2 docker-compose.yml

```yaml
services:
  skillhubserver:
    build: .
    ports:
      - "3000:3000"
    volumes:
      - skillhub_data:/app/data
    env_file:
      - .env
    restart: unless-stopped

volumes:
  skillhub_data:
```

### 8.3 PostgreSQL 模式

```yaml
services:
  skillhubserver:
    # ...同上
    depends_on:
      - db
    environment:
      DATABASE_TYPE: postgresql
      DATABASE_URL: postgresql+asyncpg://user:pass@db:5432/skillhub

  db:
    image: postgres:16-alpine
    volumes:
      - pg_data:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: skillhub
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
```

## 9. 测试策略

### 9.1 双数据库 fixture

```python
# tests/conftest.py
import pytest
from app.database import create_engine_for

@pytest.fixture(params=["sqlite", "postgresql"])
def db_session(request, tmp_path):
    if request.param == "sqlite":
        url = f"sqlite:///{tmp_path}/test.db"
    else:
        url = "postgresql://test:test@localhost:5433/test"
    engine = create_engine_for(url)
    # ... setup tables, yield session, teardown
```

### 9.2 测试分层

| 层 | 范围 | 运行条件 |
|----|------|----------|
| unit | services, utils, schemas | 始终 |
| integration | repositories + 真实 DB | 双数据库 fixture |
| api | routers（httpx TestClient） | 双数据库 fixture |
| search | SearchRepository 契约测试 | 双数据库 fixture |

### 9.3 搜索契约测试要点

- 精确匹配：查询 "my-skill" 必须返回名为 "my-skill" 的结果
- 部分匹配：查询 "skill" 匹配包含 "skill" 的名称/描述
- 特殊字符安全：SQL 注入 payload 不能导致错误
- 空查询：返回空列表而非报错
- 可见性过滤：不返回不可见技能

## 10. 模块边界与依赖方向

```
routers → services → repositories → database/filesystem
   ↓         ↓            ↓
schemas   models     search adapters
```

- routers：HTTP 层，仅做请求解析、调用 service、返回响应
- services：业务规则，不直接操作 DB 或文件系统
- repositories：数据访问，封装 SQLAlchemy 查询和文件 I/O
- middleware：认证、CSRF、安全头，横切关注点
- 禁止循环依赖：routers 不能被 services 导入，services 不能被 repositories 导入
