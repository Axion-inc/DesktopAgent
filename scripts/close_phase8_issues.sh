#!/usr/bin/env bash
set -euo pipefail

# Close all open GitHub issues for Phase 8 in the target repo.
# Requirements:
#  - gh CLI installed and authenticated (`gh auth status`)
#  - Network access
#
# Usage:
#  REPO=Axion-inc/DesktopAgent ./scripts/close_phase8_issues.sh
#  REPO=Axion-inc/DesktopAgent MILESTONE="Phase 8 — Planner/Navigator + LLM Draft + LangGraph" ./scripts/close_phase8_issues.sh --yes
#  REPO=Axion-inc/DesktopAgent ./scripts/close_phase8_issues.sh --label-only --yes

REPO=${REPO:-"Axion-inc/DesktopAgent"}
MILESTONE=${MILESTONE:-"Phase 8 — Planner/Navigator + LLM Draft + LangGraph"}
COMMENT=${COMMENT:-"Phase 8 complete. Closing tracked issues."}
LABEL_ONLY=false
YES=false

for arg in "$@"; do
  case "$arg" in
    --yes|-y) YES=true ;;
    --label-only) LABEL_ONLY=true ;;
    --repo=*) REPO="${arg#*=}" ;;
    --milestone=*) MILESTONE="${arg#*=}" ;;
    --comment=*) COMMENT="${arg#*=}" ;;
  esac
done

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI not found. Install GitHub CLI first: https://cli.github.com/" >&2
  exit 1
fi

echo "Repo:        $REPO"
echo "Milestone:   $MILESTONE"
echo "Label-only:  $LABEL_ONLY"

if [ "$LABEL_ONLY" = true ]; then
  # Fallback: close by label if milestone is not used
  echo "Listing open issues with label 'milestone:phase8'..."
  issues_json=$(gh issue list -R "$REPO" -s open -l "milestone:phase8" --json number,title,url || true)
else
  echo "Listing open issues in milestone..."
  issues_json=$(gh issue list -R "$REPO" -s open --milestone "$MILESTONE" --json number,title,url || true)
fi

count=$(printf "%s" "$issues_json" | jq 'length')
if [ "$count" -eq 0 ]; then
  echo "No open issues to close."
  exit 0
fi

echo "Found $count open issues:"
printf "%s" "$issues_json" | jq -r '.[] | "#\(.number) \(.title) (\(.url))"'

if [ "$YES" != true ]; then
  read -r -p "Close all of the above issues? [y/N] " ans
  case "$ans" in
    [yY][eE][sS]|[yY]) ;;
    *) echo "Aborted." ; exit 1 ;;
  esac
fi

for num in $(printf "%s" "$issues_json" | jq -r '.[].number'); do
  echo "Closing #$num ..."
  gh issue close "$num" -R "$REPO" -c "$COMMENT"
done

echo "Done."

