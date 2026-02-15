from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Post, User
from schemas import PostResponse, CreatePost
from security import get_current_user

router = APIRouter(prefix="/posts", tags=["Posts"])

@router.get("/", response_model=List[PostResponse])
async def get_posts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Post))
    return result.scalars().all()

@router.post("/", response_model=PostResponse)
async def add_post(
        post: CreatePost,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    if post.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only post as yourself")

    query = select(User).where(User.id == post.author_id)
    result = await db.execute(query)
    author = result.scalar_one_or_none()

    if author is None:
        raise HTTPException(status_code=400, detail="Author not found")

    db_post = Post(title=post.title, comment=post.comment, author_id=post.author_id)
    db.add(db_post)
    await db.commit()
    await db.refresh(db_post)
    return db_post

@router.get("/search/", response_model=List[PostResponse])
async def search_posts(query: Annotated[str, Query(..., min_length=1)], db: AsyncSession = Depends(get_db)):
    stmt = select(Post).filter(
        or_(
            Post.title.ilike(f"%{query}%"),
            Post.comment.ilike(f"%{query}%")
        )
    )
    result = await db.execute(stmt)
    posts = result.scalars().all()
    return posts