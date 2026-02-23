"""项目管理 API — 搜索 + 批量操作 + 审计"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import Optional

from app.core.database import get_db
from app.core.security import require_auth, require_roles, get_client_ip
from app.models.models import Project, Document, ProjectStatus
from app.schemas.schemas import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse, BatchDeleteRequest
from app.services.audit import log_action

router = APIRouter()


@router.post("/", response_model=ProjectResponse)
async def create_project(
    data: ProjectCreate, request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_auth),
):
    project = Project(
        name=data.name, project_code=data.project_code, description=data.description,
        created_by=current_user.get("sub"),
    )
    db.add(project)

    await log_action(db, action="create_project", resource_type="project",
                   user_id=current_user.get("sub"), username=current_user.get("username"),
                   details={"name": data.name, "code": data.project_code},
                   ip_address=get_client_ip(request) if request else None)

    await db.commit()
    await db.refresh(project)
    return ProjectResponse(**{c.name: getattr(project, c.name) for c in project.__table__.columns}, document_count=0)


@router.get("/", response_model=ProjectListResponse)
async def list_projects(
    skip: int = 0, limit: int = 20,
    status: Optional[str] = None,
    search: Optional[str] = None,
    risk_level: Optional[str] = None,
    sort_by: Optional[str] = "created_at",
    sort_order: Optional[str] = "desc",
    db: AsyncSession = Depends(get_db),
):
    """获取项目列表（支持搜索/筛选/排序）"""
    query = select(Project)
    count_query = select(func.count()).select_from(Project)

    if status:
        query = query.where(Project.status == status)
        count_query = count_query.where(Project.status == status)
    if risk_level:
        query = query.where(Project.risk_level == risk_level)
        count_query = count_query.where(Project.risk_level == risk_level)
    if search:
        search_filter = or_(
            Project.name.ilike(f"%{search}%"),
            Project.project_code.ilike(f"%{search}%"),
            Project.description.ilike(f"%{search}%"),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    # 排序
    sort_col = getattr(Project, sort_by, Project.created_at)
    query = query.order_by(sort_col.desc() if sort_order == "desc" else sort_col.asc())

    total = (await db.execute(count_query)).scalar() or 0
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    projects = result.scalars().all()

    items = []
    for p in projects:
        doc_count = (await db.execute(
            select(func.count()).select_from(Document).where(Document.project_id == p.id)
        )).scalar() or 0
        items.append(ProjectResponse(
            **{c.name: getattr(p, c.name) for c in p.__table__.columns}, document_count=doc_count
        ))

    return ProjectListResponse(total=total, items=items)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    doc_count = (await db.execute(
        select(func.count()).select_from(Document).where(Document.project_id == project_id)
    )).scalar() or 0
    return ProjectResponse(**{c.name: getattr(project, c.name) for c in project.__table__.columns}, document_count=doc_count)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: str, data: ProjectUpdate, db: AsyncSession = Depends(get_db), current_user=Depends(require_auth)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    doc_count = (await db.execute(
        select(func.count()).select_from(Document).where(Document.project_id == project_id)
    )).scalar() or 0
    return ProjectResponse(**{c.name: getattr(project, c.name) for c in project.__table__.columns}, document_count=doc_count)


@router.delete("/{project_id}")
async def delete_project(project_id: str, request: Request = None, db: AsyncSession = Depends(get_db), current_user=Depends(require_auth)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    await log_action(db, action="delete_project", resource_type="project", resource_id=project_id,
                   user_id=current_user.get("sub"), username=current_user.get("username"),
                   details={"name": project.name},
                   ip_address=get_client_ip(request) if request else None)

    await db.delete(project)
    await db.commit()
    return {"message": "项目已删除", "id": project_id}


@router.post("/batch-delete")
async def batch_delete_projects(
    data: BatchDeleteRequest, request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles("admin", "analyst")),
):
    """批量删除项目"""
    deleted = 0
    for pid in data.project_ids:
        result = await db.execute(select(Project).where(Project.id == pid))
        project = result.scalar_one_or_none()
        if project:
            await db.delete(project)
            deleted += 1

    await log_action(db, action="batch_delete", resource_type="project",
                   user_id=current_user.get("sub"), username=current_user.get("username"),
                   details={"count": deleted, "ids": data.project_ids},
                   ip_address=get_client_ip(request) if request else None)

    await db.commit()
    return {"message": f"已删除 {deleted} 个项目", "deleted": deleted}
