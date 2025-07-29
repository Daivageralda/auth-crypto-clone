import websocket
import json
import ssl
import certifi
import threading
import requests
from typing import List

# Simpan harga terakhir
last_prices = {}

# Ambil semua pasangan yang valid dari Gate.io
def fetch_valid_pairs(quote="USDT"):
    url = "https://api.gateio.ws/api/v4/spot/currency_pairs"
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        valid_set = {
            item["id"].upper().replace("_", "") for item in data
            if item["quote"] == quote and item["trade_status"] == "tradable"
        }
        return valid_set
    except Exception as e:
        print("[Gate.io] Failed to fetch valid pairs:", e)
        return set()

def start_multi(callback, symbols: List[str]):
    batch_size = 20
    valid_symbols = fetch_valid_pairs()

    # Filter simbol yang tidak tersedia di Gate.io
    filtered_symbols = [s for s in symbols if s in valid_symbols]
    if not filtered_symbols:
        print("[Gate.io] No valid symbols to subscribe.")
        return

    def run_batch(pairs_batch):
        ws_url = "wss://api.gateio.ws/ws/v4/"

        def on_open(ws):
            sub_msg = {
                "time": 0,
                "channel": "spot.tickers",
                "event": "subscribe",
                "payload": [s.replace("USDT", "_USDT") for s in pairs_batch]
            }
            # print(f"[Gate.io] Subscribing batch: {sub_msg['payload']}")
            ws.send(json.dumps(sub_msg))

        def on_message(ws, message):
            try:
                data = json.loads(message)
                # print(data)
                if data.get("event") != "update":
                    return

                result = data.get("result")
                if not isinstance(result, dict):
                    return

                symbol_raw = result.get("currency_pair", "")
                price = result.get("last")
                symbol = symbol_raw.replace("_", "")

                updated_symbols = []

                if symbol and price:
                    if last_prices.get(symbol) != price:
                        last_prices[symbol] = price
                        updated_symbols.append({
                            "symbol": symbol,
                            "price": price
                        })

                if updated_symbols:
                    callback({
                        "exchange": "Gate.io",
                        "data": updated_symbols
                    })

            except Exception as e:
                print("[Gate.io] Error parsing message:", e)

        def on_error(ws, error):
            print("[Gate.io] WebSocket error:", error)

        def on_close(ws, *args):
            print("[Gate.io] WebSocket closed")

        ws = websocket.WebSocketApp(
            ws_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )

        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_REQUIRED, "ca_certs": certifi.where()})

    # Bagi simbol yang valid menjadi batch kecil
    for i in range(0, len(filtered_symbols), batch_size):
        batch = filtered_symbols[i:i + batch_size]
        thread = threading.Thread(target=run_batch, args=(batch,))
        thread.daemon = True
        thread.start()
