# L4 Autopilot (Limited Full Automation)

## Summary
L4 enables unattended execution when policy permits. It must stop on deviations and notify for HITL resume.

## Enablement
- `policy.autopilot=true`
- Policy-compliant context: domain, time window, signature, capabilities, risks.

## Deviation Detection
- Verifier failures, unexpected steps, unmet completion, domain drift, download verification failure, retry cap exceeded.
- On deviation: pause run, record reason, notify (CLI/Slack), allow HITL resume.

## Metrics
- `l4_autoruns_24h`: number of unattended runs in last 24h
- `deviation_stops_24h`: number of runs stopped by deviations in last 24h

