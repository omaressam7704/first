from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import WebSocket
from app.models.models import Notification, User
from app.schemas.schemas import NotificationResponse

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        # Maps user_id -> List[WebSocket]
        self.active_connections: dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_personal_message(self, message: dict, user_id: int):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    # Handle disconnection or error silently ideally or log it
                    pass

    async def broadcast(self, message: dict):
        for user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                 try:
                    await connection.send_json(message)
                 except Exception:
                    pass

manager = ConnectionManager()

async def create_notification(
    db: AsyncSession,
    user_id: int,
    title: str,
    message: str,
    type: str
):
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=type
    )
    db.add(notification)
    
    # Push via WebSocket
    # We construct the message to match the schema or frontend expectation
    ws_message = {
        "type": type,
        "title": title,
        "message": message,
        # "created_at": str(datetime.now()) # Optionally add timestamp
    }
    await manager.send_personal_message(ws_message, user_id)
    
    return notification
