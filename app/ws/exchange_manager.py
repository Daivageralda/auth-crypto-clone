import threading
import asyncio
import inspect
import logging
from typing import Callable, Dict, List
from app.ws.exchanges import binance, bitget, bybit, gateio, huobi, indodax, kucoin, mexc, okx
from concurrent.futures import ThreadPoolExecutor
from app.utils import TICKERS_SYMBOL
executor = ThreadPoolExecutor(max_workers=10)  # bisa disesuaikan


logger = logging.getLogger("exchange_manager")
logging.basicConfig(level=logging.INFO)

latest_prices: Dict[str, Dict[str, str]] = {}
callbacks: List[Callable] = []
lock = threading.Lock()
main_loop = asyncio.get_event_loop()
DEFAULT_SYMBOL = "BTCUSDT"
TOP_COINS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT", "DOGEUSDT",
    "LTCUSDT", "BCHUSDT", "VETUSDT", "UNIUSDT", "CHZUSDT",
    "SANDUSDT", "MANAUSDT", "AXSUSDT", "ZILUSDT", "FILUSDT"
]

latest_gaps = {}
def is_valid_start(func: Callable) -> bool:
    try:
        return len(inspect.signature(func).parameters) == 2
    except:
        return False

def parse_float(val) -> float:
    try:
        return float(val)
    except:
        return 0.0
def calculate_top_gaps(source_prices: dict, target_prices: dict, source: str, target: str) -> dict:
    """
    Menghitung 10 gap terbesar antara dua exchange (misal Indodax dengan exchange lain).
    
    source_prices: dict harga dari exchange sumber (misalnya Indodax)
    target_prices: dict harga dari exchange target (misalnya Binance)
    source: nama exchange sumber
    target: nama exchange target
    """
    result = {
        "exchange": target,
        "data": []
    }

    gap_list = []

    for symbol, source_price in source_prices.items():
        target_price = target_prices.get(symbol)
        if target_price is None:
            continue

        try:
            source_price_f = float(source_price)
            target_price_f = float(target_price)

            if source_price_f <= 0 or target_price_f <= 0:
                continue

            gap = ((target_price_f - source_price_f) / source_price_f) * 100

            gap_list.append({
                "symbol": symbol,
                "market_a": f"{source_price_f:.4f}",  # Source (Indodax)
                "market_b": f"{target_price_f:.4f}",  # Target exchange
                "gap": f"{gap:.2f}%",
            })

        except Exception:
            continue

    # Urutkan dan ambil 10 terbesar
    top_10 = sorted(gap_list, key=lambda x: float(x["gap"].replace('%', '')), reverse=True)[:10]
    result["data"] = top_10
    return result


def callback(data: dict, symbol: str):
    with lock:
        exchange = data.get("exchange", "Unknown")
        items = data.get("data", [])

        for item in items:
            _symbol = item.get("symbol", symbol)
            price = parse_float(item.get("price", "0"))

            if price <= 0:
                continue

            if exchange not in latest_prices:
                latest_prices[exchange] = {}
            latest_prices[exchange][_symbol] = f"{price:.6f}"

        # Dapatkan harga dari Indodax
        indodax_prices = latest_prices.get("Indodax", {})
        if not indodax_prices:
            return
        # Untuk setiap exchange selain Indodax, hitung selisih dan kirim ke callback
        for ex, prices in latest_prices.items():
            if ex == "Indodax":
                continue

            # Ambil top gap untuk exchange ini terhadap Indodax
            result_payload = calculate_top_gaps(indodax_prices, prices, source="Indodax", target=ex)
            if not result_payload["data"]:
                continue
            # print(result_payload)
            latest_gaps[ex] = result_payload
            for cb in callbacks:
                try:
                    if asyncio.iscoroutinefunction(cb):
                        asyncio.run_coroutine_threadsafe(cb(result_payload), main_loop)
                    else:
                        cb(result_payload)
                except Exception as e:
                    logger.warning(f"[Callback Error] {e}")



def start_streaming(modules: List, symbol: str = DEFAULT_SYMBOL):
    for mod in modules:
        try:
            if hasattr(mod, 'start_multi'):
                executor.submit(mod.start_multi, lambda d: callback(d, symbol), TOP_COINS)
                logger.info(f"[Stream] start_multi: {mod.__name__}")
            elif hasattr(mod, 'start') and is_valid_start(mod.start):
                executor.submit(mod.start, lambda d: callback(d, symbol), symbol)
                logger.info(f"[Stream] start: {mod.__name__}")
            else:
                logger.warning(f"[Stream] {mod.__name__} tidak valid")
        except Exception as e:
            logger.exception(f"[Error] {mod.__name__}: {e}")

def get_all_prices() -> Dict[str, Dict[str, str]]:
    with lock:
        return latest_prices.copy()

def register_client(cb: Callable):
    with lock:
        callbacks.append(cb)
        logger.info(f"[Client] Registered")

def unregister_client(cb: Callable):
    with lock:
        if cb in callbacks:
            callbacks.remove(cb)
            logger.info(f"[Client] Unregistered")
top10_cache = {}

def get_top10(data: dict) -> List[dict]:
    return sorted(data.values(), key=lambda x: abs(float(x["gap"].strip("%"))), reverse=True)[:10]
async_lock=asyncio.Lock()
async def build_market_payload() -> List[Dict]:
    async with async_lock:
        result = []
        for target_exchange, payload in latest_gaps.items():
            if target_exchange == "Indodax":
                continue
            if not payload["data"]:
                continue

            result.append({
                "market": target_exchange,
                "data": payload["data"]
            })

        return result



# def build_market_payload() -> List[Dict]:
#     with lock:
#         result = []
#         indodax_data = latest_prices.get("Indodax", {})
#         symbol = indodax_data.get("symbol", "")
#         indodax_price = parse_float(indodax_data.get("price"))

#         for exchange, data in latest_prices.items():
#             if exchange == "Indodax" or data.get("symbol") != symbol:
#                 continue

#             other_price = parse_float(data.get("price"))
#             gap = "-"
#             if indodax_price > 0 and other_price > 0:
#                 gap_val = ((other_price - indodax_price) / indodax_price) * 100
#                 gap = f"{gap_val:.2f}%"

#             result.append({
#                 "market": exchange,
#                 "coin": [{
#                     "symbol": symbol,
#                     "market_a": f"{indodax_price:.4f}",
#                     "market_b": f"{other_price:.4f}",
#                     "gap": gap
#                 }]
#             })
#         return result
