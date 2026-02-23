"""用户认证 API — 注册、登录、获取当前用户"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token, get_current_user, get_client_ip
from app.models.models import User
from app.services.audit import log_action

router = APIRouter()


@router.post("/register")
async def register(username: str, password: str, full_name: str = "", request: Request = None, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = User(
        username=username,
        hashed_password=get_password_hash(password),
        full_name=full_name,
    )
    db.add(user)

    await log_action(db, action="register", resource_type="user",
                   user_id=user.id, username=username,
                   ip_address=get_client_ip(request) if request else None)

    await db.commit()
    await db.refresh(user)

    token = create_access_token({"sub": user.id, "username": user.username, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "user": {
        "id": user.id, "username": user.username, "full_name": user.full_name, "role": user.role
    }}


@router.post("/login")
async def login(username: str, password: str, request: Request = None, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用")

    await log_action(db, action="login", resource_type="user",
                   user_id=user.id, username=username,
                   ip_address=get_client_ip(request) if request else None)
    await db.commit()

    token = create_access_token({"sub": user.id, "username": user.username, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "user": {
        "id": user.id, "username": user.username, "full_name": user.full_name, "role": user.role
    }}


@router.get("/me")
async def get_me(current_user=Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="未登录")
    return current_user
