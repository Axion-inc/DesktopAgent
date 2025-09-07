# Autopilot L4

Enable autopilot by policy (autopilot=true) and policy compliance.

Deviation detection stops runs immediately on:
- Verifier failure (assert/wait)
- Domain/tab drift
- Download verification failure
- Retry limit exceeded

Notify: hook in `app/autopilot/runner.AutoRunner.notify()` (extend to Slack/Webhooks as needed)

Metrics: `l4_autoruns_24h`, `deviation_stops_24h`

Classification & Audit:
- DB table: `l4_deviations` persists each stop with `step_index`, `deviation_type` (verifier|domain|download|retry), and `reason`.
- API: `/api/runs/{run_id}/deviations` returns deviation list for a run (for Run画面やダッシュボード連携に利用)。
