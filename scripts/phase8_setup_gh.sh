#!/usr/bin/env bash
set -euo pipefail

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI not found. Install GitHub CLI and authenticate: gh auth login" >&2
  exit 1
fi

REPO=${REPO:-"Axion-inc/DesktopAgent"}
MILESTONE_NAME=${MILESTONE_NAME:-"Phase 8 — Planner/Navigator + LLM Draft + LangGraph"}
MILESTONE_DUE=${MILESTONE_DUE:-""}

echo "Creating milestone: $MILESTONE_NAME"
gh api repos/$REPO/milestones \
  -f title="$MILESTONE_NAME" \
  -f state=open \
  ${MILESTONE_DUE:+-f due_on="$MILESTONE_DUE"} \
  || echo "Milestone may already exist"

labels=(
  "priority:P0" "priority:P1" "priority:P2"
  "area:orch" "area:planner" "area:navigator" "area:verify" "area:webx" "area:metrics" "area:ui" "area:test" "area:docs" "area:ci"
  "type:tracker" "milestone:phase8"
)

for l in "${labels[@]}"; do
  gh label create "$l" --repo "$REPO" --color FFFFFF --description "$l" || true
done

issues=(
  "[P8] トラッカー：Planner/Navigator + LLM Draft + LangGraph|type:tracker,area:planner,area:navigator,milestone:phase8"
  "[P8][Orch] LangGraphノード/interrupt/再開/チェックポイント|area:orch,milestone:phase8"
  "[P8][Planner] 差分パッチ＆ドラフト出力 + API/Schema|area:planner,milestone:phase8"
  "[P8][Draft] 静的検査→Dry-run×3→署名→登録|area:planner,milestone:phase8"
  "[P8][Navigator] バッチ実行・ナビ変化中断・エラー分類|area:navigator,milestone:phase8"
  "[P8][Verify] doneゲート＆完了確定|area:verify,milestone:phase8"
  "[P8][Metrics/UI] 新6指標とRun可視化（計画/中断/再開/差分/証跡）|area:metrics,area:ui,milestone:phase8"
  "[P8][Tests] 契約/ユニット/E2E一式|area:test,milestone:phase8"
  "[P8][Docs] planner-navigator / planning-interval / draft-to-signed|area:docs,milestone:phase8"
)

for i in "${issues[@]}"; do
  title="${i%%|*}"; labs="${i##*|}"
  IFS=',' read -ra arr <<< "$labs"
  labelFlags=()
  for a in "${arr[@]}"; do
    labelFlags+=("-l" "$a")
  done
  gh issue create --repo "$REPO" -t "$title" -b "Auto-created for Phase 8" "${labelFlags[@]}" || true
done

echo "Done."

