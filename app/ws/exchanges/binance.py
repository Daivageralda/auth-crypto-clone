import websocket as wbs
import json
import threading
import ssl
import certifi
# def start(callback, symbol):
#     symbol = 'btcusdt'
#     socket = f'wss://stream.binance.com:9443/ws/{symbol}@ticker'

#     def on_message(ws, message):
#         data = json.loads(message)
#         price = data['c']  
#         callback({'exchange': 'Binance', 'symbol': 'BTCUSDT', 'price': price})

#     def on_error(ws, error):
#         print("[Binance] Error:", error)

#     def on_close(ws, *args):
#         print("[Binance] Connection closed")

#     ws = wbs.WebSocketApp(socket, on_message=on_message, on_error=on_error, on_close=on_close)
#     ws.run_forever()
last_prices = {}  # symbol -> last price

def start_multi(callback, symbols):
    """
    Subscribe ke banyak simbol dari Binance menggunakan WebSocket.
    """
    # streams = "/".join([f"{s.lower()}@ticker" for s in symbols])
    socket = f"wss://stream.binance.com:9443/stream?streams=!ticker@arr"

    def on_message(ws, message):
            data = json.loads(message)
            ticker_list = data.get("data", [])
            updated_symbols = []

            for ticker in ticker_list:
                symbol = ticker.get("s")
                price = ticker.get("c")

                if symbol and price:
                    # Filter jika hanya tertarik simbol tertentu
                    if symbols and symbol not in symbols:
                        continue

                    if last_prices.get(symbol) != price:
                        last_prices[symbol] = price
                        updated_symbols.append({
                            "symbol": symbol,
                            "price": price
                        })

            if updated_symbols:
                # print(updated_symbols)
                callback({
                    "exchange": "Binance",
                    "data": updated_symbols
                })

    def on_error(ws, error):
        print("[Binance] Error:", error)

    def on_close(ws, *args):
        print("[Binance] Connection closed")

    def on_open(ws):
        print("[Binance] Subscribed to:", symbols)

    ws = wbs.WebSocketApp(
        socket,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    threading.Thread(target=lambda: ws.run_forever(sslopt={
        "cert_reqs": ssl.CERT_REQUIRED,
        "ca_certs": certifi.where()
    }), daemon=True).start()