from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.ws.exchange_manager import register_client, unregister_client, start_streaming
import asyncio
import json

router = APIRouter()

@router.websocket("/ws/prices")
async def crypto_price_ws(websocket: WebSocket):
    await websocket.accept()

    queue = asyncio.Queue()

    def send_update(data):
        asyncio.create_task(queue.put(data))

    register_client(send_update)

    try:
        while True:
            data = await queue.get()
            await websocket.send_text(json.dumps(data))
    except WebSocketDisconnect:
        unregister_client(send_update)
        await websocket.close()
