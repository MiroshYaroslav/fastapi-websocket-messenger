from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Message, User
from security import get_current_user
from services.websockets import manager

router = APIRouter(prefix="/ws", tags=["WebSocket"])


@router.websocket("/chat/{room_id}/{user_id}/{recipient_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: int,
    user_id: int,
    recipient_id: int,
    username: str,
    db: AsyncSession = Depends(get_db),
):
    await manager.connect(websocket, user_id, room_id)

    try:
        query = (
            select(Message)
            .where(Message.room_id == room_id)
            .order_by(Message.timestamp.desc())
            .limit(10)
        )
        result = await db.execute(query)
        history = result.scalars().all()[::-1]

        for msg in history:
            await websocket.send_json(
                {
                    "text": msg.content,
                    "is_self": msg.sender_id == user_id,
                    "author": username if msg.sender_id == user_id else "User",
                }
            )

        while True:
            data = await websocket.receive_json()
            text = data.get("text")

            if text:
                try:
                    new_msg = Message(room_id=room_id, sender_id=user_id, content=text)
                    db.add(new_msg)
                    await db.commit()
                except Exception as db_err:
                    await db.rollback()
                    print(f"DB Save Error: {db_err}")
                    continue

                await manager.broadcast(text, room_id, user_id)

                is_recipient_in_room = (
                    room_id in manager.active_connections
                    and recipient_id in manager.active_connections.get(room_id, {})
                )

                if not is_recipient_in_room:
                    notification = {
                        "type": "new_message",
                        "from_user_id": user_id,
                        "from_username": username,
                        "text": text,
                    }
                    await manager.broadcast_global(recipient_id, notification)

    except WebSocketDisconnect:
        manager.disconnect(user_id, room_id)
    except Exception as e:
        print(f"WebSocket ERROR: {e}")
        manager.disconnect(user_id, room_id)


@router.websocket("/notifications/{user_id}")
async def websocket_global_endpoint(websocket: WebSocket, user_id: int):
    await manager.connect_global(websocket, user_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect_global(user_id)
    except Exception as e:
        print(f"Global ERROR: {e}")
        await manager.disconnect_global(user_id)


@router.get("/online-users")
async def get_online_users():
    online_ids_str = await manager.redis_client.hkeys("online_users")
    return {"online_users": [int(uid) for uid in online_ids_str]}


@router.get("/history/{room_id}")
async def get_chat_history(
    room_id: int,
    offset: int = Query(0, description="How many messages to skip"),
    limit: int = Query(10, description="How many messages to download"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(Message)
        .where(Message.room_id == room_id)
        .order_by(Message.timestamp.desc())
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(query)
    history = result.scalars().all()[::-1]

    return [
        {
            "text": msg.content,
            "is_self": msg.sender_id == current_user.id,
            "author": current_user.name if msg.sender_id == current_user.id else "User",
        }
        for msg in history
    ]


@router.get("/unread")
async def get_unread_counts(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    uid = current_user.id

    query = (
        select(Message.sender_id, func.count(Message.id))
        .where(
            (Message.room_id // 100000 == uid) | (Message.room_id % 100000 == uid),
            Message.sender_id != uid,
            Message.is_read.is_(False),
        )
        .group_by(Message.sender_id)
    )

    result = await db.execute(query)
    counts = result.all()

    return {str(sender_id): count for sender_id, count in counts}


@router.post("/mark-read/{sender_id}")
async def mark_messages_as_read(
    sender_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room_id = min(int(current_user.id), sender_id) * 100000 + max(int(current_user.id), sender_id)  # type: ignore

    query = (
        update(Message)
        .where(
            Message.room_id == room_id, Message.sender_id == sender_id, Message.is_read.is_(False)
        )
        .values(is_read=True)
    )

    await db.execute(query)
    await db.commit()

    return {"status": "ok"}
