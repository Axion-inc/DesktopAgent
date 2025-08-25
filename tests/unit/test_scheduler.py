"""
Unit tests for Scheduler functionality.

These are "red" tests for TDD - they will initially fail until
the Scheduler system is implemented.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
import time

# These imports will fail initially - expected for TDD red phase
try:
    from app.orchestrator.scheduler import CronScheduler, Schedule, CronParser
    from app.orchestrator.queue import QueueManager
except ImportError:
    # Expected during red phase
    pass


class TestCronParser:
    """Test cron expression parsing and validation."""

    @pytest.mark.xfail(reason="TDD red phase - CronParser not implemented yet")
    def test_valid_cron_expressions(self):
        """Test parsing valid cron expressions."""
        parser = CronParser()

        # Standard expressions
        assert parser.parse("0 9 * * 1").is_valid()  # Every Monday at 9 AM
        assert parser.parse("*/15 * * * *").is_valid()  # Every 15 minutes
        assert parser.parse("0 0 1 * *").is_valid()  # First of every month
        assert parser.parse("30 14 * * 0").is_valid()  # Every Sunday at 2:30 PM

        # Special expressions
        assert parser.parse("@daily").is_valid()
        assert parser.parse("@weekly").is_valid()
        assert parser.parse("@monthly").is_valid()

    @pytest.mark.xfail(reason="TDD red phase - CronParser not implemented yet")
    def test_invalid_cron_expressions(self):
        """Test rejection of invalid cron expressions."""
        parser = CronParser()

        # Invalid syntax
        assert not parser.parse("invalid").is_valid()
        assert not parser.parse("60 * * * *").is_valid()  # Invalid minute
        assert not parser.parse("* 25 * * *").is_valid()  # Invalid hour
        assert not parser.parse("* * * 13 *").is_valid()  # Invalid month
        assert not parser.parse("* * * * 8").is_valid()   # Invalid day of week

    @pytest.mark.xfail(reason="TDD red phase - Next run calculation not implemented yet")
    def test_next_run_calculation(self):
        """Test calculating next run time from cron expression."""
        parser = CronParser()

        # Every Monday at 9 AM
        cron = parser.parse("0 9 * * 1")
        now = datetime(2025, 8, 24, 10, 0)  # Sunday 10 AM

        next_run = cron.next_run_time(now)

        # Should be next Monday at 9 AM
        assert next_run.weekday() == 0  # Monday
        assert next_run.hour == 9
        assert next_run.minute == 0
        assert next_run > now


class TestSchedule:
    """Test individual schedule management."""

    @pytest.mark.xfail(reason="TDD red phase - Schedule not implemented yet")
    def test_schedule_creation_and_properties(self):
        """Test creating and accessing schedule properties."""
        schedule = Schedule(
            id="test_schedule_1",
            name="Weekly Report",
            cron="0 9 * * 1",  # Every Monday 9 AM
            template="weekly_report.yaml",
            queue="reports",
            priority=5,
            enabled=True,
            variables={"output_dir": "/reports"}
        )

        assert schedule.id == "test_schedule_1"
        assert schedule.name == "Weekly Report"
        assert schedule.cron == "0 9 * * 1"
        assert schedule.template == "weekly_report.yaml"
        assert schedule.queue == "reports"
        assert schedule.priority == 5
        assert schedule.enabled is True
        assert schedule.variables["output_dir"] == "/reports"

    @pytest.mark.xfail(reason="TDD red phase - Schedule validation not implemented yet")
    def test_schedule_validation(self):
        """Test schedule validation rules."""
        # Valid schedule should pass
        valid_schedule = Schedule(
            id="valid",
            cron="0 9 * * *",
            template="valid.yaml",
            queue="default"
        )
        assert valid_schedule.validate()

        # Invalid cron should fail
        with pytest.raises(ValueError, match="Invalid cron expression"):
            Schedule(
                id="invalid_cron",
                cron="invalid cron",
                template="test.yaml",
                queue="default"
            )

        # Missing template should fail
        with pytest.raises(ValueError, match="Template is required"):
            Schedule(
                id="no_template",
                cron="0 9 * * *",
                template=None,
                queue="default"
            )

    @pytest.mark.xfail(reason="TDD red phase - Schedule execution not implemented yet")
    def test_schedule_should_run_logic(self):
        """Test logic for determining if schedule should run."""
        schedule = Schedule(
            id="test",
            cron="0 9 * * 1",  # Every Monday 9 AM
            template="test.yaml",
            queue="default"
        )

        # Monday 9:00 AM - should run
        monday_9am = datetime(2025, 8, 25, 9, 0)  # Monday
        assert schedule.should_run(monday_9am) is True

        # Monday 9:01 AM - should not run (already passed)
        monday_901am = datetime(2025, 8, 25, 9, 1)
        assert schedule.should_run(monday_901am) is False

        # Tuesday 9:00 AM - should not run (wrong day)
        tuesday_9am = datetime(2025, 8, 26, 9, 0)
        assert schedule.should_run(tuesday_9am) is False


class TestCronScheduler:
    """Test cron scheduler core functionality."""

    @pytest.mark.xfail(reason="TDD red phase - CronScheduler not implemented yet")
    def test_scheduler_initialization(self):
        """Test scheduler initialization with queue manager."""
        queue_manager = QueueManager()
        scheduler = CronScheduler(queue_manager=queue_manager)

        assert scheduler.queue_manager is queue_manager
        assert len(scheduler.schedules) == 0
        assert scheduler.is_running is False

    @pytest.mark.xfail(reason="TDD red phase - Schedule management not implemented yet")
    def test_add_remove_schedules(self):
        """Test adding and removing schedules."""
        scheduler = CronScheduler()

        # Add schedule
        schedule = Schedule(
            id="test_1",
            cron="0 9 * * *",
            template="daily.yaml",
            queue="default"
        )

        scheduler.add_schedule(schedule)
        assert len(scheduler.schedules) == 1
        assert scheduler.get_schedule("test_1") == schedule

        # Remove schedule
        scheduler.remove_schedule("test_1")
        assert len(scheduler.schedules) == 0
        assert scheduler.get_schedule("test_1") is None

    @pytest.mark.xfail(reason="TDD red phase - Schedule loading not implemented yet")
    def test_load_schedules_from_config(self):
        """Test loading schedules from configuration file."""
        config_content = """
        schedules:
          weekly_report:
            cron: "0 9 * * 1"
            template: "weekly_report.yaml"
            queue: "reports"
            priority: 7
            variables:
              output_dir: "/data/reports"

          daily_cleanup:
            cron: "0 2 * * *"
            template: "cleanup.yaml"
            queue: "maintenance"
            priority: 3
            enabled: true
        """

        with patch('builtins.open', mock_open(read_data=config_content)):
            scheduler = CronScheduler()
            scheduler.load_config("schedules.yaml")

        assert len(scheduler.schedules) == 2

        weekly = scheduler.get_schedule("weekly_report")
        assert weekly.cron == "0 9 * * 1"
        assert weekly.template == "weekly_report.yaml"
        assert weekly.queue == "reports"
        assert weekly.priority == 7

        daily = scheduler.get_schedule("daily_cleanup")
        assert daily.cron == "0 2 * * *"
        assert daily.enabled is True

    @pytest.mark.xfail(reason="TDD red phase - Schedule execution not implemented yet")
    def test_schedule_execution_and_queueing(self):
        """Test scheduled runs are properly queued."""
        queue_manager = Mock()
        scheduler = CronScheduler(queue_manager=queue_manager)

        schedule = Schedule(
            id="test_exec",
            cron="* * * * *",  # Every minute
            template="test.yaml",
            queue="test_queue",
            priority=5,
            variables={"var1": "value1"}
        )

        scheduler.add_schedule(schedule)

        # Trigger execution
        scheduler.check_schedules()

        # Should have queued the run
        queue_manager.enqueue.assert_called_once()
        call_args = queue_manager.enqueue.call_args

        assert call_args[0][0] == "test_queue"  # Queue name
        run_data = call_args[0][1]
        assert run_data["template"] == "test.yaml"
        assert run_data["priority"] == 5
        assert run_data["variables"]["var1"] == "value1"
        assert run_data["trigger_type"] == "scheduled"


class TestSchedulerService:
    """Test scheduler service and background execution."""

    @pytest.mark.xfail(reason="TDD red phase - Background service not implemented yet")
    def test_scheduler_start_stop(self):
        """Test starting and stopping scheduler service."""
        scheduler = CronScheduler()

        # Start scheduler
        scheduler.start()
        assert scheduler.is_running is True

        # Stop scheduler
        scheduler.stop()
        assert scheduler.is_running is False

    @pytest.mark.xfail(reason="TDD red phase - Periodic checking not implemented yet")
    def test_periodic_schedule_checking(self):
        """Test scheduler periodically checks for due schedules."""
        scheduler = CronScheduler()

        # Mock time to control schedule checking
        with patch('time.time') as mock_time:
            mock_time.return_value = time.time()

            # Add a schedule that should trigger
            schedule = Mock()
            schedule.should_run.return_value = True
            schedule.enabled = True
            schedule.id = "test"

            scheduler.schedules = {"test": schedule}

            # Run one check cycle
            scheduler.check_schedules()

            # Should have checked if schedule should run
            schedule.should_run.assert_called_once()

    @pytest.mark.xfail(reason="TDD red phase - Error handling not implemented yet")
    def test_schedule_execution_error_handling(self):
        """Test error handling during schedule execution."""
        queue_manager = Mock()
        queue_manager.enqueue.side_effect = Exception("Queue full")

        scheduler = CronScheduler(queue_manager=queue_manager)

        schedule = Schedule(
            id="error_test",
            cron="* * * * *",
            template="test.yaml",
            queue="full_queue"
        )

        scheduler.add_schedule(schedule)

        # Should handle error gracefully and continue
        try:
            scheduler.check_schedules()
        except Exception:
            pytest.fail("Scheduler should handle queueing errors gracefully")

        # Schedule should be marked as failed but not removed
        assert scheduler.get_schedule("error_test") is not None


class TestSchedulerMetrics:
    """Test scheduler metrics collection."""

    @pytest.mark.xfail(reason="TDD red phase - Metrics not implemented yet")
    def test_scheduled_runs_tracking(self):
        """Test tracking of scheduled run count."""
        scheduler = CronScheduler()

        # Simulate successful schedule executions
        for i in range(5):
            scheduler.record_execution(f"schedule_{i}", success=True)

        metrics = scheduler.get_metrics()
        assert metrics["scheduled_runs_24h"] >= 5

    @pytest.mark.xfail(reason="TDD red phase - Schedule performance not implemented yet")
    def test_schedule_execution_timing(self):
        """Test tracking schedule execution timing accuracy."""
        scheduler = CronScheduler()

        # Record schedule with timing info
        scheduled_time = datetime(2025, 8, 24, 9, 0, 0)
        actual_time = datetime(2025, 8, 24, 9, 0, 2)  # 2 seconds late

        scheduler.record_execution_timing("test_schedule", scheduled_time, actual_time)

        metrics = scheduler.get_metrics()
        assert "schedule_delay_avg_ms" in metrics
        assert metrics["schedule_delay_avg_ms"] >= 2000  # 2 seconds = 2000ms

    @pytest.mark.xfail(reason="TDD red phase - Failure tracking not implemented yet")
    def test_schedule_failure_tracking(self):
        """Test tracking of schedule execution failures."""
        scheduler = CronScheduler()

        # Record some failures
        scheduler.record_execution("schedule_1", success=False, error="Queue full")
        scheduler.record_execution("schedule_2", success=False, error="Template not found")
        scheduler.record_execution("schedule_3", success=True)

        metrics = scheduler.get_metrics()
        assert metrics["schedule_failures_24h"] >= 2
        assert metrics["schedule_success_rate_24h"] <= 0.34  # 1 success out of 3


class TestSchedulerPersistence:
    """Test scheduler state persistence."""

    @pytest.mark.xfail(reason="TDD red phase - State persistence not implemented yet")
    def test_schedule_state_persistence(self):
        """Test schedules persist across restarts."""
        # First scheduler instance
        scheduler1 = CronScheduler(state_file="test_scheduler.json")

        schedule = Schedule(
            id="persistent_test",
            cron="0 12 * * *",
            template="persistent.yaml",
            queue="default"
        )

        scheduler1.add_schedule(schedule)
        scheduler1.save_state()

        # Second scheduler instance (simulating restart)
        scheduler2 = CronScheduler(state_file="test_scheduler.json")
        scheduler2.load_state()

        # Should have restored the schedule
        restored = scheduler2.get_schedule("persistent_test")
        assert restored is not None
        assert restored.cron == "0 12 * * *"
        assert restored.template == "persistent.yaml"

    @pytest.mark.xfail(reason="TDD red phase - Last run tracking not implemented yet")
    def test_last_run_tracking(self):
        """Test tracking of last execution times."""
        scheduler = CronScheduler()

        schedule = Schedule(
            id="tracked",
            cron="0 9 * * *",
            template="test.yaml",
            queue="default"
        )

        scheduler.add_schedule(schedule)

        # Record execution
        execution_time = datetime(2025, 8, 24, 9, 0, 0)
        scheduler.record_execution("tracked", success=True, execution_time=execution_time)

        # Should track last run time
        updated_schedule = scheduler.get_schedule("tracked")
        assert updated_schedule.last_run == execution_time

        # Should not trigger again for same time
        assert not updated_schedule.should_run(execution_time)


class TestSchedulerIntegration:
    """Test scheduler integration with other systems."""

    @pytest.mark.xfail(reason="TDD red phase - RBAC integration not implemented yet")
    def test_schedule_management_requires_permissions(self):
        """Test schedule management operations require proper permissions."""
        scheduler = CronScheduler()

        with patch('app.middleware.auth.get_current_user') as mock_user:
            # Viewer cannot add schedules
            mock_user.return_value = Mock(role="viewer")

            with pytest.raises(PermissionError):
                scheduler.add_schedule(Schedule(
                    id="forbidden",
                    cron="* * * * *",
                    template="test.yaml",
                    queue="default"
                ))

            # Admin can add schedules
            mock_user.return_value = Mock(role="admin")

            result = scheduler.add_schedule(Schedule(
                id="allowed",
                cron="* * * * *",
                template="test.yaml",
                queue="default"
            ))
            assert result is not None

    @pytest.mark.xfail(reason="TDD red phase - Template validation not implemented yet")
    def test_schedule_template_validation(self):
        """Test schedules validate template existence."""
        scheduler = CronScheduler()

        # Mock template validator
        with patch('app.dsl.validator.template_exists') as mock_exists:
            # Non-existent template should fail
            mock_exists.return_value = False

            with pytest.raises(ValueError, match="Template .* not found"):
                scheduler.add_schedule(Schedule(
                    id="missing_template",
                    cron="* * * * *",
                    template="nonexistent.yaml",
                    queue="default"
                ))

            # Existing template should succeed
            mock_exists.return_value = True

            result = scheduler.add_schedule(Schedule(
                id="valid_template",
                cron="* * * * *",
                template="existing.yaml",
                queue="default"
            ))
            assert result is not None


def mock_open(read_data):
    """Helper to mock file opening."""
    from unittest.mock import mock_open as _mock_open
    return _mock_open(read_data=read_data)
