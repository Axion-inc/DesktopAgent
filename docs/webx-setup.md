# Desktop Agent WebX Setup Guide

## Phase 5: Chrome Extension + Native Messaging Implementation

This guide covers the setup and configuration of the WebX system for stable, high-performance web automation with Chrome Extension and Native Messaging.

## Overview

The WebX system provides:
- **Chrome Extension**: Manifest v3 extension for DOM manipulation
- **Native Messaging Host**: Python service for extension communication  
- **Engine Abstraction**: Unified API supporting both Extension and Playwright engines
- **Backward Compatibility**: Existing DSL templates work unchanged
- **Security**: Explicit permissions, approval gates, and data masking

## Prerequisites

### System Requirements
- **macOS**: Version 10.15+ (Catalina or later)
- **Chrome**: Version 88+ 
- **Python**: 3.8+
- **Desktop Agent**: Installed and configured

### Required Permissions
- **Screen Recording**: For screenshot capture (macOS System Preferences > Security & Privacy)
- **Accessibility**: For OS-level automation fallbacks

## Installation

### 1. Automated Setup

Run the installation script from the Desktop Agent root directory:

```bash
./scripts/install_native_host.sh
```

This script will:
- ✅ Create native messaging host executable
- ✅ Install host manifest to Chrome's native messaging directory  
- ✅ Generate handshake token for authentication
- ✅ Update configuration files with extension placeholders
- ✅ Test native messaging host connectivity

### 2. Manual Chrome Extension Installation

After running the setup script:

1. **Open Chrome Extensions**
   - Navigate to `chrome://extensions/`
   - Enable "Developer mode" (toggle in top right)

2. **Load Extension**
   - Click "Load unpacked"
   - Select the `webx-extension/` directory from Desktop Agent root
   - Note the **Extension ID** that appears (e.g., `abcdefghijklmnopqrstuvwxyzabcdef`)

3. **Update Configuration**
   - Open `configs/web_engine.yaml`
   - Replace `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` with the actual Extension ID
   - Save the file

### 3. Verify Installation

Test the complete setup:

```bash
# Test native messaging host
echo '{"method":"handshake","params":{"extension_id":"test","version":"1.0.0"},"id":1}' | \
  /usr/local/bin/desktopagent-webx-host

# Run contract tests
python -m pytest tests/contract/test_webx_protocol.py -v

# Test web engine integration  
python -c "from app.web.engine import get_web_engine; print(get_web_engine().__class__.__name__)"
```

## Configuration

### Web Engine Settings

The `configs/web_engine.yaml` file controls WebX behavior:

```yaml
# Engine selection
engine: "extension"  # or "playwright"

# Extension configuration
extension:
  id: "your_actual_extension_id_here"
  native_host: "com.desktopagent.webx" 
  handshake_token: "generated_during_setup"
  timeout_ms: 15000
  enable_debugger_upload: false  # Enable only if file uploads needed

# Common settings
common:
  screenshot:
    quality: 80
    format: "png"
  security:
    mask_sensitive_data: true
    require_approval_for_destructive: true
```

### Extension Permissions

The WebX extension requests minimal permissions:

**Required Always:**
- `nativeMessaging` - Communication with Desktop Agent
- `activeTab` - Access to current tab content
- `scripting` - DOM manipulation via content scripts  
- `storage` - Extension configuration storage
- `downloads` - Download monitoring

**Optional (on-demand):**
- `debugger` - File upload support (only when `enable_debugger_upload: true`)

### Security Configuration

Update security settings in `web_engine.yaml`:

```yaml
common:
  security:
    # Sensitive field patterns for data masking
    sensitive_patterns:
      - "password"
      - "credit"  
      - "ssn"
      - "token"
    
    # Destructive action keywords requiring approval
    destructive_keywords:
      - "delete"
      - "cancel"
      - "logout" 
      - "unsubscribe"
```

## Usage

### Basic DSL Usage

Existing templates work unchanged with the extension engine:

```python
# Navigate to page
open_browser("https://example.com", engine="extension")

# Fill form fields (supports Japanese labels)
fill_by_label("氏名", "山田太郎")  
fill_by_label("メール", "yamada@example.com")

# Click buttons/links
click_by_text("送信")

# Upload files (requires debugger permission)
upload_file("/path/to/document.pdf", label="ファイル選択")

# Wait for elements
wait_for_element(selector="#success-message")

# Capture DOM schema
capture_screen_schema(where="web")

# Take screenshots
take_screenshot()
```

### Engine Selection

Choose engine per operation or globally:

```python
# Use extension engine for this operation
open_browser("https://form.example.com", engine="extension")

# Use playwright engine for this operation  
open_browser("https://complex.example.com", engine="playwright")

# Set global default
from app.web.engine import set_web_engine_type
set_web_engine_type("extension")
```

### Advanced Configuration

For complex scenarios, configure engine-specific options:

```python
# Extension engine with custom timeout
result = fill_by_label("field", "value", timeout_ms=20000)

# Handle permission requirements
if result.get("error") == "Permission denied":
    # Enable debugger permission in config
    # Then retry operation
    pass
```

## Troubleshooting

### Common Issues

#### 1. Extension Not Loading
```
Error: Extension failed to load
```
**Solution:**
- Verify Chrome Developer Mode is enabled
- Check extension directory path is correct
- Ensure manifest.json is valid
- Restart Chrome

#### 2. Native Messaging Connection Failed
```  
Error: Native messaging host disconnected
```
**Solution:**
- Run installation script again: `./scripts/install_native_host.sh`
- Check host manifest path: `~/Library/Application Support/Google/Chrome/NativeMessagingHosts/com.desktopagent.webx.json`
- Verify executable permissions: `ls -la /usr/local/bin/desktopagent-webx-host`
- Test host manually: `echo '{"method":"handshake","id":1}' | /usr/local/bin/desktopagent-webx-host`

#### 3. Extension ID Mismatch
```
Error: Extension not authorized  
```
**Solution:**
- Get actual extension ID from `chrome://extensions/`
- Update `configs/web_engine.yaml` with correct ID
- Update `webx-extension/com.desktopagent.webx.json` with correct ID
- Restart Desktop Agent

#### 4. File Upload Fails
```
Error: Permission denied for file upload
```
**Solution:**
- Set `enable_debugger_upload: true` in config
- Reload extension in Chrome
- Grant debugger permission when prompted
- Consider security implications of debugger access

#### 5. Element Not Found
```
Error: Element not found: label='フィールド名'
```
**Solution:**
- Verify label text matches exactly (case-sensitive)
- Check element is visible and interactable
- Try CSS selector instead: `selector="input[name='field']"`
- Use browser dev tools to inspect element structure

### Debug Mode

Enable verbose logging for debugging:

```yaml
# In configs/web_engine.yaml
development:
  verbose_logging: true
  debug_artifacts: true
```

Then check logs:
```bash
tail -f /tmp/webx_native_host.log
```

### Performance Monitoring

Monitor WebX metrics via the dashboard or API:

```bash
# Check metrics
curl http://localhost:8000/metrics | jq '.webx_engine_share_24h'

# Expected output:
# {
#   "extension": 0.85,
#   "playwright": 0.15  
# }
```

## Best Practices

### 1. Engine Selection Strategy
- **Extension Engine**: Fast, lightweight, good for simple forms
- **Playwright Engine**: More robust, better for complex SPAs

### 2. Permission Management
- Keep `enable_debugger_upload: false` unless file uploads needed
- Review destructive action approvals regularly
- Monitor sensitive data masking in logs

### 3. Error Handling
```python
result = fill_by_label("field", "value")
if result.get("status") == "error":
    # Log error details
    logger.error(f"Fill failed: {result.get('error')}")
    
    # Fallback to playwright engine
    result = fill_by_label("field", "value", engine="playwright")
```

### 4. Testing
```bash
# Run all WebX tests
python -m pytest tests/contract/test_webx_protocol.py tests/unit/test_webx_labeling.py -v

# Run E2E tests (requires Chrome with extension)  
npx playwright test tests/e2e/test_webx_form.spec.ts
```

## Security Considerations

### Data Protection
- Sensitive form data is masked in logs automatically
- Screenshots exclude sensitive regions when possible
- Native messaging uses token-based authentication

### Permission Model  
- Extension requests minimal required permissions
- Debugger permission only requested when needed
- All destructive actions require explicit approval

### Network Security
- Extension only communicates with native host (no external network)
- Native messaging uses local stdio protocol
- No data transmitted to external services

## Migration from Playwright

Existing templates require no code changes:

```python
# This works with both engines
open_browser("https://app.example.com")
fill_by_label("ユーザー名", "test_user")
click_by_text("ログイン") 
```

Configure engine preference in `configs/web_engine.yaml`:

```yaml
engine: "extension"  # Default to extension engine

# Fallback configuration
common:
  fallback_to_playwright: true  # Auto-fallback on extension errors
  fallback_timeout_ms: 5000
```

## Support

For issues and questions:

1. **Check logs**: `/tmp/webx_native_host.log`
2. **Run diagnostics**: `./scripts/install_native_host.sh` (re-run for health check)
3. **Test components**: `python -m pytest tests/contract/test_webx_protocol.py -v`
4. **Review metrics**: Visit dashboard WebX metrics section

The WebX system is designed for high reliability with graceful fallbacks. Most issues can be resolved by re-running the setup script or adjusting configuration settings.