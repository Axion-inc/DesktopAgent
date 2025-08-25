#!/bin/bash
# Phase 4 Example: RBAC Setup Script
# 初期ユーザーと権限を設定するスクリプト

set -e

BASE_URL="http://localhost:8000"
ADMIN_USER="admin"
ADMIN_PASS="admin"

echo "🚀 Desktop Agent Phase 4 - RBAC Setup"
echo "======================================"

# Function to make authenticated API calls
api_call() {
    local method=$1
    local endpoint=$2
    local data=$3
    
    if [ -n "$data" ]; then
        curl -s -X "$method" "$BASE_URL$endpoint" \
             -u "$ADMIN_USER:$ADMIN_PASS" \
             -H "Content-Type: application/json" \
             -d "$data"
    else
        curl -s -X "$method" "$BASE_URL$endpoint" \
             -u "$ADMIN_USER:$ADMIN_PASS"
    fi
}

# Check if server is running
echo "🔍 Checking server status..."
if ! curl -s "$BASE_URL/healthz" > /dev/null; then
    echo "❌ Server is not running at $BASE_URL"
    echo "   Start with: uvicorn app.main:app --reload"
    exit 1
fi
echo "✅ Server is running"

# Create users
echo ""
echo "👥 Creating users..."

# Project Manager (Editor role)
echo "  📝 Creating Project Manager..."
api_call POST "/api/admin/users" '{
    "username": "project_manager",
    "password": "secure_pm_pass",
    "active": true
}' > /dev/null
echo "  ✅ project_manager created (Editor permissions)"

# Automation Runner (Runner role)  
echo "  🤖 Creating Automation Runner..."
api_call POST "/api/admin/users" '{
    "username": "automation_runner", 
    "password": "secure_runner_pass",
    "active": true
}' > /dev/null
echo "  ✅ automation_runner created (Runner permissions)"

# Report Viewer (Viewer role)
echo "  👀 Creating Report Viewer..."
api_call POST "/api/admin/users" '{
    "username": "report_viewer",
    "password": "secure_viewer_pass", 
    "active": true
}' > /dev/null
echo "  ✅ report_viewer created (Viewer permissions)"

# List created users
echo ""
echo "📋 Created users:"
api_call GET "/api/admin/users" | jq -r '.users[] | "  • \(.username) - \(.active | if . then "Active" else "Inactive" end)"'

# Show example API calls
echo ""
echo "🔧 Example API Usage:"
echo ""
echo "# List runs (any authenticated user)"
echo "curl -u report_viewer:secure_viewer_pass $BASE_URL/api/runs"
echo ""
echo "# Pause run (requires Editor+)"  
echo "curl -X POST -u project_manager:secure_pm_pass $BASE_URL/api/runs/123/pause"
echo ""
echo "# Admin operations (requires Admin)"
echo "curl -u admin:admin $BASE_URL/api/admin/audit"
echo ""
echo "# HITL Approval page"
echo "open $BASE_URL/hitl/approve/{run_id}"
echo ""
echo "✅ RBAC setup completed!"
echo "📖 See docs/operations.md for detailed usage information"