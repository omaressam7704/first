from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.notification_service import manager
from app.core.security import SecurityUtils
from fastapi import Query

router = APIRouter()

@router.websocket("/ws/notifications/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int, token: str = Query(...)):
    # Validate token
    # In real world, verify token matches user_id or valid session
    # For now, simplistic check
    try:
        # Verify token?
        # decoded = SecurityUtils.verify_token(token) ...
        pass
    except Exception:
        await websocket.close(code=1008)
        return

    await manager.connect(websocket, user_id)
    try:
        while True:
            # Keep alive
            data = await websocket.receive_text()
            # We can handle client messages here (e.g. echo)
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
