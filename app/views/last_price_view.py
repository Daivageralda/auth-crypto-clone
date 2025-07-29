from fastapi import APIRouter, WebSocket, Request
from fastapi.responses import JSONResponse, HTMLResponse
from typing import Dict, List
from fastapi.templating import Jinja2Templates
from app.ws.exchange_manager import (
    get_all_prices,
    register_client,
    unregister_client,
    build_market_payload
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/last-price")
async def get_last_price():
    prices = get_all_prices()
    return JSONResponse(content=prices)

@router.get("/market")
async def market_view(request: Request):
    data = await build_market_payload()
    return templates.TemplateResponse("market.html", {
        "request": request,
        "markets": data
    })

# global cache of last pushed prices
last_sent: Dict[str, List[dict]] = {}

def is_updated(exchange: str, new_data: List[dict]) -> bool:
    old_data = last_sent.get(exchange)
    if old_data != new_data:
        last_sent[exchange] = new_data
        return True
    return False
@router.websocket("/ws-price")
async def price_stream(ws: WebSocket):
    await ws.accept()

    async def push(data: dict):
        exchange = data.get("exchange")
        coins = data.get("data", [])
        
        if not is_updated(exchange, coins):
            return

        try:
            await ws.send_json({
                "exchange": exchange,
                "data": coins
            })
        except Exception as e:
            print("[WebSocket] Error sending data:", e)


    register_client(push)
    try:
        while True:
            await ws.receive_text()  # Ping-pong atau keep alive dari frontend
    except Exception as e:
        print("[WebSocket] Disconnected:", e)
    finally:
        unregister_client(push)
