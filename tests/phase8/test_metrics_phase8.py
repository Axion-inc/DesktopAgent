from app.metrics import get_metrics_collector


def test_phase8_counters_exist_and_increment():
    m = get_metrics_collector()
    # New Phase 8 counters
    for key in [
        'planning_runs_24h',
        'navigator_avg_batch',
        'page_change_interrupts_24h',
        'planner_draft_count_24h',
        'draft_signoff_rate_7d',
        'verifier_pass_rate_24h',
    ]:
        m.increment_counter(key)
        assert m.get_counter(key) >= 1

