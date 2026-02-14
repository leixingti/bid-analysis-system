# 招投标串标围标自动分析系统 — 项目文档

> **用途**：每次与 AI 助手新对话时，上传此文件即可完整恢复项目上下文，无需重复说明。

---

## 1. 基本信息

| 项目 | 值 |
|------|------|
| **名称** | 招投标串标围标自动分析系统 (Bid Collusion Detection System) |
| **版本** | v2.1.0 |
| **GitHub** | `https://github.com/[你的用户名]/bid-analysis-system` |
| **线上地址** | `https://web-production-17e69.up.railway.app/app/` |
| **API 文档** | `https://web-production-17e69.up.railway.app/docs` |
| **部署平台** | Railway (自动部署，push 到 main 分支即触发) |

---

## 2. 技术栈

| 层 | 技术 |
|----|------|
| **后端** | Python 3.10 + FastAPI + SQLAlchemy (async) + asyncpg |
| **数据库** | PostgreSQL (Railway 托管) |
| **前端** | 单文件 React SPA (`frontend/index.html`)，CDN 引入 React 18.2 + Recharts + Babel |
| **认证** | JWT (python-jose) + bcrypt 密码哈希 |
| **文件解析** | PyMuPDF (PDF) + python-docx (DOCX) |
| **报告导出** | openpyxl (Excel) + reportlab (PDF) |
| **容器** | Docker (python:3.10-slim) |

---

## 3. 项目结构

```
bid-analysis-system/
├── Dockerfile                  # 生产 Docker 镜像
├── railway.toml                # Railway 部署配置
├── Procfile                    # 备用启动配置
├── docker-compose.yml          # 本地开发
├── PROJECT.md                  # 本文件（项目记忆）
│
├── backend/
│   ├── requirements.txt        # Python 依赖
│   └── app/
│       ├── main.py             # FastAPI 入口 + 路由注册 + 前端挂载
│       ├── core/
│       │   ├── config.py       # Settings (环境变量)
│       │   ├── database.py     # SQLAlchemy async engine + init_db()
│       │   └── security.py     # JWT + bcrypt 密码工具
│       ├── models/
│       │   └── models.py       # Project / Document / AnalysisResult 模型
│       ├── schemas/
│       │   └── schemas.py      # Pydantic 请求/响应模型
│       ├── api/v1/
│       │   ├── auth.py         # 注册/登录/JWT
│       │   ├── projects.py     # 项目 CRUD
│       │   ├── documents.py    # 文件上传/解析/查询
│       │   ├── analysis.py     # 检测分析执行/结果查询
│       │   ├── risk.py         # 风险看板/预警列表
│       │   └── report.py       # Excel/PDF 报告导出
│       ├── services/
│       │   ├── detection/      # 6 大检测引擎
│       │   │   ├── content_similarity.py  # SimHash + TF-IDF 文本相似度
│       │   │   ├── metadata_detector.py   # 元数据关联检测
│       │   │   ├── format_detector.py     # 格式指纹比对
│       │   │   ├── error_pattern.py       # 错别字/异常模式
│       │   │   ├── entity_cross.py        # 实体交叉分析
│       │   │   └── price_analysis.py      # 报价梯度分析
│       │   ├── parsing/        # 文档解析器
│       │   │   ├── pdf_parser.py
│       │   │   └── docx_parser.py
│       │   ├── report/         # 报告生成
│       │   │   ├── excel_report.py
│       │   │   └── pdf_report.py
│       │   └── risk/           # 风险评分引擎
│       │       └── risk_engine.py
│       └── utils/
│           ├── hash.py         # MD5 计算
│           └── desensitize.py  # 数据脱敏
│
└── frontend/
    └── index.html              # 完整 React SPA (39KB)
```

---

## 4. Railway 配置

### 环境变量 (web 服务)

| 变量名 | 值 |
|--------|------|
| `DATABASE_URL` | `postgresql://postgres:AWGfXVdezeTXmfudPmaxYzMKJlmqsMsX@switchyard.proxy.rlwy.net:54084/railway` |
| `SECRET_KEY` | `x9k2m7p4v8b1n5c3z6a0w4r7t2e9y1u6h3j8f5` |

> **注意**：使用外网地址 `switchyard.proxy.rlwy.net:54084`，不要用内网地址 `postgres.railway.internal:5432`（会 DNS 解析失败）。

### Railway 服务
- **web**: GitHub 自动部署，Dockerfile 构建，health check `/health`
- **PostgreSQL**: Railway 托管数据库，自动提供 8 个内置变量

---

## 5. API 端点

| 模块 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 认证 | POST | `/api/v1/auth/register` | 用户注册 |
| 认证 | POST | `/api/v1/auth/login` | 用户登录 |
| 认证 | GET  | `/api/v1/auth/me` | 获取当前用户 |
| 项目 | GET  | `/api/v1/projects/` | 项目列表 |
| 项目 | POST | `/api/v1/projects/` | 创建项目 |
| 项目 | GET  | `/api/v1/projects/{id}` | 项目详情 |
| 项目 | PUT  | `/api/v1/projects/{id}` | 更新项目 |
| 项目 | DELETE | `/api/v1/projects/{id}` | 删除项目 |
| 文档 | POST | `/api/v1/documents/upload/{project_id}` | 上传文件 |
| 文档 | GET  | `/api/v1/documents/{project_id}` | 文档列表 |
| 文档 | GET  | `/api/v1/documents/detail/{doc_id}` | 文档详情 |
| 分析 | POST | `/api/v1/analysis/run/{project_id}` | 执行检测 |
| 分析 | GET  | `/api/v1/analysis/results/{project_id}` | 检测结果 |
| 风险 | GET  | `/api/v1/risk/dashboard` | 风险总览 |
| 风险 | GET  | `/api/v1/risk/alerts` | 预警列表 |
| 报告 | GET  | `/api/v1/report/excel/{project_id}` | 导出 Excel |
| 报告 | GET  | `/api/v1/report/pdf/{project_id}` | 导出 PDF |
| 系统 | GET  | `/health` | 健康检查 |
| 系统 | GET  | `/docs` | Swagger API 文档 |

---

## 6. 前端页面

| 页面 | 功能 |
|------|------|
| **LoginPage** | 用户登录/注册，JWT token 存 localStorage |
| **Dashboard** (总览看板) | 风险概览、项目统计、风险分布图 |
| **ProjectsPage** (项目管理) | 项目 CRUD，列表展示 |
| **AnalysisPage** (分析详情) | 文件上传、执行分析、结果展示（相似度矩阵、元数据比对等） |
| **AlertsPage** (风险预警) | 预警列表、风险等级过滤 |

---

## 7. 数据库模型

### projects
```
id (UUID PK), name, project_code, description, status, risk_score, risk_level, created_at, updated_at
```

### documents
```
id (UUID PK), project_id (FK), company_name, file_name, file_path, file_type, file_size, file_hash,
meta_author, meta_company, meta_last_modified_by, meta_created_time, meta_modified_time,
meta_producer, meta_creator, meta_software_version, meta_extra (JSON),
full_text, text_length, page_count, fonts_used (JSON), format_info (JSON),
parsed (0/1/2), created_at
```

### analysis_results
```
id (UUID PK), project_id (FK), analysis_type, doc_id_a (FK), doc_id_b (FK),
company_a, company_b, score, risk_level, summary, details (JSON), created_at
```

### users (v2.1 新增)
```
id (UUID PK), username, hashed_password, full_name, role, is_active, created_at
```

---

## 8. 已知问题 & 待修复

| # | 问题 | 状态 | 说明 |
|---|------|------|------|
| 1 | `security.py` 用 passlib+bcrypt | ⚠️ 待确认 | bcrypt 4.x 与 passlib 不兼容，需替换为直接用 bcrypt |
| 2 | `main.py` 缺少 auth 路由导入 | ⚠️ 待确认 | 当前 import 行可能没有 `auth`，需要加上 |
| 3 | 文件存储使用容器本地 `/app/uploads` | ⚠️ 已知限制 | 容器重启后文件丢失，需迁移到 S3/R2 对象存储 |
| 4 | `documents.py` 的 DocumentResponse | ✅ 已修复 | 已创建 `_doc_to_response()` 辅助函数避免 fonts_used 重复 |

---

## 9. 后续开发计划

### Phase 2 — 进行中
- [ ] 修复 security.py bcrypt 兼容性
- [ ] 确认 auth 路由正确注册
- [ ] 文件上传 + 解析完整流程验证
- [ ] 执行分析 + 风险评分验证

### Phase 3 — 计划
- [ ] S3/R2 持久化文件存储
- [ ] 用户权限管理 (admin/analyst/viewer)
- [ ] AI 增强分析 (LLM 辅助判断)
- [ ] 分析历史对比
- [ ] 导出报告优化（更专业的 PDF 排版）

### Phase 4 — 远期
- [ ] 多项目对比分析
- [ ] 投标人画像 / 关系图谱
- [ ] 自动监控 + 邮件通知
- [ ] 移动端适配

---

## 10. 开发工作流

### 日常修改
```bash
# 1. 在本地编辑文件
# 2. 提交到 GitHub
git add .
git commit -m "描述修改内容"
git push origin main
# 3. Railway 自动构建部署（约 1-2 分钟）
```

### 新对话恢复上下文
1. 上传本文件 `PROJECT.md`
2. 描述当前问题或需求
3. AI 即可无缝继续开发

### 本地开发（可选）
```bash
cd bid-analysis-system
pip install -r backend/requirements.txt
# 设置环境变量
export DATABASE_URL="sqlite+aiosqlite:///./bid_analysis.db"
export SECRET_KEY="dev-secret-key"
# 启动
cd backend
uvicorn app.main:app --reload --port 8000
```

---

## 11. 重要文件修改记录

| 日期 | 文件 | 修改 |
|------|------|------|
| 2025-02-14 | `core/database.py` | 添加 Railway 外网 URL 支持 + SSL disable |
| 2025-02-14 | `core/security.py` | 需要替换：passlib → 直接用 bcrypt |
| 2025-02-14 | `api/v1/documents.py` | 修复 DocumentResponse fonts_used 重复参数 |
| 2025-02-14 | `api/v1/auth.py` | 新增用户注册/登录/JWT 端点 |
| 2025-02-14 | `models/models.py` | 新增 User 模型 |
| 2025-02-14 | `frontend/index.html` | 添加登录页、Recharts CDN 修复 |

---

*最后更新: 2026-02-14*
