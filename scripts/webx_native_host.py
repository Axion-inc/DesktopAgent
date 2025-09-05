#!/usr/bin/env python3
from __future__ import annotations

import sys
import struct
import json
import threading
import queue
from typing import Any, Dict

# Minimal Native Messaging host that echoes and supports webx.exec_batch passthrough

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


def handle_message(msg: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(msg, dict):
        return {"error": "invalid message"}
    if msg.get('method') == 'webx.ping':
        return {"pong": True}
    # For webx.exec_batch, this host currently does not execute; it is a placeholder.
    # Real deployments can forward to a local service or app.
    return {"ok": True}


def main() -> int:
    try:
        while True:
            msg = read_message()
            if msg is None:
                break
            result = handle_message(msg)
            out = {"id": msg.get('id'), "result": result}
            with send_lock:
                send_message(out)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

