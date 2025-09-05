#!/usr/bin/env python3
from __future__ import annotations

import sys
import struct
import json
import threading
import asyncio
from typing import Any, Dict

send_lock = threading.Lock()


def send_message(msg: Dict[str, Any]) -> None:
    data = json.dumps(msg).encode('utf-8')
    sys.stdout.buffer.write(struct.pack('<I', len(data)))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def read_message() -> Dict[str, Any] | None:
    raw_length = sys.stdin.buffer.read(4)
    if not raw_length:
        return None
    (length,) = struct.unpack('<I', raw_length)
    data = sys.stdin.buffer.read(length)
    if not data:
        return None
    try:
        return json.loads(data.decode('utf-8'))
    except Exception:
        return None


async def bridge_loop(ws_url: str = 'ws://127.0.0.1:8765') -> None:
    try:
        import websockets  # type: ignore
    except Exception:
        # Fallback: echo only
        while True:
            msg = read_message()
            if msg is None:
                break
            out = {"id": msg.get('id'), "result": {"ok": True}}
            with send_lock:
                send_message(out)
        return

    async with websockets.connect(ws_url) as ws:  # type: ignore
        await ws.send(json.dumps({"type": "hello", "role": "native_host"}))

        async def stdin_reader():
            loop = asyncio.get_event_loop()
            while True:
                msg = await loop.run_in_executor(None, read_message)
                if msg is None:
                    break
                await ws.send(json.dumps(msg))

        async def ws_reader():
            async for data in ws:
                try:
                    obj = json.loads(data)
                except Exception:
                    continue
                with send_lock:
                    send_message(obj)

        await asyncio.gather(stdin_reader(), ws_reader())


def main() -> int:
    try:
        asyncio.run(bridge_loop())
    except KeyboardInterrupt:
        pass
    except Exception:
        # On failure, fall back to echo
        try:
            while True:
                msg = read_message()
                if msg is None:
                    break
                out = {"id": msg.get('id'), "result": {"ok": True}}
                with send_lock:
                    send_message(out)
        except Exception:
            pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
