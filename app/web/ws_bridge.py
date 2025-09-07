from __future__ import annotations

import asyncio
import json
import threading
from typing import Any, Dict, Optional

_bridge_loop: Optional[asyncio.AbstractEventLoop] = None
_bridge_thread: Optional[threading.Thread] = None
_clients: set = set()
_pending: Dict[str, asyncio.Future] = {}


def _ensure_loop() -> asyncio.AbstractEventLoop:
    global _bridge_loop, _bridge_thread
    if _bridge_loop and _bridge_loop.is_running():
        return _bridge_loop

    _bridge_loop = asyncio.new_event_loop()

    def runner(loop: asyncio.AbstractEventLoop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    _bridge_thread = threading.Thread(target=runner, args=(_bridge_loop,), daemon=True)
    _bridge_thread.start()
    return _bridge_loop


async def _ws_handler(websocket):  # type: ignore
    _clients.add(websocket)
    try:
        async for message in websocket:  # type: ignore
            try:
                data = json.loads(message)
            except Exception:
                continue
            # Response frame: { id, result } expected
            if isinstance(data, dict) and 'id' in data:
                fut = _pending.pop(str(data['id']), None)
                if fut and not fut.cancelled():
                    fut.set_result(data.get('result'))
    finally:
        _clients.discard(websocket)


def start(host: str = '127.0.0.1', port: int = 8765) -> None:
    try:
        import websockets  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        return

    loop = _ensure_loop()

    async def _start():
        server = await websockets.serve(_ws_handler, host, port, ping_interval=20, ping_timeout=20)  # type: ignore
        return server

    # Start server lazily; ignore if already bound
    asyncio.run_coroutine_threadsafe(_start(), loop)


def is_connected() -> bool:
    return len(_clients) > 0


def send_request(method: str, params: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
    """Send a JSON-RPC like request to any connected client and wait for response.

    Returns the result payload or raises TimeoutError.
    """
    loop = _ensure_loop()
    if not _clients:
        raise RuntimeError('No WebX extension client connected')

    req_id = str(id(params))
    fut: asyncio.Future = asyncio.Future()
    _pending[req_id] = fut

    async def _send():
        frame = json.dumps({'id': req_id, 'method': method, 'params': params})
        # Broadcast to all clients; any can respond
        for ws in list(_clients):
            try:
                await ws.send(frame)  # type: ignore
            except Exception:
                pass

    asyncio.run_coroutine_threadsafe(_send(), loop)

    try:
        return asyncio.run_coroutine_threadsafe(asyncio.wait_for(fut, timeout), loop).result()
    except Exception as e:
        _pending.pop(req_id, None)
        raise TimeoutError(str(e))

