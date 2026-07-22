# SkillHub Server — 项目上下文

## 项目定位
自托管技能管理平台。Python (FastAPI) 后端 + React (Vite) 前端，单容器部署。

## 核心技术栈
- 后端：Python 3.12+, FastAPI, SQLAlchemy 2, Alembic, Pydantic, Argon2id, uv
- 前端：React 18, TypeScript, Vite, Tailwind CSS, react-i18next (en/zh)
- 数据库：SQLite + PostgreSQL 双支持（配置文件切换）
- 测试：pytest + 双数据库参数化 fixture
- 部署：Docker 单容器，FastAPI 同源托管前端静态资源

## 关键设计决策
- API 前缀 `/api/v1`，重新设计（不兼容旧 PromptHub API）
- 认证：服务端 Session + HttpOnly Cookie + CSRF 双提交 Token
- 账号：多用户、管理员创建、admin/user 两级角色
- 技能：private/public 两级可见性、按用户唯一名（owner/name 命名空间）
- 发布：所有者提交 → 管理员审核（draft → pending_review → published）
- 存储：文件系统工作区 + 数据库元数据（双真理源、frontmatter↔DB 同步）
- 版本：线性自增 + 快照保留（只读历史）
- 搜索：数据库专用适配器（SQLite FTS5 / PostgreSQL tsvector）
- media：仅本地上传（5MB，JPEG/PNG/WebP/SVG）
- 导入导出：ZIP 归档
- 首次初始化：首启引导页面

## 目录布局
```
skillhubserver/
├── backend/        # Python FastAPI 服务
│   ├── app/        # 主应用包
│   ├── alembic/    # 数据库迁移
│   └── tests/      # pytest 测试
├── frontend/       # React Vite 应用
├── docker/         # Dockerfile + compose
└── docs/           # 设计文档（proposal/design/tasks）
```

## 详细设计
完整设计见 `docs/design.md`，任务清单见 `docs/tasks.md`，决策记录见 `docs/proposal.md`。

## 开发命令（规划中）
- `cd backend && uv sync` — 安装 Python 依赖
- `cd backend && uv run pytest` — 运行测试
- `cd frontend && npm install && npm run dev` — 前端开发
- `docker compose up --build` — 完整部署
