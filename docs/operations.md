# Desktop Agent Phase 4 Operations Guide

This guide covers operational procedures for Phase 4 features and enterprise functionality.

## 📋 Table of Contents

- [Queue Management](#queue-management)
- [RBAC (Role-Based Access Control)](#rbac)
- [Scheduler & Triggers](#scheduler--triggers)
- [Secrets Management](#secrets-management)  
- [Failure Clustering](#failure-clustering)
- [HITL (Human-in-the-Loop)](#hitl)
- [Monitoring & Metrics](#monitoring--metrics)
- [Troubleshooting](#troubleshooting)

---

## Queue Management

### Overview
The queue system efficiently processes multiple execution requests and manages system resources appropriately.

### Basic Configuration

**Configuration File**: `configs/orchestrator.yaml`

```yaml
queues:
  default:
    max_concurrent: 3
    priority_levels: 9
    retry_policy:
      max_attempts: 3
      backoff_multiplier: 1.5
      
  high_priority:
    max_concurrent: 5
    priority_levels: 9
    
  background:
    max_concurrent: 1
```

### API Usage

```python
# Add to high priority queue
queue_manager = get_queue_manager()
run_id = queue_manager.enqueue_run({
    "template": "important_task.yaml",
    "variables": {"target": "production"},
    "queue": "high_priority",
    "priority": 1  # 1 is highest priority
})
```

### Operational Guidelines

1. **Concurrency Tuning**: Adjust `max_concurrent` based on system resources
2. **Priority Setting**: Use priority 1-3 for critical tasks, 5 for normal, 7-9 for background
3. **Queue Separation**: Use separate queues by purpose to avoid resource contention

---

## RBAC (Role-Based Access Control)

### Overview
Role-based access control provides appropriate permissions for each user based on their responsibilities.

### Role Types

| Role | Permissions | Use Case |
|------|-------------|----------|
| **Admin** | Full access | System administrators |
| **Editor** | Execute, pause, approve | Project managers |
| **Runner** | Execute, view | Execution operators |
| **Viewer** | View only | Monitoring, reporting |

### User Management

```bash
# Create user as admin
curl -X POST http://localhost:8000/api/admin/users \
  -u admin:password \
  -H "Content-Type: application/json" \
  -d '{
    "username": "project_manager",
    "password": "secure_password",
    "active": true
  }'
```

### Endpoint Protection

Implementation example:
```python
from app.middleware.auth import require_editor

@app.post("/api/runs/{run_id}/pause")
@require_editor
async def pause_run(run_id: int, current_user: RBACUser = Depends(get_current_user)):
    # Requires Editor permissions or higher
    pass
```

### Security Considerations

1. **Password Management**: Use strong passwords
2. **Regular Audits**: Review audit logs periodically
3. **Principle of Least Privilege**: Grant minimal necessary permissions

---

## Scheduler & Triggers

### Overview
Automated execution through scheduler and various trigger mechanisms.

### Cron Scheduler

**Configuration File**: `configs/schedules.yaml`

```yaml
schedules:
  - id: "daily_report" 
    name: "Daily Report Generation"
    cron: "0 9 * * *"  # Daily at 9 AM
    template: "daily_report.yaml"
    queue: "background"
    priority: 5
    enabled: true
    variables:
      report_type: "daily"

  - id: "weekly_backup"
    name: "Weekly Backup"  
    cron: "0 2 * * 0"  # Sundays at 2 AM
    template: "backup.yaml"
    queue: "default"
    priority: 3
```

### Folder Watcher

Automated execution based on file system changes:

```python
from app.orchestrator.watcher import get_watcher

watcher = get_watcher()
watcher.add_watcher(WatchConfig(
    id="invoice_processor",
    name="Invoice Processing",
    watch_path="/path/to/invoices",
    template="process_invoice.yaml",
    patterns=["*.pdf"],
    events=["created"],
    debounce_ms=5000,
    queue="default",
    priority=5
))
```

### Webhooks

External system notifications for execution:

```python
from app.orchestrator.webhook import get_webhook_service

webhook_service = get_webhook_service()
webhook_service.add_webhook(WebhookConfig(
    id="github_deploy",
    name="GitHub Deploy Hook", 
    endpoint="/webhooks/deploy",
    template="deploy.yaml",
    secret="your_webhook_secret",
    allowed_ips=["192.30.252.0/22"],  # GitHub IP range
    extract_variables=["repository.name", "head_commit.id"]
))
```

---

## Secrets Management

### Overview
Secure management and utilization system for sensitive information.

### Configuration Methods

#### 1. Keychain/Keyring (Recommended)

```bash
# macOS Keychain
security add-generic-password -s "com.axion.desktop-agent" \
  -a "api_key" -w "your_secret_value"

# Linux keyring
secret-tool store --label="Desktop Agent API Key" \
  service com.axion.desktop-agent account api_key
```

#### 2. Environment Variables

```bash
export DESKTOP_AGENT_SECRET_API_KEY="your_secret_value"
export DESKTOP_AGENT_SECRET_DB_PASSWORD="db_password"
```

#### 3. Encrypted Files

```python
from app.security.secrets import store_secret

store_secret("api_key", "your_secret_value", "external_api")
```

### DSL Usage

```yaml
dsl_version: "1.1"
name: "API Call with Secrets"
steps:
  - make_request:
      url: "https://api.example.com/data"
      headers:
        Authorization: "Bearer {{secrets://api_key}}"
        # Or service/key format
        X-API-Key: "{{secrets://external_api/api_key}}"
```

### Security Best Practices

1. **Secret Protection**
   - Not logged to output
   - Masked in error messages
   - Properly cleared from memory

2. **Access Control**
   - Minimal necessary access permissions
   - Regular secret rotation

3. **Audit**
   - Monitor secret access logs
   - Detect abnormal access patterns

---

## Failure Clustering

### Overview
System that automatically analyzes failure patterns and suggests remediation actions.

### Configuration

Failure analysis runs automatically, but custom rules can be added:

```python
from app.analytics.failure_clustering import get_failure_analyzer

analyzer = get_failure_analyzer()

# Custom rule example
custom_rules = {
    "NETWORK_TIMEOUT": {
        "patterns": [r"timeout.*network", r"connection.*timed out"],
        "display_name": "Network Timeout",
        "recommended_actions": [
            "Check network connectivity",
            "Consider adjusting timeout values",
            "Verify proxy settings"
        ],
        "severity": "medium"
    }
}
```

### Dashboard Monitoring

Check failure clusters via metrics endpoint:

```bash
curl http://localhost:8000/metrics | jq '.top_failure_clusters_24h'
```

### Response Workflow

1. **Failure Detection**: Automatically analyze error patterns
2. **Classification**: Match against known patterns
3. **Recommended Actions**: Provide specific remediation steps
4. **Trend Analysis**: Visualize failure trends

---

## HITL (Human-in-the-Loop)

### Overview
Feature that requires human confirmation/approval for critical operations.

### DSL Configuration

```yaml
dsl_version: "1.1"
name: "Production Deployment"
steps:
  - prepare_deployment:
      target: "production"
  
  - human_confirm:
      message: "Execute production deployment?"
      timeout_minutes: 30
      auto_action: "deny"  # Auto-deny on timeout
      required_role: "Editor"  # Requires Editor permissions or higher
      risk_level: "high"
      
  - deploy_to_production:
      target: "production"
```

### Approval Workflow

1. **Pause**: Execution pauses at `human_confirm` step
2. **Notification**: Approver notified via WebUI
3. **Review**: Approval screen shown at `/hitl/approve/{run_id}`
4. **Decision**: Approve or deny action
5. **Continue**: Execution continues if approved, terminates if denied

### Approval Screen Access

```bash
# Approval screen URL
http://localhost:8000/hitl/approve/{run_id}
```

---

## Monitoring & Metrics

### Phase 4 New Metrics

#### Queue Related
- `queue_depth_peak_24h`: 24-hour queue depth peak
- `runs_per_hour_24h`: Runs per hour
- `retry_rate_24h`: Retry rate

#### RBAC Related  
- `rbac_denied_24h`: Permission denials count
- `user_active_sessions`: Active user sessions

#### Failure Analysis
- `top_failure_clusters_24h`: Top failure clusters
- `failure_cluster_diversity`: Failure pattern diversity

### Dashboard

View metrics at:

```bash
# JSON format
curl http://localhost:8000/metrics

# Web Dashboard  
open http://localhost:8000/public/dashboard
```

### Alert Configuration Example

```bash
# Detect high failure rate
if [ "$(curl -s http://localhost:8000/metrics | jq '.success_rate_24h < 0.8')" = "true" ]; then
  echo "Alert: Success rate below 80%" | mail -s "Desktop Agent Alert" admin@company.com
fi
```

---

## Troubleshooting

### Common Issues and Solutions

#### 1. Queue Congestion

**Symptoms**: Executions not starting
**Cause**: Concurrent execution limit reached

**Solution**:
```bash
# Check current queue status
curl http://localhost:8000/metrics | jq '.queue_depth_peak_24h'

# Adjust configuration (configs/orchestrator.yaml)
max_concurrent: 5  # Increase value
```

#### 2. RBAC Authentication Errors

**Symptoms**: 403 Forbidden errors
**Cause**: Insufficient permissions

**Solution**:
```bash
# Check audit logs
curl -u admin:password http://localhost:8000/api/admin/audit

# Verify user permissions
curl -u admin:password http://localhost:8000/api/admin/users
```

#### 3. Secrets Not Resolving

**Symptoms**: Template variable not found
**Cause**: Secrets backend configuration issue

**Solution**:
```python
from app.security.secrets import get_secrets_manager

# Check secrets availability
manager = get_secrets_manager()
print(manager.get_metrics())
```

#### 4. Scheduler Not Running

**Symptoms**: Cron jobs not executing
**Cause**: Incorrect cron expression configuration

**Solution**:
```bash
# Check scheduler status
curl http://localhost:8000/metrics | jq '.scheduler_metrics'

# Validate cron expression (use https://crontab.guru/)
```

### Log Inspection

```bash
# Application logs
tail -f logs/desktop-agent.log

# Component-specific checks
grep "Queue" logs/desktop-agent.log
grep "RBAC" logs/desktop-agent.log  
grep "Secrets" logs/desktop-agent.log
```

### Performance Optimization

1. **Queue Configuration Tuning**
   - Adjust concurrency based on CPU/memory
   - Set appropriate priorities

2. **Secrets Optimization**  
   - Adjust cache settings
   - Optimize backend selection

3. **Monitoring Interval Adjustment**
   - Tune scheduler check intervals
   - Optimize watcher debounce settings

---

## Support

For technical issues or questions, please refer to:

- **Issue Reporting**: [GitHub Issues](https://github.com/Axion-inc/DesktopAgent/issues)
- **Configuration Examples**: `examples/` directory
- **API Documentation**: `/docs` endpoint (FastAPI auto-generated)

---

*Phase 4 Desktop Agent - Enterprise Automation Platform*