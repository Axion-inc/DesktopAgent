# Policy Engine v1

Policy file: `configs/policy.yaml`

Example:
```
autopilot: false
allow_domains: ["partner.example.com"]
allow_risks: ["sends"]
window: "SAT 00:00-23:59 Asia/Tokyo"
require_signed_templates: true
require_capabilities: ["webx"]
```

- Guard checks: domain, time window (TZ), risks, signed templates, required capabilities
- Block behavior: stop before execution, show reason, increment `policy_blocks_24h`
- Autopilot: only when `autopilot=true` and all checks pass

Integration:
- CLI pre-exec guard: `policy_guard` step is inserted with detailed `checks` in step output_json.
- Audit: JSONL written to `logs/policy_audit.log` on every block (includes reasons and check results).
- API: `/api/runs/{run_id}/policy-checks` returns the last `policy_guard` checks for a run.
