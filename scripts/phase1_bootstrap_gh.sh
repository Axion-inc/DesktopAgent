#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   export OWNER=Axion-inc REPO=DesktopAgent GH_PAT=... \
#   MILESTONE_NAME="Phase 1 — Hardening & 決定的実行の底上げ" MILESTONE_DUE="2025-09-30T00:00:00Z" \
#   && bash scripts/phase1_bootstrap_gh.sh

if [[ -z "${OWNER:-}" || -z "${REPO:-}" || -z "${GH_PAT:-}" ]]; then
  echo "OWNER/REPO/GH_PAT must be set" >&2
  exit 1
fi

API="https://api.github.com/repos/${OWNER}/${REPO}"
AUTH=(-H "Authorization: token ${GH_PAT}" -H "Accept: application/vnd.github+json" -H "Content-Type: application/json")

MILESTONE_NAME=${MILESTONE_NAME:-"Phase 1 — Hardening & Deterministic Execution"}
MILESTONE_DUE=${MILESTONE_DUE:-""}

# 1) Create or fetch Milestone
create_milestone_payload() {
  if [[ -n "$MILESTONE_DUE" ]]; then
    printf '{"title":"%s","state":"open","due_on":"%s"}' "$MILESTONE_NAME" "$MILESTONE_DUE"
  else
    printf '{"title":"%s","state":"open"}' "$MILESTONE_NAME"
  fi
}

echo "Ensuring milestone: $MILESTONE_NAME"
# Try create milestone
resp=$(curl -sS "${AUTH[@]}" -X POST "$API/milestones" -d "$(create_milestone_payload)" || true)
if [ -n "$resp" ] && echo "$resp" | grep -q '"number"'; then
  milestone_number=$(python - <<'PY'
import json,sys
print(json.load(sys.stdin).get('number'))
PY
<<<"$resp")
else
  # Fallback: list and find by title
  list=$(curl -sS "${AUTH[@]}" "$API/milestones?state=all&per_page=100" || true)
  if [ -z "$list" ]; then
    echo "GitHub API call returned empty response. Check GH_PAT scope/network. Body from create attempt:" >&2
    echo "$resp" >&2
    exit 2
  fi
  milestone_number=$(python - <<PY
import json,sys,os
name=os.environ.get('MILESTONE_NAME')
try:
    data=json.loads(sys.stdin.read() or '[]')
except Exception:
    print('')
    raise
for m in data:
    if m.get('title')==name:
        print(m.get('number'))
        break
PY
<<<"$list")
fi
if [[ -z "${milestone_number:-}" ]]; then
  echo "Failed to ensure milestone. Response from create:" >&2
  echo "$resp" >&2
  exit 2
fi
echo "Milestone #$milestone_number ensured"

# 2) Ensure labels
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

while IFS= read -r L; do
  NAME="${L%%:*}"
  REST="${L#*:}"
  COLOR="${REST##*:}"
  DESC="${REST%:*}"
  curl -sS "${AUTH[@]}" -X POST "$API/labels" \
    -d "{\"name\":\"$NAME\",\"color\":\"${COLOR#\#}\",\"description\":\"$DESC\"}" >/dev/null || true
done < /tmp/labels_phase1.txt
echo "Labels ensured"

# 3) Create Issues (tracker + tasks)
create_issue() {
  local title="$1"; shift
  local body="$1"; shift
  local labels_csv="$1"; shift
  local payload
  payload=$(python - <<PY
import json,os,sys
title=os.environ['T']; body=os.environ['B']; labels=os.environ['L'].split(',') if os.environ.get('L') else []
milestone=int(os.environ['M'])
print(json.dumps({"title":title,"body":body,"labels":labels,"milestone":milestone},ensure_ascii=False))
PY
  )
  curl -sS "${AUTH[@]}" -X POST "$API/issues" -d "$payload" >/dev/null
}

tracker_title="Phase 1 — Hardening & Deterministic Execution"
tracker_body=$'Parent tracker\n- Goals: DSL 1.1 / Replay diff / Permission diagnostics / p95 & 7d / Clustering v0 / Self-recovery v0 / 3 templates / Nightly x50\n- Acceptance: Nightly 50 runs ≥45 success, Template 20 runs ≥19 success, Dashboard shows p95/7d/Top3'
T="$tracker_title" B="$tracker_body" L="type:tracker,priority:P1" M="$milestone_number" create_issue "$tracker_title" "$tracker_body" "type:tracker,priority:P1"

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
  T="${TITLES[$i]}"; B="${BODIES[$i]}"; L="${LABELS[$i]}"; M="$milestone_number" 
  create_issue "$T" "$B" "$L"
done

echo "Milestone and issues created."
