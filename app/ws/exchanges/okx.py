import websocket
import json
import ssl
import certifi
import threading
import time

last_prices = {}

def keep_alive(ws_app, sslopt):
    """Menjaga koneksi WebSocket tetap hidup dan reconnect jika putus."""
    while True:
        try:
            ws_app.run_forever(sslopt=sslopt)
        except Exception as e:
            print("[OKX] Reconnect error:", e)
        print("[OKX] Disconnected. Reconnecting in 5 seconds...")
        time.sleep(5)

def start_multi(callback, symbols: list):
    """
    Memulai koneksi WebSocket ke OKX dan memanggil callback ketika ada update harga.
    :param callback: fungsi callback(dict)
    :param symbols: list of strings, contoh ["BTCUSDT", "ETHUSDT"]
    """

    dash_symbols = []
    symbol_map = {}

    # Ubah ke format "BTC-USDT", simpan mappingnya
    for sym in symbols:
        if len(sym) >= 6:
            base = sym[:-4]
            quote = sym[-4:]
            dash = f"{base}-{quote}"
        else:
            dash = sym
        dash_symbols.append(dash)
        symbol_map[dash] = sym  # BTC-USDT → BTCUSDT

    def on_open(ws):
        args = [{"channel": "tickers", "instId": s} for s in dash_symbols]
        sub_msg = {
            "op": "subscribe",
            "args": args
        }
        ws.send(json.dumps(sub_msg))
        # print(f"[OKX] Subscribed to: {dash_symbols}")

    def on_message(ws, message):
        updated_symbols = []

        try:
            data = json.loads(message)

            if data.get("event") == "subscribe":
                print(f"[OKX] Subscription success: {data}")
                return

            if "data" in data and isinstance(data["data"], list):
                for ticker in data["data"]:
                    inst_id = ticker.get("instId")
                    price = ticker.get("last")

                    if not inst_id or not price:
                        continue

                    original_symbol = symbol_map.get(inst_id, inst_id.replace("-", ""))
                    if last_prices.get(original_symbol) != price:
                        last_prices[original_symbol] = price
                        updated_symbols.append({
                            "symbol": original_symbol,
                            "price": price
                        })

                if updated_symbols:
                    callback({
                        "exchange": "OKX",
                        "data": updated_symbols
                    })

        except Exception as e:
            print("[OKX] Error parsing message:", e)

    def on_error(ws, error):
        print("[OKX] Error:", error)

    def on_close(ws, code=None, msg=None):
        print(f"[OKX] Connection closed: {code} - {msg}")

    ws = websocket.WebSocketApp(
        "wss://ws.okx.com:8443/ws/v5/public",
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    sslopt = {
        "cert_reqs": ssl.CERT_REQUIRED,
        "ca_certs": certifi.where()
    }

    threading.Thread(
        target=keep_alive,
        args=(ws, sslopt),
        daemon=True
    ).start()
