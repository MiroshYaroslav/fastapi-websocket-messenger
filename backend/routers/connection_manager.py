import json
import os
import redis.asyncio as redis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict
from database import get_db
from models import Message

REDIS_URL = "redis://redis:6379"

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, Dict[int, WebSocket]] = {}
        self.global_connections: Dict[int, WebSocket] = {}

        self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        self.pubsub = self.redis_client.pubsub()

    async def connect(self, websocket: WebSocket, user_id: int, room_id: int):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = {}
        self.active_connections[room_id][user_id] = websocket

    def disconnect(self, user_id: int, room_id: int):
        if room_id in self.active_connections and user_id in self.active_connections[room_id]:
            del self.active_connections[room_id][user_id]
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]

    async def broadcast(self, message: str, room_id: int, sender_id: int):
        payload = {
            "event_type": "room_message",
            "room_id": room_id,
            "sender_id": sender_id,
            "message": message
        }
        await self.redis_client.publish("chat_channel", json.dumps(payload))

    async def connect_global(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.global_connections[user_id] = websocket

        count = await self.redis_client.hincrby("online_users", str(user_id), 1)

        if count == 1:
            await self.broadcast_presence(user_id, True)

    async def disconnect_global(self, user_id: int):
        if user_id in self.global_connections:
            del self.global_connections[user_id]

        count = await self.redis_client.hincrby("online_users", str(user_id), -1)

        if count <= 0:
            await self.redis_client.hdel("online_users", str(user_id))
            await self.broadcast_presence(user_id, False)

    async def broadcast_presence(self, user_id: int, is_online: bool):
        payload = {
            "event_type": "presence",
            "user_id": user_id,
            "is_online": is_online
        }
        await self.redis_client.publish("chat_channel", json.dumps(payload))

    async def broadcast_global(self, recipient_id: int, notification: dict):
        payload = {
            "event_type": "global_notification",
            "recipient_id": recipient_id,
            "notification": notification
        }
        await self.redis_client.publish("chat_channel", json.dumps(payload))

    async def listen_to_redis(self):
        try:
            await self.pubsub.subscribe("chat_channel")
            print("Redis Listener started, subscribed to 'chat_channel'")

            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])

                    if data["event_type"] == "room_message":
                        room_id = data["room_id"]
                        sender_id = data["sender_id"]
                        text = data["message"]

                        if room_id in self.active_connections:
                            users_in_room = list(self.active_connections[room_id].keys())
                            for user_id in users_in_room:
                                connection = self.active_connections[room_id].get(user_id)
                                if connection:
                                    message_with_class = {
                                        "message": text,
                                        "is_self": sender_id == user_id
                                    }
                                    try:
                                        await connection.send_json(message_with_class)
                                    except Exception as e:
                                        print(f"ERROR in room: {e}")
                                        self.disconnect(user_id, room_id)

                    elif data["event_type"] == "global_notification":
                        recipient_id = data["recipient_id"]
                        notification = data["notification"]

                        if recipient_id in self.global_connections:
                            websocket = self.global_connections[recipient_id]
                            try:
                                await websocket.send_json(notification)
                            except Exception as e:
                                print(f"ERROR global socket: {e}")
                                await self.disconnect_global(recipient_id)

                    elif data["event_type"] == "presence":
                        presence_data = {
                            "type": "presence_update",
                            "user_id": data["user_id"],
                            "is_online": data["is_online"]
                        }
                        for uid, ws in list(self.global_connections.items()):
                            try:
                                await ws.send_json(presence_data)
                            except Exception as e:
                                print(f"ERROR presence socket: {e}")
                                await self.disconnect_global(uid)

        except Exception as e:
            print(f"ERROR REDIS LISTENER: {e}")


manager = ConnectionManager()
router = APIRouter(prefix="/ws", tags=["WebSocket"])

@router.websocket("/chat/{room_id}/{user_id}/{recipient_id}")
async def websocket_endpoint(
        websocket: WebSocket,
        room_id: int,
        user_id: int,
        recipient_id: int,
        username: str,
        db: AsyncSession = Depends(get_db)
):
    await manager.connect(websocket, user_id, room_id)

    try:
        query = select(Message).where(Message.room_id == room_id).order_by(Message.timestamp.asc())
        result = await db.execute(query)
        history = result.scalars().all()

        for msg in history:
            await websocket.send_json({
                "message": msg.content,
                "is_self": msg.sender_id == user_id,
                "author": username if msg.sender_id == user_id else "User"
            })

        while True:
            data = await websocket.receive_json()
            text = data.get("text")

            if text:
                new_msg = Message(room_id=room_id, sender_id=user_id, content=text)
                db.add(new_msg)
                await db.commit()

                await manager.broadcast(text, room_id, user_id)

                is_recipient_in_room = (
                        (room_id in manager.active_connections) and
                        (recipient_id in manager.active_connections[room_id])
                )

                if not is_recipient_in_room:
                    notification = {
                        "type": "new_message",
                        "from_user_id": user_id,
                        "from_username": username,
                        "text": text
                    }
                    await manager.broadcast_global(recipient_id, notification)

    except WebSocketDisconnect:
        manager.disconnect(user_id, room_id)
    except Exception as e:
        print(f"ERROR:{e}")
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
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    online_ids_str = await redis_client.hkeys("online_users")
    online_ids = [int(uid) for uid in online_ids_str]
    await redis_client.close()
    return {"online_users": online_ids}