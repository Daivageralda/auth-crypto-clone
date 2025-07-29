import websocket
import json
import ssl
import certifi
import threading
import time

def start_multi(callback, symbol):
    latest_prices = {}
    updated_prices = []
    lock = threading.Lock()

    def flush_updates():
        """Routine untuk flush semua update simbol secara periodik."""
        while True:
            time.sleep(0.5)  # flush setiap 0.5 detik, bisa disesuaikan
            with lock:
                if updated_prices:
                    callback({
                        "exchange": "MEXC",
                        "data": updated_prices.copy()
                    })
                    updated_prices.clear()

    def create_socket(symbol):
        def on_open(ws):
            sub = {
                "method": "SUBSCRIPTION",
                "params": [f"spot@public.deals.v3.api@{symbol}"],
                "id": 1
            }
            ws.send(json.dumps(sub))

        def on_message(ws, msg):
            try:
                data = json.loads(msg)
                if data.get("c") == f"spot@public.deals.v3.api@{symbol}":
                    deals = data.get("d", {}).get("deals", [])
                    if deals:
                        price = deals[0].get("p")
                        if price:
                            with lock:
                                if latest_prices.get(symbol) != price:
                                    latest_prices[symbol] = price
                                    updated_prices.append({
                                        "symbol": symbol,
                                        "price": price})
            except Exception as e:
                print(f"[MEXC:{symbol}] Error parsing message:", e)

        ws = websocket.WebSocketApp(
            "wss://wbs.mexc.com/ws",
            on_open=on_open,
            on_message=on_message,
            on_error=lambda ws, e: print(f"[MEXC:{symbol}] Error:", e),
            on_close=lambda ws, code, msg: print(f"[MEXC:{symbol}] Closed")
        )

        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_REQUIRED, "ca_certs": certifi.where()})

    # Start socket untuk setiap simbol
    for sym in symbol:
        t = threading.Thread(target=create_socket, args=(sym,))
        t.daemon = True
        t.start()

    # Start thread untuk flush update secara batch
    flush_thread = threading.Thread(target=flush_updates)
    flush_thread.daemon = True
    flush_thread.start()


# import websocket
# import json
# import ssl
# import certifi

# def start(callback, symbol):
#     def on_open(ws):
#         sub = {
#             "method": "SUBSCRIPTION",
#             "params": [f"spot@public.deals.v3.api@{symbol}"],
#             "id": 1
#         }
#         ws.send(json.dumps(sub))

#     def on_message(ws, msg):
#         try:
#             data = json.loads(msg)
#             if data.get("c") == f"spot@public.deals.v3.api@{symbol}":
#                 deals = data.get("d", {}).get("deals", [])
#                 if deals:
#                     price = deals[0].get("p")
#                     if price:
#                         callback({
#                             "exchange": "MEXC",
#                             "symbol": symbol,
#                             "price": price
#                         })
#         except Exception as e:
#             print("[MEXC] Error parsing message:", e)

#     ws = websocket.WebSocketApp(
#         "wss://wbs.mexc.com/ws",
#         on_open=on_open,
#         on_message=on_message,
#         on_error=lambda ws, e: print("[MEXC] Error:", e),
#         on_close=lambda ws, code, msg: print("[MEXC] Closed")
#     )

#     ws.run_forever(sslopt={"cert_reqs": ssl.CERT_REQUIRED, "ca_certs": certifi.where()})
