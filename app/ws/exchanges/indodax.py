import threading
import requests
import time
from app.utils import USDTIDR_SYMBOL

last_prices = {}
def start_multi(callback, symbol):
    def poll():
        previous_prices = {}

        while True:
            try:
                # Ambil harga USDT/IDR
                r2 = requests.get(f"https://indodax.com/api/ticker/{USDTIDR_SYMBOL}", timeout=5)
                usdt_data = r2.json()
                if "ticker" not in usdt_data:
                    print("Invalid USDT/IDR ticker response:", usdt_data)
                    time.sleep(3)
                    continue
                usdt_idr = float(usdt_data["ticker"]["last"])

                # Ambil semua data ticker
                r = requests.get("https://indodax.com/api/ticker_all", timeout=5)
                data = r.json()
                if "tickers" not in data:
                    print("Invalid ticker_all response:", data)
                    time.sleep(3)
                    continue

                all_tickers = data["tickers"]

                # Proses simbol yang diminta
                result = []
                changed = False

                for symb in symbol:
                    indodax_symbol = symb.lower().replace("usdt", "") + "_idr"
                    if indodax_symbol in all_tickers:
                        price_idr = float(all_tickers[indodax_symbol]["last"])
                        price_usdt = price_idr / usdt_idr

                        prev_price = previous_prices.get(symb)
                        if prev_price is None or abs(prev_price - price_usdt) > 1e-6:
                            # Hanya dianggap berubah jika ada selisih lebih dari toleransi kecil (1e-6)
                            previous_prices[symb] = price_usdt
                            changed = True

                        result.append({
                            "symbol": symb,
                            "price": price_usdt
                        })

                if changed and result:
                    # print(result)
                    callback({
                        "exchange": "Indodax",
                        "data": result
                    })

            except Exception as e:
                print("Error polling Indodax:", e)

            time.sleep(3)

    threading.Thread(target=poll, daemon=True).start()

# def start(callback, symbol):
#     def poll():
#         while True:
#             try:
#                 # usdtidr price
#                 r2 = requests.get(f"https://indodax.com/api/ticker/{USDTIDR_SYMBOL}", timeout=5)
#                 usdt_data = r2.json()
#                 # print(usdt_data)
#                 if "ticker" not in usdt_data:
#                     print("Invalid USDT/IDR ticker response:", usdt_data)
#                     time.sleep(3)
#                     continue
#                 usdt_idr = float(usdt_data["ticker"]["last"])

#                 # All tickers
#                 r = requests.get("https://indodax.com/api/ticker_all", timeout=5)
#                 data = r.json()
#                 if "tickers" not in data:
#                     print("Invalid ticker_all response:", data)
#                     time.sleep(3)
#                     continue

#                 all_tickers = data["tickers"]
#                 pure_usdt_prices = {}
#                 symbolku = []
#                 updated_symbols = {}

#                 # if _usdt -> convert and save as reference
#                 for sym, info in all_tickers.items():
#                     if sym.endswith("_usdt"):
#                         try:
#                             price = float(info["last"])
#                             symbol_formatted = sym.replace("_usdt", "USDT").upper()  # e.g. btc_usdt → BTCUSDT
#                             pure_usdt_prices[symbol_formatted] = price
#                         except Exception as e:
#                             print(f"Error reading USDT symbol {sym}: {e}")
#                             continue
                
#                 converted_symbols = set()

#                 # if idr symbol -> convert it
#                 for sym, info in all_tickers.items():
#                     if not sym.endswith("_idr"):
#                         continue  # Skip non-IDR pairs

#                     try:
#                         price_idr = float(info["last"])
#                         price_usdt = price_idr / usdt_idr
#                         symbol_formatted = sym.replace("_idr", "USDT").upper()
#                         converted_symbols.add(symbol_formatted)

#                         # Gunakan harga *_usdt jika tersedia
#                         if symbol_formatted in pure_usdt_prices:
#                             price_usdt = pure_usdt_prices[symbol_formatted]

#                         symbolku.append(symbol_formatted)
#                         print(sym,price_usdt)
#                         if last_prices.get(symbol_formatted) != price_usdt:
#                             last_prices[symbol_formatted] = price_usdt
#                             updated_symbols[symbol_formatted] = f"{price_usdt:.6f}"

#                     except Exception as e:
#                         print(f"Error processing IDR symbol {sym}: {e}")
#                         continue

#                 # if not in idr symbols
#                 for symbol_formatted, price in pure_usdt_prices.items():
#                     if symbol_formatted not in converted_symbols:
#                         symbolku.append(symbol_formatted)
#                         if last_prices.get(symbol_formatted) != price:
#                             last_prices[symbol_formatted] = price
#                             updated_symbols[symbol_formatted] = f"{price:.6f}"

#                 if updated_symbols:
#                     print(updated_symbols.get("MANAUSDT"))
#                     callback({
#                         "exchange": "Indodax",
#                         "data": [
#                             {"symbol": sym, "price": price}
#                             for sym, price in updated_symbols.items()
#                         ]
#                     })

#             except Exception as e:
#                 print("Indodax Polling Error:", e)

#             time.sleep(3)

#     threading.Thread(target=poll, daemon=True).start()
# #