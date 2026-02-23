"""审计日志服务 — 记录用户操作"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import AuditLog

logger = logging.getLogger(__name__)


async def log_action(
    db: AsyncSession,
    action: str,
    resource_type: str = None,
    resource_id: str = None,
    user_id: str = None,
    username: str = None,
    details: Dict[str, Any] = None,
    ip_address: str = None,
):
    """记录一条审计日志"""
    try:
        entry = AuditLog(
            user_id=user_id,
            username=username,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
        )
        db.add(entry)
        # 不单独commit，跟随调用方的事务
    except Exception as e:
        logger.error(f"审计日志写入失败: {e}")
