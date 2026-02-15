from fastapi import WebSocket, APIRouter, WebSocketDisconnect
from typing import Dict

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, Dict[int, WebSocket]] = {}

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
        if room_id in self.active_connections and sender_id in self.active_connections[room_id]:
            for user_id, connection in self.active_connections[room_id].items():
                message_with_class = {
                    "message": message,
                    "is_self": sender_id == user_id
                }
                await connection.send_json(message_with_class)



manager = ConnectionManager()
router = APIRouter(prefix="/ws", tags=["WebSocket"])

@router.websocket("/chat/{room_id}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: int, user_id: int, username: str):
    await manager.connect(websocket, user_id, room_id)
    await manager.broadcast(f"{username} has joined the chat", room_id, user_id)

    try:
        while True:
            data = await websocket.receive_json()
            await manager.broadcast(f"{username} (ID {user_id}): {data}" , room_id, user_id)

    except WebSocketDisconnect:
        manager.disconnect(user_id, room_id)
        await manager.broadcast(f"{username} has left the chat", room_id, user_id)