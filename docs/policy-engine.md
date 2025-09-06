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

