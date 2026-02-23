"""审计日志 API"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.core.database import get_db
from app.core.security import require_roles
from app.models.models import AuditLog
from app.schemas.schemas import AuditLogResponse, AuditLogListResponse

router = APIRouter()


@router.get("/", response_model=AuditLogListResponse)
async def list_audit_logs(
    skip: int = 0, limit: int = 50,
    action: Optional[str] = None,
    username: Optional[str] = None,
    resource_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles("admin", "auditor")),
):
    """查询审计日志（仅admin/auditor可访问）"""
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    count_query = select(func.count()).select_from(AuditLog)

    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)
    if username:
        query = query.where(AuditLog.username == username)
        count_query = count_query.where(AuditLog.username == username)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
        count_query = count_query.where(AuditLog.resource_type == resource_type)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(query.offset(skip).limit(limit))
    logs = result.scalars().all()

    return AuditLogListResponse(
        total=total,
        items=[AuditLogResponse(**{c.name: getattr(l, c.name) for c in l.__table__.columns}) for l in logs]
    )
