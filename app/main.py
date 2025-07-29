from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.views import auth_view, dashboard_view, last_price_view
from app.ws import ws_router
from app.ws.exchange_manager import start_streaming
from app.ws.exchanges import binance, bybit, okx, kucoin, indodax, huobi, gateio, mexc, bitget
from fastapi import WebSocket
from app.ws.exchange_manager import register_client, unregister_client

app = FastAPI()

@app.websocket("/ws-price")
async def price_stream(ws: WebSocket):
    await ws.accept()

    async def push(data: dict):
        # print("[WS] push called:", data)  
        try:
            await ws.send_json(data)
        except Exception as e:
            print("[WS] Send error:", e)

    register_client(push)
    try:
        while True:
            await ws.receive_text()
    except:
        pass
    finally:
        unregister_client(push)


app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth_view.router)
app.include_router(ws_router.router)
app.include_router(dashboard_view.router)
app.include_router(last_price_view.router)
start_streaming([
    binance,
    bybit,
    okx, 
    kucoin, 
    indodax, 
    huobi, 
    gateio,
     mexc, 
    bitget
])


    