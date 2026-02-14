"""项目管理 API"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.core.database import get_db
from app.models.models import Project, Document, ProjectStatus
from app.schemas.schemas import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse

router = APIRouter()


@router.post("/", response_model=ProjectResponse)
async def create_project(data: ProjectCreate, db: AsyncSession = Depends(get_db)):
    """创建招标项目"""
    project = Project(
        name=data.name,
        project_code=data.project_code,
        description=data.description,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    return ProjectResponse(
        **{c.name: getattr(project, c.name) for c in project.__table__.columns},
        document_count=0
    )


@router.get("/", response_model=ProjectListResponse)
async def list_projects(
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取项目列表"""
    query = select(Project).order_by(Project.created_at.desc())
    if status:
        query = query.where(Project.status == status)

    # Count
    count_query = select(func.count()).select_from(Project)
    if status:
        count_query = count_query.where(Project.status == status)
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    projects = result.scalars().all()

    items = []
    for p in projects:
        doc_count_q = select(func.count()).select_from(Document).where(Document.project_id == p.id)
        doc_count = (await db.execute(doc_count_q)).scalar() or 0
        items.append(ProjectResponse(
            **{c.name: getattr(p, c.name) for c in p.__table__.columns},
            document_count=doc_count
        ))

    return ProjectListResponse(total=total, items=items)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """获取项目详情"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    doc_count_q = select(func.count()).select_from(Document).where(Document.project_id == project_id)
    doc_count = (await db.execute(doc_count_q)).scalar() or 0

    return ProjectResponse(
        **{c.name: getattr(project, c.name) for c in project.__table__.columns},
        document_count=doc_count
    )


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: str, data: ProjectUpdate, db: AsyncSession = Depends(get_db)):
    """更新项目"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)

    await db.commit()
    await db.refresh(project)

    doc_count_q = select(func.count()).select_from(Document).where(Document.project_id == project_id)
    doc_count = (await db.execute(doc_count_q)).scalar() or 0

    return ProjectResponse(
        **{c.name: getattr(project, c.name) for c in project.__table__.columns},
        document_count=doc_count
    )


@router.delete("/{project_id}")
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """删除项目"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    await db.delete(project)
    await db.commit()
    return {"message": "项目已删除", "id": project_id}
