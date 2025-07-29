import websocket
import json
import ssl
import certifi
import threading
import requests

def get_active_bybit_spot_symbols() -> set:
    """
    Ambil simbol Spot aktif (status Trading) dari Bybit.
    Return: set symbol, misal: {"BTCUSDT", "ETHUSDT", ...}
    """
    url = "https://api.bybit.com/v5/market/instruments-info"
    params = {"category": "spot"}
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("retCode") != 0:
            print("[Bybit] Gagal ambil simbol:", data.get("retMsg"))
            return set()

        return {
            item["symbol"]
            for item in data["result"]["list"]
            if item.get("status") == "Trading"
        }

    except Exception as e:
        print("[Bybit] ERROR:", str(e))
        return set()


last_prices = {}

def start_multi(callback, symbols):
    """Subscribe ke banyak simbol Bybit SPOT."""
    socket = "wss://stream.bybit.com/v5/public/spot"

    def on_open(ws):
        active_symbols = get_active_bybit_spot_symbols()

        # Filter hanya simbol yang aktif di Bybit
        filtered = [
            f"tickers.{symbol.upper()}"
            for symbol in symbols
            if symbol.upper() in active_symbols
        ]
        print(f"[Bybit] Total simbol aktif yang disubscribe: {len(filtered)}")

        # Kirim dalam batch (Bybit max 10 per subscribe)
        chunk_size = 10
        for i in range(0, len(filtered), chunk_size):
            chunk = filtered[i:i+chunk_size]
            sub_msg = {
                "op": "subscribe",
                "args": chunk
            }
            ws.send(json.dumps(sub_msg))
            # print("[Bybit] Subscribed to:", chunk)

    def on_message(ws, message):
        data = json.loads(message)
        if 'data' in data:
            items = data['data']
            # Pastikan ini list (bisa juga dict tergantung bybit)
            if isinstance(items, dict):
                items = [items]

            updated_symbols = []

            for item in items:
                # print(items)
                symbol = item.get('symbol')
                price = item.get('lastPrice')

                if not symbol or price is None:
                    continue

                if last_prices.get(symbol) != price:
                    last_prices[symbol] = price
                    updated_symbols.append({
                        "symbol": symbol,
                        "price": price
                    })
            # print(updated_symbols)
            if updated_symbols:
                callback({
                    "exchange": "Bybit",
                    "data": updated_symbols
                })

    def on_error(ws, error):
        print("[Bybit] Error:", error)

    def on_close(ws, *args):
        print("[Bybit] Connection closed")

    ws = websocket.WebSocketApp(socket,
                                 on_open=on_open,
                                 on_message=on_message,
                                 on_error=on_error,
                                 on_close=on_close)

    threading.Thread(target=lambda: ws.run_forever(sslopt={
        "cert_reqs": ssl.CERT_REQUIRED,
        "ca_certs": certifi.where()
    }), daemon=True).start()
# def start(callback, symbol):
#     socket = f"wss://stream.bybit.com/v5/public/spot"

#     def on_open(ws):
#         sub_msg = {
#             "op": "subscribe",
#             "args": [f"tickers.{symbol}"]
#         }
#         ws.send(json.dumps(sub_msg))

#     def on_message(ws, message):
#         data = json.loads(message)
#         if 'data' in data and isinstance(data['data'], dict):
#             price = data['data'].get('lastPrice')
#             if price:
#                 callback({'exchange': 'Bybit', 'symbol': symbol, 'price': price})

#     def on_error(ws, error):
#         print("[Bybit] Error:", error)

#     def on_close(ws, *args):
#         print("[Bybit] Connection closed")

#     ws = websocket.WebSocketApp(socket, 
#                                  on_open=on_open,
#                                  on_message=on_message, 
#                                  on_error=on_error, 
#                                  on_close=on_close)
    
#     ws.run_forever(sslopt={"cert_reqs": ssl.CERT_REQUIRED, "ca_certs": certifi.where()})