# Planning Interval and Tuning

Planner/Navigator loops work best with short batches and periodic replanning.

## Defaults (configs/runner.yaml)

```
planning_interval_steps: 5
navigator_batch_limit: 3
retry: { max_attempts: 1, backoff_ms: 800 }
deviation:
  stop_on_domain_drift: true
  assert_failures_threshold: 1
artifacts:
  screenshot_every_step: true
  capture_dom_schema_every_step: true
```

## Guidance

- Use `navigator_batch_limit` of 2–4 to minimize drift and improve recovery.
- Increase `timeout_ms` only when strictly necessary.
- Favor explicit waits on status elements (`role=status`) to improve verifier pass rate.

