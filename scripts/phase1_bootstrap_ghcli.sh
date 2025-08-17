#!/usr/bin/env bash
set -euo pipefail

# Bootstrap Phase 1 using GitHub CLI auth instead of GH_PAT/curl.
# Requires: gh (authenticated with a user that has write access to the repo)

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI not found. Install from https://cli.github.com/" >&2
  exit 1
fi

OWNER=${OWNER:-Axion-inc}
REPO=${REPO:-DesktopAgent}
MILESTONE_NAME=${MILESTONE_NAME:-"Phase 1 — Hardening & Deterministic Execution"}
MILESTONE_DUE=${MILESTONE_DUE:-""}

echo "Checking gh auth..."
gh auth status >/dev/null

API_ROOT="repos/${OWNER}/${REPO}"

echo "Ensuring milestone: $MILESTONE_NAME"
# First try to find existing milestone
ms_number=$(gh api "$API_ROOT/milestones?state=all&per_page=100" --jq \
  ".[] | select(.title==\"$MILESTONE_NAME\") | .number" 2>/dev/null || true)

if [[ -z "${ms_number:-}" ]]; then
  # Create new milestone if it doesn't exist
  if [[ -n "$MILESTONE_DUE" ]]; then
    ms_number=$(gh api -X POST "$API_ROOT/milestones" \
      -f title="$MILESTONE_NAME" -f state=open -f due_on="$MILESTONE_DUE" --jq '.number' 2>/dev/null || true)
  else
    ms_number=$(gh api -X POST "$API_ROOT/milestones" \
      -f title="$MILESTONE_NAME" -f state=open --jq '.number' 2>/dev/null || true)
  fi
fi

if [[ -z "${ms_number:-}" ]]; then
  echo "Failed to ensure milestone via gh api" >&2
  exit 2
fi
echo "Milestone #$ms_number ensured"

cat > /tmp/labels_phase1.txt <<'LBL'
priority:P0:#d73a4a:Top priority
priority:P1:#fbca04:High priority
priority:P2:#0e8a16:Normal priority
area:dsl:#0366d6:DSL
area:replay:#0366d6:Replay UI
area:macos:#0366d6:macOS integration
area:metrics:#0366d6:Metrics/dashboard
area:recovery:#0366d6:Self-recovery
area:templates:#0366d6:Plan templates
area:ci:#0366d6:CI/CD
area:test:#0366d6:Testing
area:docs:#0366d6:Documentation
area:security:#0366d6:Security/PII
area:migration:#0366d6:Migration/compat
area:bip:#0366d6:Build in Public
type:tracker:#7057ff:Tracker issue
milestone:phase1:#5319e7:Phase 1 scope
LBL

echo "Ensuring labels..."
while IFS= read -r L; do
  NAME="${L%%:*}"
  REST="${L#*:}"
  COLOR="${REST##*:}"
  DESC="${REST%:*}"
  gh api -X POST "$API_ROOT/labels" -f name="$NAME" -f color="${COLOR#\#}" -f description="$DESC" >/dev/null 2>&1 || true
done < /tmp/labels_phase1.txt
echo "Labels ensured"

create_issue() {
  local title="$1"; shift
  local body="$1"; shift
  local labels_csv="$1"; shift
  # Convert comma-separated labels to array format
  local labels_json=$(python3 -c "import sys,json; print(json.dumps(sys.argv[1].split(',')))" "$labels_csv")
  # Escape quotes in title and body for JSON
  local title_escaped=$(python3 -c "import sys,json; print(json.dumps(sys.argv[1]))" "$title")
  local body_escaped=$(python3 -c "import sys,json; print(json.dumps(sys.argv[1]))" "$body")
  gh api -X POST "$API_ROOT/issues" \
    --input - <<EOF
{
  "title": $title_escaped,
  "body": $body_escaped,
  "labels": $labels_json,
  "milestone": $ms_number
}
EOF
}

tracker_title="Phase 1 — Hardening & Deterministic Execution"
tracker_body=$'Parent tracker\n- Goals: DSL 1.1 / Replay diff / Permission diagnostics / p95 & 7d / Clustering v0 / Self-recovery v0 / 3 templates / Nightly x50\n- Acceptance: Nightly 50 runs ≥45 success, Template 20 runs ≥19 success, Dashboard shows p95/7d/Top3'
create_issue "$tracker_title" "$tracker_body" "type:tracker,priority:P1"

declare -a TITLES=(
  "feat(dsl): v1.1 parser/validator/when"
  "feat(replay): timeline diff + failure summary"
  "feat(macos): permission diagnostics UI"
  "feat(metrics): /metrics schema + p95 + 7d"
  "feat(metrics): dashboard shows p95 and 7d"
  "feat(recovery): self-healing for find_files/move_to"
  "feat(templates): weekly_report.yaml v1.1"
  "feat(templates): weekly_report_split.yaml"
  "feat(templates): downloads_tidy.yaml"
  "ci(nightly): 50-run dry-run with metrics comment"
  "test(dsl): when/steps/static-validation cases"
  "test(pii): mask email/phone/path/name"
  "test(pdf): merge/extract"
  "docs: DSL 1.1 spec"
  "docs: permissions troubleshooting"
  "docs: /metrics schema"
  "security: ensure no external telemetry"
)

declare -a LABELS=(
  "area:dsl,priority:P1"
  "area:replay,priority:P1"
  "area:macos,priority:P1"
  "area:metrics,priority:P0"
  "area:metrics,priority:P1"
  "area:recovery,priority:P1"
  "area:templates,priority:P1"
  "area:templates,priority:P1"
  "area:templates,priority:P1"
  "area:ci,priority:P1,type:tracker"
  "area:test,priority:P1"
  "area:security,priority:P1"
  "area:test,priority:P1"
  "area:docs,priority:P1"
  "area:docs,priority:P1"
  "area:docs,priority:P1"
  "area:security,priority:P1"
)

declare -a BODIES=(
  $'DSL v1.1 implementation\n- Require dsl_version\n- when expressions with steps references\n- Static validation (no future refs/types)\n- Unit tests\nAcceptance: /plans/validate OK, unit tests green'
  $'Replay enhancements\n- Before/After diff per step\n- Failure summary card (cause/hints/retry link)\nAcceptance: visible on run_detail'
  $'Permission diagnostics UI (macOS)\n- Detect Screen Recording / Automation\n- Block and guide when missing\nAcceptance: /permissions and approval block'
  $'/metrics extension\n- success_rate/median/p95/Top3/7d\nAcceptance: schema returned is stable'
  $'Dashboard\n- Show p95 and 7d moving average\nAcceptance: visible at /public/dashboard'
  $'Self-recovery v0\n- move_to: auto-create output directory\n- find_files: widen one level once when 0 results\nAcceptance: recorded in replay'
  $'Template update\n- weekly_report.yaml to v1.1\nAcceptance: 20 runs ≥19 success'
  $'Template new weekly_report_split.yaml\nAcceptance: executes successfully'
  $'Template new downloads_tidy.yaml\nAcceptance: find→rename→move success'
  $'Nightly x50 (dry-run)\n- Post success/p95/Top3 to tracking issue\nAcceptance: comment is auto-posted'
  $'Tests: DSL when/steps/static validation\nAcceptance: pytest green'
  $'Tests: PII mask (email/phone/path/name)\nAcceptance: pytest green'
  $'Tests: PDF merge/extract\nAcceptance: pytest green'
  $'Docs: DSL 1.1 spec\nAcceptance: README/docs updated'
  $'Docs: permissions troubleshooting\nAcceptance: README updated'
  $'Docs: /metrics schema\nAcceptance: README updated'
  $'Security: disable telemetry\nAcceptance: no external sends'
)

for i in "${!TITLES[@]}"; do
  create_issue "${TITLES[$i]}" "${BODIES[$i]}" "${LABELS[$i]}"
done

echo "Milestone and issues created via gh."

