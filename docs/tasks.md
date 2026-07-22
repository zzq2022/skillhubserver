# 实现任务清单：skillhubserver

> 状态：实现完成（Phase 0–11；PG 双库测试需设置 TEST_POSTGRESQL_URL）
> 依据：proposal.md（29 项决策）+ design.md（技术设计）

---

## Phase 0：仓库初始化

- [x] **T0.1** 创建独立 Git 仓库 `skillhubserver`，初始化 `backend/` 和 `frontend/` 顶层目录
- [x] **T0.2** backend：初始化 `pyproject.toml`（uv），添加核心依赖（fastapi, uvicorn, sqlalchemy, alembic, pydantic, pydantic-settings, argon2-cffi, python-multipart）
- [x] **T0.3** backend：创建 `app/` 包结构（main.py, config.py, database.py, 空 routers/services/repositories/models/schemas/middleware/utils 包）
- [x] **T0.4** frontend：搬入现有 React 前端（从 `apps/web/src/client` 提取），适配为独立 Vite 项目，保留 i18n（en/zh）
- [x] **T0.5** 创建 `.env.example`、`Makefile`、`README.md`
- [x] **T0.6** 创建 `docker/Dockerfile`（多阶段）和 `docker-compose.yml`

---

## Phase 1：数据库与配置

- [x] **T1.1** 实现 `app/config.py`：Pydantic Settings，支持 DATABASE_TYPE 切换
- [x] **T1.2** 实现 `app/database.py`：根据 DATABASE_TYPE 创建 SQLAlchemy engine/session（同步/异步按需）
- [x] **T1.3** 实现 ORM 模型：`users`, `sessions`, `skills`, `skill_versions`, `reviews`, `media`
- [x] **T1.4** 初始化 Alembic，生成初始迁移（同时兼容 SQLite + PostgreSQL）
- [x] **T1.5** 编写双数据库 pytest fixture（`conftest.py`），验证迁移可在两种 DB 上执行

---

## Phase 2：认证与会话

- [x] **T2.1** 实现 `app/utils/password.py`：Argon2id hash/verify
- [x] **T2.2** 实现 `app/repositories/session_repo.py`：Session CRUD、过期清理
- [x] **T2.3** 实现 `app/repositories/user_repo.py`：用户 CRUD、大小写不敏感查询
- [x] **T2.4** 实现 `app/services/auth_service.py`：login、logout、get_current_user、change_password
- [x] **T2.5** 实现 `app/middleware/session_auth.py`：从 Cookie 提取 session、验证、注入当前用户
- [x] **T2.6** 实现 `app/middleware/csrf.py`：写操作校验 X-CSRF-Token
- [x] **T2.7** 实现 `app/routers/auth.py`：login/logout/me/password 端点
- [x] **T2.8** 实现 `app/routers/bootstrap.py`：GET bootstrap + POST init（首用户创建）
- [x] **T2.9** 编写认证集成测试：登录/登出/session 过期/CSRF 拒绝/禁用用户立即失效

---

## Phase 3：管理员与用户管理

- [x] **T3.1** 实现 `app/services/user_service.py`：创建用户、修改角色、启用/禁用、删除、保护最后一个 admin
- [x] **T3.2** 实现 `app/routers/admin.py`：用户 CRUD 端点 + stats
- [x] **T3.3** 编写管理员测试：角色修改、最后 admin 保护、禁用后 session 失效

---

## Phase 4：技能 CRUD 与版本

- [x] **T4.1** 实现 `app/utils/skill_name.py`：技能名验证（`/^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/`）、slugify
- [x] **T4.2** 实现 `app/services/skill_workspace.py`：文件系统工作区管理（创建目录、读写 SKILL.md、frontmatter↔DB 同步、版本快照）
- [x] **T4.3** 实现 `app/repositories/skill_repo.py`：skills + skill_versions 数据访问
- [x] **T4.4** 实现 `app/services/skill_service.py`：CRUD、版本创建、所有权校验
- [x] **T4.5** 实现 `app/routers/skills.py`：全部端点（list/create/get/update/delete/content/versions）
- [x] **T4.6** 编写技能 CRUD 集成测试：创建/读取/更新/删除/版本快照/按用户唯一约束

---

## Phase 5：全文搜索

- [x] **T5.1** 实现 `app/repositories/search/base.py`：SearchRepository 抽象接口
- [x] **T5.2** 实现 `app/repositories/search/sqlite_fts.py`：FTS5 虚拟表 + 触发器 + search 方法
- [x] **T5.3** 实现 `app/repositories/search/pg_tsvector.py`：tsvector 列 + GIN 索引 + search 方法
- [x] **T5.4** Alembic 迁移：分别添加 FTS5 虚拟表（SQLite）和 tsvector 列+索引（PostgreSQL）
- [x] **T5.5** 编写搜索契约测试：精确/部分/特殊字符/空查询/可见性过滤（双数据库参数化）

---

## Phase 6：审核与公开目录

- [x] **T6.1** 实现 `app/repositories/review_repo.py`：审核记录数据访问
- [x] **T6.2** 实现 `app/services/review_service.py`：提交审核、批准（private→public）、驳回（→private）、下架（public→private）
- [x] **T6.3** 实现 `app/routers/skillhub.py`：公开目录列表/详情/下载（ZIP）
- [x] **T6.4** 实现 `app/routers/admin.py` 审核端点扩展：待审列表/批准/驳回
- [x] **T6.5** 实现 skills 路由中 `POST /:id/submit` 提交审核
- [x] **T6.6** 编写审核流测试：提交→批准→公开/提交→驳回→私有/下架/重新提交

---

## Phase 7：导入导出

- [x] **T7.1** 实现 `app/services/import_export_service.py`：ZIP 打包导出、ZIP 导入（含 zip slip 防护、符号链接拒绝、大小限制）
- [x] **T7.2** 实现 `app/routers/import_export.py`：POST import + GET export
- [x] **T7.3** 编写导入导出测试：正常包/路径穿越/超大文件/损坏 ZIP/符号链接

---

## Phase 8：媒体上传

- [x] **T8.1** 实现 `app/repositories/media_repo.py`：媒体记录数据访问
- [x] **T8.2** 实现 `app/services/media_service.py`：上传验证（类型/大小）、存储到 `media/` 目录
- [x] **T8.3** 实现 `app/routers/media.py`：上传/获取/删除
- [x] **T8.4** 编写媒体测试：正常上传/类型拒绝/大小超限/路径穿越文件名

---

## Phase 9：前端适配

- [x] **T9.1** 重写 `frontend/src/api/`：新 API 客户端层对接 `/api/v1/*`
- [x] **T9.2** 重写 `AuthContext`：改为 Session Cookie + CSRF token 内存管理
- [x] **T9.3** 添加首启引导页面（Bootstrap Page）
- [x] **T9.4** 适配技能管理页面对接新 skills/skillhub/import-export API
- [x] **T9.5** 适配管理员页面对接新 admin API
- [x] **T9.6** 移除 sync/devices/ai 相关页面和组件
- [x] **T9.7** 验证 en/zh 翻译完整性

---

## Phase 10：安全加固与集成

- [x] **T10.1** 实现 `app/middleware/security_headers.py`：HSTS、X-Content-Type-Options、X-Frame-Options 等
- [x] **T10.2** 静态文件托管：FastAPI mount 前端 dist 目录 + SPA fallback
- [x] **T10.3** Session 过期清理定时任务（后台 asyncio task 或启动时惰性清理）
- [x] **T10.4** 健康检查端点 `GET /api/v1/health`
- [x] **T10.5** 端到端冒烟测试：Docker 构建 → 启动 → bootstrap → 登录 → 创建技能 → 搜索 → 导出

---

## Phase 11：文档与发布准备

- [x] **T11.1** 编写 README.md：项目介绍、快速开始、配置项、部署指南
- [x] **T11.2** 编写 CONTRIBUTING.md：开发环境搭建、测试运行、代码规范
- [x] **T11.3** 添加 GitHub Actions CI：lint + 双数据库测试 + Docker 构建验证
- [x] **T11.4** 最终验证：全量测试通过 + Docker 部署验证 + 双数据库切换验证
