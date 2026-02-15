from typing import Annotated, List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import User
from schemas import UserResponse, CreateUser
from security import get_password_hash, get_current_user

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/", response_model=UserResponse)
async def add_user(user: CreateUser, db: AsyncSession = Depends(get_db)):
    hashed_password = get_password_hash(user.password)

    db_user = User(name=user.name, age=user.age, hashed_password=hashed_password)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user

@router.get("/all", response_model=List[UserResponse])
async def read_users_all(current_user: Annotated[User, Depends(get_current_user)], db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User))
    return result.scalars().all()