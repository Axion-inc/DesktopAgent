#!/usr/bin/env bash
set -euo pipefail

REMOTE_URL=${1:-}
if [ -z "$REMOTE_URL" ]; then
  echo "Usage: $0 <git-remote-url>"
  echo "Example: $0 https://github.com/Axion-inc/DesktopAgent.git"
  exit 1
fi

git init
git branch -M main || true
git add .
git commit -m "feat: initial MVP M0 (macOS) with DSL, actions, adapters, FastAPI, tests, CI"
git remote remove origin 2>/dev/null || true
git remote add origin "$REMOTE_URL"
echo "Now push with: git push -u origin main"

