# Verifier PASS Rate Tuning

- Increase waits/assert timeouts on slower sites:
  - Example: `plans/templates/timeout_tuning_example.yaml` uses `timeout_ms: 12000` for `wait_for_element` and `assert_element`.
- Prefer stable locators (labels/roles) over brittle selectors.
- Reduce unnecessary navigation and retries; use `wait_for_download` + `assert_file_exists` for DL flows.
- Measure `/metrics` → `verifier_pass_rate_24h` and iterate timeouts until ≥ 0.95.

## Run Examples

- Policy-only dry-run (safely counts autorun, no browser):
  - `POLICY_ONLY=1 python -m app.cli run plans/templates/autorun_local.yaml --auto-approve`
- Full run (requires permissions and browser):
  - `python -m app.cli run plans/templates/timeout_tuning_example.yaml --auto-approve`
