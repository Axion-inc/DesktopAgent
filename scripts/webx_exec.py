#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List

from app.web.engine import exec_batch


def build_batch(url: str, allow_hosts: List[str]) -> Dict[str, Any]:
    return {
        "guards": {
            "allowHosts": allow_hosts,
            "risk": ["sends"],
            "maxRetriesPerStep": 1,
        },
        "actions": [
            {"id": "a1", "type": "goto", "url": url},
            {"id": "a2", "type": "wait_for_text", "contains": "Example", "role": "heading", "timeoutMs": 8000},
        ],
        "evidence": {"screenshotEach": True, "domSchemaEach": True},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a WebX exec_batch to the Chrome extension via WS bridge")
    parser.add_argument("url", nargs="?", default="https://example.com", help="Target URL to open")
    parser.add_argument("--allow-host", dest="allow_hosts", action="append", default=["example.com"], help="Allowed host (repeatable)")
    parser.add_argument("--json", dest="json_path", help="Path to JSON file with batch payload")
    parser.add_argument("--timeout", type=float, default=30.0, help="Response timeout seconds")
    args = parser.parse_args()

    # Enable WS bridge
    os.environ.setdefault("WEBX_WS_BRIDGE_ENABLE", "1")
    os.environ.setdefault("WEBX_WS_TIMEOUT", str(args.timeout))

    if args.json_path:
        with open(args.json_path, "r") as f:
            payload = json.load(f)
    else:
        payload = build_batch(args.url, args.allow_hosts)

    res = exec_batch(payload.get("guards", {}), payload.get("actions", []), payload.get("evidence", {}))
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

