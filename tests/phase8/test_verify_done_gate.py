from app.verify.core import aggregate_verification


def test_planner_done_needs_verifier_pass():
    # Planner says done, but verifier has not passed yet
    verify_results = [{"name": "wait_for_text", "status": "pending"}]
    final = aggregate_verification(verify_results, planner_done=True)
    assert final["finalized"] is False

    # After pass
    verify_results = [{"name": "wait_for_text", "status": "success"}]
    final = aggregate_verification(verify_results, planner_done=True)
    assert final["finalized"] is True

