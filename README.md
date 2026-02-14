# 🔍 电子招投标串标围标自动分析系统

基于 AI 的招投标异常行为（串标/围标）自动检测与预警平台。

## 功能概览

### Phase 1 — 核心检测引擎
- ✅ 智能文档解析 — PDF / DOCX 全量提取（文本、元数据、格式、嵌入图片）
- ✅ 文本相似度检测 — SimHash + TF-IDF 余弦相似度
- ✅ 元数据比对 — 作者、软件版本、时间戳异常分析
- ✅ 格式指纹 — 字体、页边距、排版一致性检测

### Phase 2 — 深度分析 + 可视化
- ✅ 实体交叉检测 — 公司名/电话/邮箱/人名跨标书混名检测
- ✅ 错误模式识别 — 共性错别字、过期标准引用、标点异常
- ✅ 报价分析 — 等差/等比数列、固定系数、价格围堵、分项构成比对
- ✅ 综合风险评分 — 多维度加权评分 + 风险等级分类
- ✅ React 可视化仪表盘 — 总览看板、项目管理、分析详情、风险预警
- ✅ 报告导出 — Excel / PDF 分析报告

## 部署到 Railway（推荐）

### 前置条件
- GitHub 账号
- [Railway](https://railway.app) 账号

### 步骤

**1. 推送到 GitHub**
```bash
git init
git add .
git commit -m "init: 串标围标分析系统 Phase 1+2"
git remote add origin https://github.com/<your-username>/bid-analysis-system.git
git branch -M main
git push -u origin main
```

**2. 在 Railway 创建项目**
1. 登录 [railway.app](https://railway.app)
2. 点击 **"New Project"** → **"Deploy from GitHub Repo"**
3. 选择 `bid-analysis-system` 仓库
4. Railway 会自动检测到 `Dockerfile` 并开始构建

**3. 添加 PostgreSQL 数据库**
1. 在项目中点击 **"+ New"** → **"Database"** → **"PostgreSQL"**
2. PostgreSQL 创建后，点击它 → **"Connect"** → 复制 `DATABASE_URL`
3. 回到你的服务 → **"Variables"** → 添加：

| 变量 | 值 | 说明 |
|------|------|------|
| `DATABASE_URL` | `postgresql://...`（从 PostgreSQL 服务复制） | 数据库连接 |
| `SECRET_KEY` | （随机生成一个长字符串） | JWT 签名密钥 |
| `PORT` | `8000` | 服务端口 |

**4. 部署完成**
- Railway 会自动构建并部署
- 点击生成的域名即可访问系统
- API 文档：`https://<your-domain>/docs`
- 前端应用：`https://<your-domain>/app`

### 后续更新
```bash
git add .
git commit -m "update: xxx"
git push
# Railway 自动重新部署
```

## 本地开发

### Docker Compose（推荐）
```bash
docker-compose up -d
# API: http://localhost:8000/docs
# 前端: http://localhost:8000/app
```

### 手动启动
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
# 本地使用 SQLite，无需配置数据库
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/projects/` | 创建项目 |
| GET | `/api/v1/projects/` | 项目列表 |
| POST | `/api/v1/documents/upload` | 上传标书 |
| POST | `/api/v1/analysis/run/{id}` | 执行分析 |
| GET | `/api/v1/analysis/results/{id}` | 分析结果 |
| GET | `/api/v1/risk/dashboard` | 风险总览 |
| GET | `/api/v1/risk/alerts/{id}` | 风险预警 |
| GET | `/api/v1/report/excel/{id}` | 导出 Excel 报告 |
| GET | `/api/v1/report/pdf/{id}` | 导出 PDF 报告 |

## 技术栈

- **后端**: FastAPI + SQLAlchemy (async) + PyMuPDF + python-docx
- **前端**: React (单文件 SPA) + Recharts
- **数据库**: PostgreSQL (生产) / SQLite (本地开发)
- **报告**: openpyxl (Excel) + reportlab (PDF)
- **部署**: Railway + Docker

## 目录结构

```
bid-analysis-system/
├── Dockerfile                 # Railway 构建用
├── railway.toml              # Railway 配置
├── docker-compose.yml        # 本地 Docker 开发
├── Procfile                  # 备选部署方式
├── frontend/
│   └── index.html            # React SPA 前端
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py           # FastAPI 入口
│   │   ├── core/             # 配置、数据库、安全
│   │   ├── api/v1/           # API 路由
│   │   │   ├── projects.py   # 项目管理
│   │   │   ├── documents.py  # 文档管理
│   │   │   ├── analysis.py   # 检测分析
│   │   │   ├── risk.py       # 风险预警
│   │   │   └── report.py     # 报告导出
│   │   ├── models/           # ORM 模型
│   │   ├── schemas/          # Pydantic 校验
│   │   ├── services/
│   │   │   ├── parsing/      # PDF/DOCX 解析引擎
│   │   │   ├── detection/    # 6大检测引擎
│   │   │   ├── risk/         # 风险评分引擎
│   │   │   └── report/       # 报告生成器
│   │   └── utils/            # 工具函数
│   └── tests/                # 测试用例
```

## License

Private - Internal Use Only
