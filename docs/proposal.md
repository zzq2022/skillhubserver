# 提案：将 Web 后端整体迁移为独立的 Python 项目 skillhubserver

> 状态：盘问完成，待产出设计文档与任务清单
> 变更类型：跨仓库迁移 + 后端语言重写 + 存储与契约边界变更
> 关联技能：grill-with-docs

## 背景与动机

当前 `apps/web`（包名 `@prompthub/web`，v0.7.1）是一个**全栈**应用：

- 服务端：Hono（`src/index.ts` → `src/app.ts` → `routes/`、`services/`、`middleware/`），并负责托管打包后的前端 `dist/client`。
- 客户端：React 18 + TypeScript + Vite 的 SPA（`src/client`），通过 HTTP `fetch /api/*` 与服务端通信。
- 服务端强依赖三个 workspace 包：`@prompthub/core`、`@prompthub/db`、`@prompthub/shared`（`workspace:*`）。
- 数据真理源：SQLite（`node-sqlite3-wasm` + `@prompthub/db` schema，含 FTS5）＋ 技能文件工作区（`bootstrapSkillWorkspace`）。

用户希望把这套「服务端功能」整体迁出，落到一个**新的独立项目 skillhubserver**，并借机把后端语言换成 Python。

## 已确认的决策（盘问产出）

1. **迁移范围 = 整个 `apps/web` 后端**（A）：auth、skills、settings、ai、media、sync、import-export、devices、skillhub(public)、admin 全部迁走。`apps/web` 之后退化为纯前端壳或废弃。
2. **仓库形态 = 完全独立的新 Git 仓库**（B），自包含、不外链本 monorepo 的包。
3. **后端语言 = Python 重写（而非搬运 TS 代码）**。三个 TS 包（core/db/shared）仅作为业务行为、数据概念与边界参考，不复制 TS 实现。
4. **前端 = 沿用现技术栈**（React 18 / TypeScript / Vite），随迁进新仓库。
5. **skillhubserver 构成 = 前端 + Python 后端同仓**（甲）：React SPA + Python API 服务，共处一个仓库。
6. **数据策略 = 全新起步（greenfield）**：不迁移旧 SQLite 数据、用户账号、会话、设置或技能工作区文件。旧系统仅作为业务能力参考；新系统不承担旧密码哈希、JWT 会话、HTTP 接口或存储布局的兼容义务。
7. **Python Web 框架 = FastAPI**：采用类型化 HTTP API；暂定配套 Pydantic、SQLAlchemy 2 与 Alembic，最终数据库适配在后续决策中确认。
8. **主要部署模型 = 组织/个人自托管**：每个部署服务个人或小团队，优先单机/单容器、低运维和易备份；首版不以公共多租户 SaaS、横向扩展为设计目标。
9. **数据库 = SQLite 与 PostgreSQL 正式双支持**：通过配置文件选择数据库后端。SQLAlchemy 2 与 Alembic 必须覆盖两种方言；迁移、事务、约束、搜索及集成测试需建立双数据库矩阵。不得仅在 SQLite 上验证后宣称 PostgreSQL 兼容。
10. **全文搜索 = 数据库专用适配器**：在统一搜索契约后提供 SQLite FTS5 与 PostgreSQL `tsvector` 实现。共同契约覆盖查询安全、过滤和匹配集合等可观察行为；不承诺两端相关度分值或排序完全一致。
11. **API 策略 = 重新设计**：不要求兼容现有 `/api/*` 的路径、状态码、JSON 形状、Cookie/JWT 双通道或历史缺陷。保留业务能力并为新前端 API 层定义新契约。
12. **认证方向 = 简化为登录**：不移植现有验证码、access/refresh JWT 双令牌轮换及复杂兼容行为。
13. **账号模型 = 多账号、管理员创建**：首次初始化创建管理员；不开放自助注册。管理员可以创建、禁用普通账号。认证能力保留登录、登出、获取当前用户和修改密码；账号删除与角色细节仍待确认。
14. **会话机制 = 服务端 Session + HttpOnly Cookie**：浏览器仅持有随机 Session ID；Session 记录存入所选数据库。移除 JWT、refresh token、Bearer token及前端 token 内存管理。禁用用户、登出和管理员强制下线通过撤销 Session 立即生效。生产环境以前后端同源为默认，Cookie 使用 `HttpOnly`、`SameSite=Lax`，HTTPS 下启用 `Secure`；CSRF 防护方案待设计确认。
15. **角色模型 = `admin` / `user` 两级**：首个用户自动成为 `admin`，允许多个管理员。系统禁止删除、禁用或降级最后一个有效管理员，避免实例失去管理入口。
16. **技能可见性 = `private` / `public` 两级**：技能始终归属于一个用户。私有技能仅所有者与管理员可见；公开技能进入公开目录。系统不提供仅实例成员可见的 `internal` 层，因此普通用户之间共享未公开技能不属于首版能力。
17. **发布工作流 = 所有者提交、管理员审核**：技能发布状态机为 `private → pending_review → public`；管理员驳回回到 `private`，下架从 `public → private`；重新提交需再次进入 `pending_review`。保留提交记录与管理员审核能力。
18. **技能存储 = 文件系统工作区 + 数据库元数据（沿用现有实现）**：技能作为磁盘上的目录包存储（`SKILL.md` + 辅助文件 + `versions/` 版本目录），数据库存元数据索引。内容真理源为 `SKILL.md` 文件，元数据真理源为数据库（`name/description/version/tags/author/model` 等键），二者通过同步服务保持一致。**已知风险**：双真理源存在同步竞态，备份需同时快照数据库与文件卷；迁移时必须移植现有的 frontmatter↔DB 同步契约作为缓解，而非重新设计。
19. **首版能力范围**：
    - 保留：skills（CRUD + 版本）、skillhub 公开目录 + 审核、auth（简化登录/账号）、admin（用户管理 + 技能治理）、import-export（技能包导入/导出）、media（降级为技能/头像基础媒体，去除复杂远程抓取）。
    - 砍掉：ai（AI 供应商代理 / 技能安全扫描）、sync（WebDAV 多设备同步）、devices（设备管理）。
    - 产品后果：skillhubserver 不提供多设备同步、设备管理和 AI 安全扫描；桌面端如需对接改走新的 skills API。
20. **部署与打包 = 单容器、FastAPI 托管前端**：前端 Vite 构建产物注入后端镜像，运行期由 FastAPI 同源托管，API 与前端同端口，Session Cookie 同源无 CORS 复杂度。部署产物为一个镜像 + 一个挂载数据卷（数据库文件 + 技能工作区）。
21. **仓库目录布局 = 顶层 `backend/` + `frontend/`**：`backend/` 存放 Python/FastAPI 服务与 Alembic 迁移；`frontend/` 存放 React/Vite 应用；构建流程将 `frontend` 产物提供给 `backend` 镜像托管。
22. **CSRF 防护 = `SameSite=Lax` + 双提交 CSRF Token**：Session Cookie 使用 `SameSite=Lax`；登录后下发 CSRF token，前端在写操作（POST/PUT/DELETE）请求头回传，服务端校验；读操作不强制。
23. **技能名唯一性 = 按用户唯一**：同一用户内技能名不可重复；不同用户可拥有同名技能。公开目录以 `owner/name` 命名空间展示。
24. **版本模型 = 线性自增 + 快照保留**：每次发布产生递增版本号（`0001`、`0002`...），旧版本 SKILL.md 快照保留在 `versions/` 目录下只读查阅，首版不支持回滚为当前版本。
25. **import/export 包格式 = ZIP 归档**：技能目录→zip，导入解压到工作区。ZIP 内根目录即技能包，包含 `SKILL.md` 和辅助文件。Python `zipfile` 标准库处理。
26. **media 降级边界 = 仅本地上传**：移除远程 URL 抓取和 SSRF 相关逻辑。允许类型 JPEG/PNG/WebP/SVG，单文件上限 5MB，文件存数据卷 `media/` 子目录。
27. **国际化 = 保留 en + zh 双语**：前端 react-i18next 照搬现有翻译文件；后端 API 错误消息保持英文。
28. **Python 依赖管理与测试 = uv + pytest**：uv 管理虚拟环境和 lockfile（`uv.lock`）；pytest + pytest-asyncio 进行双数据库参数化测试矩阵。
29. **首次初始化 = 首启引导页面**：首次访问 Web 时若数据库无用户，展示创建管理员表单。表单提交后注册 admin、直接登录，此后不再出现；API 通过 `GET /api/bootstrap` 返回 `initialized` 状态控制前端路由。

## 关键风险（已整理）

- **双真理源同步竞态**：文件系统工作区与数据库元数据的一致性，必须移植 frontmatter↔DB 同步契约并建立写后验证测试。
- **双数据库测试矩阵**：SQLite + PostgreSQL 正式双支持要求所有迁移、事务、约束、搜索和集成测试跑双矩阵，不得偏科。
- **全文搜索适配器**：SQLite FTS5 与 PostgreSQL tsvector 的语义差异（分词、运算符、排序）需用契约测试覆盖共同行为。
- **前端 API 层全面改造**：API 重新设计意味着现有前端 `src/client/api/` 和 `AuthContext` 需要为新 Session 流和新 endpoint 重写。
- **Session 安全**：CSRF 双提交 token 的实现和 Session 过期/清理策略要在首版覆盖测试。
- **ZIP 导入安全**：路径穿越（zip slip）、符号链接、超大文件需要在导入时显式防护。
- **备份策略**：双真理源要求备份同时快照数据库文件和技能工作区文件卷。

- API 重设计：必须建立明确的新 OpenAPI 契约和前端 API 适配层，避免从旧实现随意复制不一致的接口。
- 简化认证：“简单登录”仍需明确单用户/多用户、首次初始化、会话形态、密码重置与管理员边界。
- 双数据库：SQLite FTS5 与 PostgreSQL `tsvector`、外键、事务和迁移必须通过双数据库契约测试验证。
- WebDAV 同步、媒体工作区、导入导出等文件系统副作用需要重新定义，而非默认等价移植。
- 部署形态（现有 Docker / docker-compose）需按 Python + React 同仓重新设计。

## 回滚考量

迁移期间旧 `apps/web` 保持可用；skillhubserver 作为独立仓库并行开发，切换前不影响现有部署。新项目全新起步且不迁移数据，回滚方式是继续使用旧部署，而不是把新数据反向导回旧系统。

## 决策日志

| # | 决策 | 选项 | 结论 |
| - | ---- | ---- | ---- |
| 1 | 迁移范围 | A 整个后端 / B 仅 SkillHub 子集 | **A** |
| 2 | 仓库形态 | A monorepo 内新包 / B 独立仓库 | **B** |
| 3 | 后端语言 | 搬运 TS / Python 重写 | **Python 重写** |
| 4 | 前端技术栈 | 沿用 React/TS/Vite / 换栈 | **沿用** |
| 5 | 仓库构成 | 甲 前后端同仓 / 乙 仅后端 | **甲 同仓** |
| 6 | 数据策略 | 甲 全新起步 / 乙 迁移存量 | **甲 全新起步** |
| 7 | Python Web 框架 | FastAPI / Django + DRF / Django Ninja | **FastAPI** |
| 8 | 主要部署模型 | 公共多租户 / 组织或个人自托管 / 双模式 | **组织/个人自托管** |
| 9 | 数据库支持 | SQLite / PostgreSQL / 正式双支持 | **SQLite + PostgreSQL，通过配置文件切换** |
| 10 | 全文搜索 | 普通文本查询 / 数据库专用适配器 / 独立搜索服务 | **SQLite FTS5 + PostgreSQL tsvector 适配器** |
| 11 | API 策略 | 严格兼容 / 兼容并修缺陷 / 重新设计 | **重新设计** |
| 12 | 认证复杂度 | 复刻现有认证 / 简单登录 | **简单登录** |
| 13 | 账号模型 | 单账号 / 管理员创建多账号 / 开放注册 | **多账号、管理员创建** |
| 14 | 会话机制 | 服务端 Session Cookie / 单 JWT / access + refresh JWT | **服务端 Session + HttpOnly Cookie** |
| 15 | 角色模型 | admin/user / 固定 Owner + user / Owner/Admin/User | **admin/user 两级，保护最后一个 admin** |
| 16 | 技能可见性 | 全员共享 / private-internal-public / private-public | **private / public 两级** |
| 17 | 发布工作流 | 所有者直接公开 / 提交+管理员审核 / 仅管理员公开 | **所有者提交、管理员审核** |
| 18 | 技能存储 | 甲 文件系统+DB元数据 / 乙 DB单一真理源 / 丙 对象存储 | **甲 文件系统工作区 + DB 元数据（沿用现有）** |
| 19 | 首版能力范围 | 全量迁移 / 精简 | **留 skills·skillhub·auth·admin·import-export·media(降级)；砍 ai·sync·devices** |
| 20 | 部署与打包 | 甲 单容器FastAPI托管前端 / 乙 双容器Nginx / 丙 前端独立部署 | **甲 单容器、FastAPI 托管前端** |
| 21 | 仓库目录布局 | backend/ + frontend/ 顶层分离 | **顶层 backend/ 与 frontend/** |
| 22 | CSRF 防护 | 甲 仅 SameSite=Lax / 乙 Lax+双提交Token / 丙 SameSite=Strict | **乙 SameSite=Lax + 双提交 CSRF Token** |
| 23 | 技能名唯一性 | 按用户唯一 / 全局唯一 | **按用户唯一** |
| 24 | 版本模型 | 线性自增+快照 / 可回滚 / SemVer | **线性自增 + 快照保留（只读历史）** |
| 25 | import/export 格式 | ZIP / tar.gz / 自定义 | **ZIP 归档** |
| 26 | media 边界 | 仅本地上传 / 保留远程抓取+白名单 | **仅本地上传（移除远程抓取/SSRF）** |
| 27 | 国际化 | en+zh 双语 / 仅英文 / 仅中文 | **保留 en + zh 双语** |
| 28 | Python 依赖与测试 | uv+pytest / Poetry+pytest / pip+pytest | **uv + pytest** |
| 29 | 首次初始化 | 首启引导页面 / 环境变量预设 / CLI 命令 | **首启引导页面** |
