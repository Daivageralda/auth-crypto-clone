import websocket
import json
import requests
import ssl
import certifi
import threading
import time

from app.utils import TICKERS_SYMBOL  # misalnya: ["BTC-USDT", "ETH-USDT", ...]


last_prices = {}

def get_kucoin_ws_info():
    """Ambil informasi WebSocket publik dari KuCoin REST API."""
    try:
        res = requests.post("https://api.kucoin.com/api/v1/bullet-public")
        res.raise_for_status()
        data = res.json()["data"]
        return {
            "token": data["token"],
            "endpoint": data["instanceServers"][0]["endpoint"]
        }
    except Exception as e:
        print("[KuCoin] Failed to fetch WS info:", e)
        return None

def start_multi(callback, symbols=TICKERS_SYMBOL):
    """
    Mulai koneksi WebSocket untuk banyak simbol di KuCoin.
    Memanggil callback jika ada harga yang berubah.
    """
    print("WEWEWEW")
    info = get_kucoin_ws_info()
    if info is None:
        return

    token = info["token"]
    endpoint = info["endpoint"]
    ws_url = f"{endpoint}?token={token}"

    def on_message(ws, message):
        updated_symbols=[]
        try:
            data = json.loads(message)
            # print(data)
            if data.get("type") == "message" and "data" in data:
                topic = data.get("topic", "")
                ticker = data["data"]
                price = float(ticker.get("price", 0))

                if price == 0 or not topic.startswith("/market/ticker:"):
                    return

                symbol = topic.split(":")[1].upper()

                if last_prices.get(symbol) != price:
                    symbol_clear=symbol.replace("-", "")
                    last_prices[symbol] = price
                    updated_symbols.append({
                        "symbol": symbol_clear,
                        "price": price
                    })

            if updated_symbols:
                callback({
                    "exchange": "Kucoin",
                    "data": updated_symbols
                })

            elif data.get("type") == "ping":
                ws.send(json.dumps({"type": "pong"}))

        except Exception as e:
            print("[KuCoin] Error parsing message:", e)

    def on_open(ws):
        for symbol in symbols:
            # Tambahkan dash pemisah: BTCUSDT → BTC-USDT
            if len(symbol) >= 6:
                base = symbol[:-4]
                quote = symbol[-4:]
                symbol_with_dash = f"{base}-{quote}"
            else:
                symbol_with_dash = symbol  # fallback

            sub_msg = {
                "id": int(time.time() * 1000),
                "type": "subscribe",
                "topic": f"/market/ticker:{symbol_with_dash}",
                "privateChannel": False,
                "response": True,
            }
            ws.send(json.dumps(sub_msg))
            # print(f"[KuCoin] Subscribed to {symbol_with_dash}")


    def on_error(ws, error):
        print("[KuCoin] Error:", error)

    def on_close(ws, code, msg):
        print("[KuCoin] Connection closed:", code, msg)

    def keep_alive():
        while True:
            try:
                ws = websocket.WebSocketApp(
                    ws_url,
                    on_message=on_message,
                    on_open=on_open,
                    on_error=on_error,
                    on_close=on_close
                )
                ws.run_forever(sslopt={
                    "cert_reqs": ssl.CERT_REQUIRED,
                    "ca_certs": certifi.where()
                }, ping_interval=20, ping_timeout=10)
            except Exception as e:
                print("[KuCoin] Reconnect error:", e)

            print("[KuCoin] Disconnected. Reconnecting in 5 seconds...")
            time.sleep(5)

    threading.Thread(target=keep_alive, daemon=True).start()
