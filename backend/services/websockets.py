import json
from typing import Dict

import redis.asyncio as redis
from fastapi import WebSocket

from config import settings


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: Dict[int, Dict[int, WebSocket]] = {}
        self.global_connections: Dict[int, WebSocket] = {}

        redis_url = f"redis://{settings.REDIS_HOST}:6379"

        self.redis_client = redis.from_url(redis_url, decode_responses=True)
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
            "message": message,
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
        payload = {"event_type": "presence", "user_id": user_id, "is_online": is_online}
        await self.redis_client.publish("chat_channel", json.dumps(payload))

    async def broadcast_global(self, recipient_id: int, notification: dict):
        payload = {
            "event_type": "global_notification",
            "recipient_id": recipient_id,
            "notification": notification,
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
                                        "text": text,
                                        "is_self": sender_id == user_id,
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
                            "is_online": data["is_online"],
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
