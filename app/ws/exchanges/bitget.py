# import websocket
# import json
# import ssl
# import certifi

# def start(callback, symbol):
#     symbol = "BTCUSDT"

#     def on_open(ws):
#         sub_msg = {
#             "op": "subscribe",
#             "args": [{
#                 "instType": "SPOT",
#                 "channel": "ticker",
#                 "instId": symbol
#             }]
#         }
#         ws.send(json.dumps(sub_msg))
#         print(f"[Bitget] Subscribed to {symbol}")

#     def on_message(ws, message):
#         data = json.loads(message)
#         if data.get("action") == "snapshot" and "data" in data:
#             for item in data["data"]:
#                 callback({
#                     "exchange": "Bitget",
#                     "symbol": item.get("instId"),
#                     "price": item.get("lastPr")
#                 })

#     def on_error(ws, error):
#         print("[Bitget] Error:", error)

#     def on_close(ws, *args):
#         print("[Bitget] Closed")

#     ws = websocket.WebSocketApp(
#         "wss://ws.bitget.com/v2/ws/public",
#         on_open=on_open,
#         on_message=on_message,
#         on_error=on_error,
#         on_close=on_close
#     )

#     ws.run_forever(sslopt={
#         "cert_reqs": ssl.CERT_REQUIRED,
#         "ca_certs": certifi.where()
#     })
import websocket
import json
import ssl
import certifi
import threading
import time
import logging
import random
from app.utils import TICKERS_SYMBOL

# Bitget WebSocket URIs for fallback
BITGET_WEBSOCKET_URIS = [
    "wss://ws.bitget.com/v2/ws/public",
    "wss://ws.bitgetapi.com/v2/ws/public"
]

BATCH_SIZE = 50  # Bitget can handle more symbols per connection
MAX_RECONNECT_ATTEMPTS = 5
INITIAL_RECONNECT_DELAY = 10
PING_INTERVAL = 30
PING_TIMEOUT = 10
HEALTH_CHECK_INTERVAL = 120

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bitget-client")

def start_multi(callback, symbols=TICKERS_SYMBOL):
    last_prices = {}
    active_connections = {}
    reconnect_attempts = {}
    failed_batches = set()
    batch_symbols_map = {}
    restart_timer = time.time()

    def check_network_connectivity():
        """Simple connectivity check"""
        import socket
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except:
            return False

    def run_ws(symbol_batch, batch_id=None, uri_index=0, attempt=0):
        if batch_id is None:
            batch_id = f"batch_{hash(tuple(symbol_batch)) % 10000}"
        
        # Exponential backoff for reconnections
        if attempt > 0:
            delay = min(INITIAL_RECONNECT_DELAY * (2 ** (attempt - 1)), 60)
            logger.info(f"[Bitget] Reconnecting batch {batch_id} in {delay}s (attempt {attempt})")
            time.sleep(delay)

        # Cycle through URIs if previous ones failed
        if uri_index >= len(BITGET_WEBSOCKET_URIS):
            uri_index = 0

        uri = BITGET_WEBSOCKET_URIS[uri_index]

        def on_open(ws):
            logger.info(f"[Bitget] Connected batch {batch_id} to {uri} with {len(symbol_batch)} symbols")
            active_connections[batch_id] = ws
            reconnect_attempts[batch_id] = 0
            
            try:
                sub_msg = {
                    "op": "subscribe",
                    "args": [{
                        "instType": "SPOT",
                        "channel": "ticker",
                        "instId": symbol.upper()
                    } for symbol in symbol_batch]
                }
                ws.send(json.dumps(sub_msg))
                logger.info(f"[Bitget] Subscribed to {len(symbol_batch)} symbols in batch {batch_id}")
            except Exception as e:
                logger.error(f"[Bitget] Failed to subscribe in batch {batch_id}: {e}")

        def on_message(ws, message):
            try:
                data = json.loads(message)
                
                # Handle ping-pong
                if data.get("event") == "ping":
                    ws.send(json.dumps({"event": "pong"}))
                    logger.debug(f"[Bitget] Pong sent for batch {batch_id}")
                    return
                
                # Handle ticker data
                if data.get("action") == "snapshot" and "data" in data:
                    updated_symbols = []

                    for item in data["data"]:
                        symbol = item.get("instId", "").upper()
                        price = item.get("lastPr")

                        if not symbol or price is None:
                            continue

                        try:
                            price = float(price)
                        except (ValueError, TypeError):
                            continue

                        # Send only if price changed
                        if last_prices.get(symbol) != price:
                            last_prices[symbol] = price
                            updated_symbols.append({
                                "symbol": symbol,
                                "price": price
                            })

                    if updated_symbols:
                        callback({
                            "exchange": "Bitget",
                            "data": updated_symbols,
                            "batch_id": batch_id
                        })
                        
            except Exception as e:
                logger.error(f"[Bitget] Message processing error in batch {batch_id}: {e}")

        def on_error(ws, error):
            logger.error(f"[Bitget] Error in batch {batch_id}: {error}")
            if batch_id in active_connections:
                del active_connections[batch_id]
            try_reconnect()

        def on_close(ws, code, msg):
            logger.warning(f"[Bitget] Closed batch {batch_id}: {code} - {msg}")
            if batch_id in active_connections:
                del active_connections[batch_id]
            try_reconnect()

        def try_reconnect():
            current_attempt = reconnect_attempts.get(batch_id, 0)
            
            if current_attempt >= MAX_RECONNECT_ATTEMPTS:
                logger.error(f"[Bitget] Max reconnection attempts reached for batch {batch_id}")
                failed_batches.add(batch_id)
                return
            
            reconnect_attempts[batch_id] = current_attempt + 1
            
            # Check network connectivity before attempting reconnection
            if not check_network_connectivity():
                logger.warning(f"[Bitget] Network connectivity issue detected, waiting longer for batch {batch_id}")
                time.sleep(30)
            
            # Try next URI or restart from first URI
            next_uri_index = (uri_index + 1) % len(BITGET_WEBSOCKET_URIS)
            
            def reconnect_thread():
                run_ws(symbol_batch, batch_id, next_uri_index, current_attempt + 1)
            
            thread = threading.Thread(target=reconnect_thread)
            thread.daemon = True
            thread.start()

        try:
            # Add random delay to avoid overwhelming the server
            if attempt > 0:
                time.sleep(random.uniform(2.0, 5.0))
            
            # Check network before attempting connection
            if not check_network_connectivity():
                logger.warning(f"[Bitget] Network connectivity issue, skipping connection attempt for batch {batch_id}")
                time.sleep(60)
                try_reconnect()
                return
            
            ws = websocket.WebSocketApp(
                uri,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            
            # Enhanced connection options
            ws.run_forever(
                sslopt={
                    "cert_reqs": ssl.CERT_NONE,  # Less strict SSL
                    "ca_certs": certifi.where()
                },
                ping_interval=PING_INTERVAL,
                ping_timeout=PING_TIMEOUT,
                # timeout=30
            )
            
        except Exception as e:
            logger.error(f"[Bitget] WebSocket thread crash for batch {batch_id}: {e}")
            try_reconnect()

    def restart_failed_batches():
        """Restart failed batches periodically"""
        if not failed_batches:
            return
            
        logger.info(f"[Bitget] Attempting to restart {len(failed_batches)} failed batches")
        batches_to_restart = list(failed_batches)
        failed_batches.clear()
        
        for batch_id in batches_to_restart:
            if batch_id in batch_symbols_map:
                symbol_batch = batch_symbols_map[batch_id]
                reconnect_attempts[batch_id] = 0  # Reset attempts
                
                def restart_thread():
                    time.sleep(random.uniform(5, 15))
                    run_ws(symbol_batch, batch_id, 0, 0)
                
                thread = threading.Thread(target=restart_thread)
                thread.daemon = True
                thread.start()
                
                time.sleep(2)

    # Split symbols into batches and start connections
    for i in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[i:i + BATCH_SIZE]
        batch_id = f"batch_{i//BATCH_SIZE + 1}"
        batch_symbols_map[batch_id] = batch
        
        thread = threading.Thread(target=run_ws, args=(batch, batch_id))
        thread.daemon = True
        thread.start()
        
        # Stagger connection attempts
        time.sleep(random.uniform(3, 6))

    expected_batches = (len(symbols) + BATCH_SIZE - 1) // BATCH_SIZE
    logger.info(f"[Bitget] All WebSocket threads started for {len(symbols)} symbols in {expected_batches} batches")

    try:
        while True:
            time.sleep(HEALTH_CHECK_INTERVAL)
            active_count = len(active_connections)
            
            if active_count < expected_batches:
                connection_ratio = active_count / expected_batches
                logger.warning(f"[Bitget] Health check: {active_count}/{expected_batches} connections active ({connection_ratio:.1%})")
                
                # If too many connections are down, restart failed batches
                if connection_ratio < 0.6 and time.time() - restart_timer > 300:
                    logger.info("[Bitget] Connection ratio too low, attempting batch restart")
                    restart_failed_batches()
                    restart_timer = time.time()
            else:
                logger.info(f"[Bitget] Health check: All {active_count} connections healthy")
                
    except KeyboardInterrupt:
        logger.info("[Bitget] Interrupted by user")
        # Clean shutdown
        for ws in active_connections.values():
            try:
                ws.close()
            except:
                pass