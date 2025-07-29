import websocket
import json
import gzip
import ssl
import certifi
import threading
import time
import logging
import random
from app.utils import TICKERS_SYMBOL

# Enhanced URI list with more fallback options
HUOBI_WEBSOCKET_URIS = [
    "wss://api.huobi.pro/ws",
    "wss://api.huobi.vn/ws",
    "wss://api.huobi.so/ws",
    "wss://api-aws.huobi.pro/ws",  # Additional fallbacks
    "wss://api.hbdm.com/ws"
]

BATCH_SIZE = 25  # Further reduced for better stability
MAX_RECONNECT_ATTEMPTS = 5  # Increased attempts
INITIAL_RECONNECT_DELAY = 10  # Longer initial delay
PING_INTERVAL = 30
PING_TIMEOUT = 10
HEALTH_CHECK_INTERVAL = 120  # Check every 2 minutes
BATCH_RESTART_THRESHOLD = 0.6  # Restart if less than 60% batches active

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("huobi-client")
confirmed_symbols = set()

def start_multi(callback, symbols=TICKERS_SYMBOL):
    last_prices = {}
    active_connections = {}
    reconnect_attempts = {}
    failed_batches = set()
    batch_symbols_map = {}  # Store symbols for each batch
    restart_timer = time.time()

    def get_current_timestamp():
        return int(time.time() * 1000)
    
    def check_network_connectivity():
        """Simple connectivity check"""
        import socket
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except:
            return False

    def process_message(data, updated_symbols):
        try:
            if 'ping' in data:
                return json.dumps({"pong": data['ping']})

            if 'tick' in data and 'ch' in data:
                ch = data['ch']
                tick = data['tick']
                price = tick.get('close', 0)
                symbol_ = ch.split('.')[1].upper()

                if symbol_ not in confirmed_symbols:
                    confirmed_symbols.add(symbol_)
                    # logger.info(f"[Huobi] ✅ Data received for: {symbol_}")

                if last_prices.get(symbol_) != price:
                    last_prices[symbol_] = price
                    updated_symbols.append({
                        "symbol": symbol_,
                        "price": price
                    })
        except Exception as e:
            logger.error(f"[Huobi] Error processing message: {e}")
        return None

    def run_ws(symbol_batch, batch_id=None, uri_index=0, attempt=0):
        if batch_id is None:
            batch_id = f"batch_{hash(tuple(symbol_batch)) % 10000}"
        
        # Exponential backoff for reconnections
        if attempt > 0:
            delay = min(INITIAL_RECONNECT_DELAY * (2 ** (attempt - 1)), 60)  # Max 60 seconds
            logger.info(f"[Huobi] Reconnecting batch {batch_id} in {delay}s (attempt {attempt})")
            time.sleep(delay)

        # Cycle through URIs if previous ones failed
        if uri_index >= len(HUOBI_WEBSOCKET_URIS):
            uri_index = 0

        uri = HUOBI_WEBSOCKET_URIS[uri_index]

        def on_message(ws, message):
            try:
                if isinstance(message, bytes):
                    message = gzip.decompress(message).decode("utf-8")
                data = json.loads(message)
                updated = []
                pong = process_message(data, updated)
                if pong:
                    ws.send(pong)
                if updated:
                    callback({
                        "exchange": "Huobi",
                        "data": updated
                    })
            except Exception as e:
                logger.error(f"[Huobi] Message processing error: {e}")

        def on_open(ws):
            logger.info(f"[Huobi] Connected batch {batch_id} to {uri} with {len(symbol_batch)} symbols")
            active_connections[batch_id] = ws
            reconnect_attempts[batch_id] = 0
            
            # Subscribe with small delays to avoid rate limiting
            for i, symbol in enumerate(symbol_batch):
                try:
                    sub_msg = json.dumps({
                        "sub": f"market.{symbol.lower()}.ticker",
                        "id": f"sub_{symbol}_{get_current_timestamp()}"
                    })
                    ws.send(sub_msg)
                    
                    # Small delay every 10 subscriptions
                    if i > 0 and i % 10 == 0:
                        time.sleep(0.1)
                        
                except Exception as e:
                    logger.error(f"[Huobi] Failed to subscribe to {symbol}: {e}")

        def on_error(ws, error):
            logger.error(f"[Huobi] Error in batch {batch_id}: {error}")
            if batch_id in active_connections:
                del active_connections[batch_id]
            try_reconnect()

        def on_close(ws, code, msg):
            logger.warning(f"[Huobi] Closed batch {batch_id}: {code} - {msg}")
            if batch_id in active_connections:
                del active_connections[batch_id]
            try_reconnect()

        def try_reconnect():
            current_attempt = reconnect_attempts.get(batch_id, 0)
            
            if current_attempt >= MAX_RECONNECT_ATTEMPTS:
                logger.error(f"[Huobi] Max reconnection attempts reached for batch {batch_id}")
                failed_batches.add(batch_id)
                return
            
            reconnect_attempts[batch_id] = current_attempt + 1
            
            # Check network connectivity before attempting reconnection
            if not check_network_connectivity():
                logger.warning(f"[Huobi] Network connectivity issue detected, waiting longer for batch {batch_id}")
                time.sleep(30)  # Wait longer if network issues
            
            # Try next URI or restart from first URI
            next_uri_index = (uri_index + 1) % len(HUOBI_WEBSOCKET_URIS)
            
            def reconnect_thread():
                run_ws(symbol_batch, batch_id, next_uri_index, current_attempt + 1)
            
            thread = threading.Thread(target=reconnect_thread)
            thread.daemon = True
            thread.start()

        try:
            # Add random delay to avoid overwhelming the server
            if attempt > 0:
                time.sleep(random.uniform(2.0, 5.0))  # Longer delays for reconnects
            
            # Check network before attempting connection
            if not check_network_connectivity():
                logger.warning(f"[Huobi] Network connectivity issue, skipping connection attempt for batch {batch_id}")
                time.sleep(60)  # Wait 1 minute before retry
                try_reconnect()
                return
            
            ws = websocket.WebSocketApp(
                uri,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            
            # Enhanced SSL and connection options
            ws.run_forever(
                sslopt={
                    "cert_reqs": ssl.CERT_NONE,  # Less strict SSL for better compatibility
                    "ca_certs": certifi.where()
                },
                ping_interval=PING_INTERVAL,
                ping_timeout=PING_TIMEOUT,
                origin="https://www.huobi.com",
                host="api.huobi.pro",
                # timeout=30  # Add connection timeout
            )
            
        except Exception as e:
            logger.error(f"[Huobi] WebSocket thread crash for batch {batch_id}: {e}")
            try_reconnect()

    def restart_failed_batches():
        """Restart failed batches periodically"""
        if not failed_batches:
            return
            
        logger.info(f"[Huobi] Attempting to restart {len(failed_batches)} failed batches")
        batches_to_restart = list(failed_batches)
        failed_batches.clear()
        
        for batch_id in batches_to_restart:
            if batch_id in batch_symbols_map:
                symbol_batch = batch_symbols_map[batch_id]
                reconnect_attempts[batch_id] = 0  # Reset attempts
                
                def restart_thread():
                    time.sleep(random.uniform(5, 15))  # Stagger restarts
                    run_ws(symbol_batch, batch_id, 0, 0)
                
                thread = threading.Thread(target=restart_thread)
                thread.daemon = True
                thread.start()
                
                time.sleep(2)  # Small delay between restart attempts

    # Split symbols into batches and start connections
    for i in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[i:i + BATCH_SIZE]
        batch_id = f"batch_{i//BATCH_SIZE + 1}"
        batch_symbols_map[batch_id] = batch  # Store for potential restarts
        
        thread = threading.Thread(target=run_ws, args=(batch, batch_id))
        thread.daemon = True
        thread.start()
        
        # Longer stagger for initial connections
        time.sleep(random.uniform(3, 6))

    expected_batches = (len(symbols) + BATCH_SIZE - 1) // BATCH_SIZE
    logger.info(f"[Huobi] All WebSocket threads started for {len(symbols)} symbols in {expected_batches} batches")

    try:
        while True:
            # Health check with adaptive interval
            time.sleep(HEALTH_CHECK_INTERVAL)
            active_count = len(active_connections)
            
            if active_count < expected_batches:
                connection_ratio = active_count / expected_batches
                logger.warning(f"[Huobi] Health check: {active_count}/{expected_batches} connections active ({connection_ratio:.1%})")
                
                # If too many connections are down, attempt to restart failed batches
                if connection_ratio < BATCH_RESTART_THRESHOLD and time.time() - restart_timer > 300:  # 5 minutes
                    logger.info("[Huobi] Connection ratio too low, attempting batch restart")
                    restart_failed_batches()
                    restart_timer = time.time()
            else:
                logger.info(f"[Huobi] Health check: All {active_count} connections healthy")
                
    except KeyboardInterrupt:
        logger.info("[Huobi] Interrupted by user")
        # Clean shutdown
        for ws in active_connections.values():
            try:
                ws.close()
            except:
                pass