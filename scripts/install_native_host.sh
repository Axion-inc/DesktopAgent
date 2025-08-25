#!/bin/bash
# Desktop Agent WebX Extension Setup Script
# Installs Chrome extension and native messaging host

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
EXTENSION_DIR="webx-extension"
NATIVE_HOST_NAME="com.desktopagent.webx"
INSTALL_DIR="/usr/local/bin"
CONFIG_DIR="$HOME/.config/desktop-agent"

echo -e "${BLUE}🚀 Desktop Agent WebX Extension Setup${NC}"
echo "======================================="

# Check if Chrome is installed
if ! command -v google-chrome &> /dev/null && ! command -v chromium &> /dev/null; then
    echo -e "${RED}❌ Chrome or Chromium not found. Please install Chrome first.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Chrome browser found${NC}"

# Check if extension directory exists
if [ ! -d "$EXTENSION_DIR" ]; then
    echo -e "${RED}❌ Extension directory not found: $EXTENSION_DIR${NC}"
    echo "Please run this script from the Desktop Agent root directory."
    exit 1
fi

echo -e "${GREEN}✅ Extension directory found${NC}"

# Create configuration directory
mkdir -p "$CONFIG_DIR"

# Generate unique extension ID placeholder
EXTENSION_ID="abcdefghijklmnopqrstuvwxyzabcdef"
echo -e "${YELLOW}📝 Using extension ID: $EXTENSION_ID${NC}"
echo -e "${YELLOW}   (This will be replaced with the actual ID after installation)${NC}"

# Update extension ID in manifest and native host config
sed -i.bak "s/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/$EXTENSION_ID/g" "$EXTENSION_DIR/com.desktopagent.webx.json"
sed -i.bak "s/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/$EXTENSION_ID/g" "configs/web_engine.yaml"

echo -e "${GREEN}✅ Updated extension ID in configuration files${NC}"

# Create native messaging host executable
echo -e "${BLUE}📦 Creating native messaging host executable...${NC}"

cat > "/tmp/desktopagent-webx-host" << 'EOF'
#!/usr/bin/env python3
"""
Desktop Agent WebX Native Messaging Host
Entry point for Chrome extension communication
"""

import sys
import os
from pathlib import Path

# Add Desktop Agent to Python path
desktop_agent_path = Path(__file__).parent.parent / "lib" / "desktop-agent"
if desktop_agent_path.exists():
    sys.path.insert(0, str(desktop_agent_path))
else:
    # Try relative path from current working directory
    sys.path.insert(0, os.getcwd())

try:
    from app.web.native_host import main
    main()
except ImportError as e:
    import json
    import struct
    
    # Send error message in native messaging format
    error_msg = {
        "error": f"Failed to import Desktop Agent: {e}",
        "details": "Please check Desktop Agent installation"
    }
    
    message = json.dumps(error_msg).encode('utf-8')
    length = len(message)
    
    sys.stdout.buffer.write(struct.pack('<I', length))
    sys.stdout.buffer.write(message)
    sys.stdout.buffer.flush()
    
    sys.exit(1)
EOF

# Make executable and install
chmod +x "/tmp/desktopagent-webx-host"
sudo cp "/tmp/desktopagent-webx-host" "$INSTALL_DIR/"
rm "/tmp/desktopagent-webx-host"

echo -e "${GREEN}✅ Native messaging host installed to $INSTALL_DIR/desktopagent-webx-host${NC}"

# Update native host manifest path
sed -i.bak "s|/usr/local/bin/desktopagent-webx-host|$INSTALL_DIR/desktopagent-webx-host|g" "$EXTENSION_DIR/com.desktopagent.webx.json"

# Install native messaging host manifest
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    NATIVE_MESSAGING_DIR="$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts"
    mkdir -p "$NATIVE_MESSAGING_DIR"
    cp "$EXTENSION_DIR/com.desktopagent.webx.json" "$NATIVE_MESSAGING_DIR/"
    
    echo -e "${GREEN}✅ Native messaging host manifest installed (macOS)${NC}"
    echo -e "${BLUE}   Location: $NATIVE_MESSAGING_DIR/com.desktopagent.webx.json${NC}"
    
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    NATIVE_MESSAGING_DIR="$HOME/.config/google-chrome/NativeMessagingHosts"
    mkdir -p "$NATIVE_MESSAGING_DIR"
    cp "$EXTENSION_DIR/com.desktopagent.webx.json" "$NATIVE_MESSAGING_DIR/"
    
    echo -e "${GREEN}✅ Native messaging host manifest installed (Linux)${NC}"
    echo -e "${BLUE}   Location: $NATIVE_MESSAGING_DIR/com.desktopagent.webx.json${NC}"
    
else
    echo -e "${RED}❌ Unsupported operating system: $OSTYPE${NC}"
    exit 1
fi

# Generate handshake token
HANDSHAKE_TOKEN=$(openssl rand -hex 32)
echo -e "${YELLOW}🔐 Generated handshake token: $HANDSHAKE_TOKEN${NC}"

# Update configuration with token
sed -i.bak "s/change-me-in-production/$HANDSHAKE_TOKEN/g" "configs/web_engine.yaml"

echo -e "${GREEN}✅ Updated handshake token in configuration${NC}"

# Create installation summary
cat > "$CONFIG_DIR/webx-setup.json" << EOF
{
  "installation_date": "$(date -Iseconds)",
  "extension_id": "$EXTENSION_ID",
  "handshake_token": "$HANDSHAKE_TOKEN",
  "native_host_path": "$INSTALL_DIR/webx-native-host",
  "manifest_path": "$NATIVE_MESSAGING_DIR/com.desktopagent.webx.json"
}
EOF

echo -e "${GREEN}✅ Installation summary saved to $CONFIG_DIR/webx-setup.json${NC}"

# Instructions for manual extension installation
echo ""
echo -e "${BLUE}📋 Next Steps - Manual Extension Installation:${NC}"
echo ""
echo "1. Open Chrome and navigate to: chrome://extensions/"
echo "2. Enable 'Developer mode' (toggle in top right)"
echo "3. Click 'Load unpacked'"
echo "4. Select the extension directory: $(pwd)/$EXTENSION_DIR"
echo "5. Note the actual Extension ID that appears"
echo "6. Update configs/web_engine.yaml with the real Extension ID"
echo ""
echo -e "${YELLOW}⚠️  Important: The extension ID in the configuration is a placeholder.${NC}"
echo -e "${YELLOW}   You must replace it with the actual ID shown in Chrome after installation.${NC}"
echo ""
echo -e "${BLUE}🧪 Testing the Installation:${NC}"
echo ""
echo "1. Load the extension in Chrome"
echo "2. Open browser console (F12)"
echo "3. Look for 'Desktop Agent WebX installed' message"
echo "4. Run: python -m pytest tests/contract/test_webx_protocol.py"
echo ""
echo -e "${GREEN}🎉 Setup complete! Follow the manual steps above to finish installation.${NC}"

# Test native messaging host
echo ""
echo -e "${BLUE}🔧 Testing native messaging host...${NC}"

if echo '{"method":"handshake","params":{"extension_id":"test","version":"1.0.0"},"id":1}' | python3 "$INSTALL_DIR/desktopagent-webx-host" 2>/dev/null | head -c 100 >/dev/null; then
    echo -e "${GREEN}✅ Native messaging host is responding${NC}"
else
    echo -e "${YELLOW}⚠️  Native messaging host test failed - this is normal if Desktop Agent is not in PATH${NC}"
    echo -e "${YELLOW}   Make sure to run from Desktop Agent directory or install Desktop Agent properly${NC}"
fi

echo ""
echo -e "${GREEN}Setup script completed successfully!${NC}"