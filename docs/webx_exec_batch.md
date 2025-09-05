# WebX Exec Batch (DOM-first with CDP fallback)

This document describes the batch JSON used to drive Chrome extension execution from the Desktop Agent.

## Guards
- `allowHosts`: list of hostnames allowed to operate on (suffix match)
- `risk`: string tags for auditable operations (e.g. `sends`)
- `maxRetriesPerStep`: per-step retry count on failure

## Actions (examples)
- `goto { url }`
- `fill_by_label { label | selector, text, frame? }`
- `click_by_text { text | selector, role?, frame? }`
- `wait_for_text { contains, role?, timeoutMs?, frame? }`
- `frame_select { frame: { selector | index } }`
- `frame_clear`
- `pierce_shadow` (no-op toggle; deep traversal is default)
- `precise_click { x, y }` (CDP)
- `insert_text { text }` (CDP)
- `set_file_input_files { selector, files }` (CDP)
- `download_file { url, filename? }`
- `wait_for_download { url?, filename?, timeoutMs? }`
- `assert_file_exists { url?, filename? }`
- `get_cookie { name, url? | (domain,path) }`
- `set_cookie { name, value, url? | (domain,path), expirationDate? }`
- `get_storage { key? }`
- `set_storage { key, value }`

## Evidence
- `screenshotEach`: capture screenshot after each step
- `domSchemaEach`: capture simplified DOM schema after each step

## Schema
See `schemas/webx_exec_batch.schema.json` for a machine-readable JSON Schema.

## Transports
- Dev default: WebSocket bridge (`ws://127.0.0.1:8765`)
  - App: set `WEBX_WS_BRIDGE_ENABLE=1` (or `WEBX_TRANSPORT=ws`)
- Optional: Native Messaging bridge (extension <-> host)
  - Host stub script: `scripts/webx_native_host.py`
  - Install host manifest: `webx-extension/com.desktopagent.webx.json` (update `path` and extension ID)

## Local Test
```bash
export WEBX_WS_BRIDGE_ENABLE=1
python scripts/webx_exec.py  # or provide --json PATH
```

