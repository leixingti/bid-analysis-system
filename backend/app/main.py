"""招投标串标围标自动分析系统 - FastAPI 入口 v2.3"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.v1 import documents, analysis, risk, projects, report, auth, audit
from app.core.config import settings
from app.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    print(f"✅ {settings.APP_NAME} v{settings.APP_VERSION} started")
    yield
    print("👋 Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## 电子招投标串标围标自动分析系统 API v2.3

### 功能模块
- **用户认证**: 注册/登录/JWT鉴权/RBAC角色权限
- **项目管理**: 创建/搜索/批量删除/管理招标项目
- **文档上传**: 上传投标文件(PDF/DOCX)，自动解析+重试，支持文档预览
- **智能分析**: 七维度异步检测，实时进度追踪，可配置检测参数
- **分析历史**: 版本化分析记录，支持历史对比
- **风险预警**: 综合评分与风险等级判定
- **报告导出**: Excel/PDF分析报告（含完整检测详情）
- **审计日志**: 操作日志记录与查询
    """,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
app.include_router(auth.router,      prefix="/api/v1/auth",      tags=["用户认证"])
app.include_router(projects.router,  prefix="/api/v1/projects",  tags=["项目管理"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["文档管理"])
app.include_router(analysis.router,  prefix="/api/v1/analysis",  tags=["检测分析"])
app.include_router(risk.router,      prefix="/api/v1/risk",      tags=["风险预警"])
app.include_router(report.router,    prefix="/api/v1/report",    tags=["报告导出"])
app.include_router(audit.router,     prefix="/api/v1/audit",     tags=["审计日志"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION, "service": settings.APP_NAME}


@app.get("/")
async def root():
    return {
        "message": f"欢迎使用{settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
        "app": "/app",
    }


# Serve frontend
import os
frontend_candidates = [
    "/frontend",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "..", "frontend"),
]
for fdir in frontend_candidates:
    fdir = os.path.abspath(fdir)
    if os.path.isdir(fdir) and os.path.exists(os.path.join(fdir, "index.html")):
        app.mount("/app", StaticFiles(directory=fdir, html=True), name="frontend")
        print(f"📂 Frontend served from {fdir}")
        break
