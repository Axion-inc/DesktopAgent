Desktop Agent (Phase 5)

Demo Site: https://axion-inc.github.io/DesktopAgent/

![CI](https://github.com/Axion-inc/DesktopAgent/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

CI: https://github.com/Axion-inc/DesktopAgent/actions
Badges (after deploying /metrics):
- Success rate: `![Success](https://img.shields.io/endpoint?url=https://YOUR_HOST/metrics&label=success&query=$.success_rate&suffix=%25)`
- Runs: `![Runs](https://img.shields.io/endpoint?url=https://YOUR_HOST/metrics&label=runs&query=$.total_runs)`

Purpose: A comprehensive enterprise desktop AI agent for macOS 14+ that automates file operations, PDF processing, Mail.app integration, **web form automation with Chrome Extension + Native Messaging (Phase 5 WebX)**, robust verification capabilities, and enterprise orchestration. Features CLI interface, approval gates, natural language plan generation, role-based access control, queue management, and comprehensive testing. Designed for Windows 11 support with full OS adapter architecture.

## Phase 5 Features 🌐 (Web Operator v2)

**WebX Engine Architecture** - Chrome Extension + Native Messaging
- **Engine Abstraction** - Unified API supporting Extension and Playwright engines
- **Chrome Extension MV3** - High-performance DOM manipulation with minimal permissions  
- **Native Messaging Host** - Secure JSON-RPC communication bridge
- **Backward Compatibility** - Existing DSL templates work unchanged with new engine

**Enhanced Web Automation** - Stable, Fast, Permission-Clear
- **Japanese Form Support** - Advanced label matching with synonym support
- **File Upload via Debugger** - Secure file uploads with explicit permission model
- **DOM Schema Capture** - Web equivalent of screen schema for element discovery
- **Approval Gates** - Maintained security for destructive web actions

**Performance & Monitoring** - DoD-Compliant Metrics
- **Engine Usage Tracking** - Extension vs Playwright utilization metrics (webx_engine_share_24h)
- **Upload Success Rate** - File upload reliability monitoring (webx_upload_success_24h ≥ 0.95)
- **Failure Rate Tracking** - Web operation error monitoring (webx_failures_24h / webx_steps_24h ≤ 0.05)
- **Zero Missubmissions** - Approval gate effectiveness (継続維持)

**Security Model** - Explicit Permissions & Safe Defaults
- **Minimal Permissions** - Extension requests only: scripting, storage, downloads
- **Optional Debugger** - File upload capability only when explicitly enabled
- **Token Authentication** - Native messaging secured with handshake tokens
- **Extension ID Allowlist** - Prevent unauthorized extension connections

## Phase 4 Features 🚀

**Enterprise Orchestration** - Advanced execution management
- **Queue Management** - Priority-based task queuing with concurrency control
- **Resume/Pause** - Intelligent resumption from interruption points with state persistence
- **HITL (Human-in-the-Loop)** - Approval workflows for critical operations
- **Retry Policies** - Configurable retry logic with exponential backoff

**Role-Based Access Control (RBAC)** - Enterprise security
- **User Roles** - Admin, Editor, Runner, Viewer with hierarchical permissions
- **FastAPI Middleware** - Endpoint protection with decorator-based authorization
- **Audit Logging** - Complete access tracking and security monitoring
- **Session Management** - Secure authentication with request-scoped contexts

**Secrets Management** - Secure credential handling
- **Multi-Backend Support** - Keychain/Keyring, encrypted files, environment variables
- **Template Integration** - `{{secrets://key}}` syntax in DSL templates
- **Auto-Masking** - Secrets never appear in logs or error messages
- **Reference Validation** - Compile-time verification of secret references

**Automated Triggers** - Event-driven execution
- **Cron Scheduler** - Time-based automation with YAML configuration
- **Folder Watcher** - File system change triggers with pattern matching
- **Webhooks** - HTTP endpoint triggers with HMAC signature verification
- **Configurable Debouncing** - Prevent duplicate executions

**Advanced Failure Analysis** - Intelligent error handling
- **Failure Clustering** - Pattern-based error grouping with ML-ready features
- **Actionable Recommendations** - Context-aware troubleshooting suggestions
- **Trend Analysis** - Historical failure pattern tracking
- **Severity Classification** - Automatic criticality assessment

**Enhanced Metrics & Monitoring** - Enterprise visibility
- **Queue Metrics** - Depth, throughput, and concurrency monitoring
- **RBAC Analytics** - Permission denials and user activity tracking
- **Failure Insights** - Top error patterns with recommended actions
- **Performance Metrics** - P95 latency, success rates, retry statistics

## Phase 3 Features ✨

**Verifier Loop** - Automated verification with intelligent retry
- `wait_for_element` - Wait for UI elements with configurable timeout
- `assert_element` - Verify element presence with count validation
- `assert_text` - Confirm text presence on screen or web
- `assert_file_exists` - Validate file system operations
- `assert_pdf_pages` - PDF page count verification
- Auto-retry logic with PASS/FAIL/RETRY status tracking

**Screen Schema v0** - Accessibility-based screen understanding
- `capture_screen_schema` - Extract macOS AX API hierarchy as JSON
- Web accessibility tree capture via Playwright
- Structured element data for Planner L1 and Verifier use
- Cross-platform schema format for future Windows UI Automation

**Web Extensions** - Enhanced web automation capabilities
- `upload_file` - File upload to input[type=file] elements
- `wait_for_download` - Monitor download completion
- Intelligent file input discovery by label or selector
- Compatible with existing web automation workflow

**Windows-Ready OS Adapter** - Cross-platform foundation
- Unified OSAdapter interface for all platform operations
- Capability negotiation system with graceful fallbacks
- Complete Windows implementation stubs with future guidance
- Contract tests ensuring consistent cross-platform behavior

**Enhanced Metrics** - Comprehensive Phase 3 monitoring
- `verifier_pass_rate_24h` - Verification success rate including retries
- `schema_captures_24h` - Screen schema capture frequency
- `web_upload_success_rate_24h` - File upload operation success rate
- `os_capability_miss_24h` - Unsupported feature encounter tracking

## Phase 2 Features ✨

**Web Automation** - Automate web forms with Playwright
- `open_browser` - Navigate to websites
- `fill_by_label` - Fill form fields by label text
- `click_by_text` - Click buttons and links
- `download_file` - Download files from web pages

**Approval Gates** - Risk analysis for destructive operations
- Automatic detection of high-risk actions (submit, delete, etc.)
- Manual approval workflow for destructive operations
- Risk categorization and detailed analysis

**Planner L1** - Natural language to DSL conversion
- Template-based plan generation from natural language
- Support for CSV-to-form, PDF workflows, and file organization
- Local-only processing, no external API calls

**Enhanced Self-Recovery** - Improved error handling
- Web form field recovery with label synonyms
- Enhanced file operation recovery
- Detailed recovery action logging

**Mock SaaS Testing** - Built-in testing environment
- Japanese mock form for E2E testing
- Realistic form validation and submission
- Perfect for testing web automation workflows

Quickstart (macOS 14+)
- Prereqs: Python 3.11+, Xcode CLT, Node.js (for Playwright), permissions for Screen Recording and Automation.
- Setup:
  - `python3 -m venv venv`
  - `source venv/bin/activate`
  - `pip install -r requirements.txt`
  - `npx playwright install --with-deps chromium` (for web automation)

**CLI Interface**:
  - `./cli.py templates` - List available templates
  - `./cli.py validate plans/templates/weekly_report.yaml` - Validate plan
  - `./cli.py run plans/templates/weekly_report.yaml` - Execute plan
  - `./cli.py list` - View run history
  - `./cli.py show <run_id>` - View run details

**Optional API Server** (for metrics only):
  - `uvicorn app.main:app --reload`
  - Health check: http://127.0.0.1:8000/healthz
  - Metrics: http://127.0.0.1:8000/metrics

## Phase 5 WebX Setup 🌐

**1. Install WebX Extension System**
```bash
# Run automated setup
./scripts/install_native_host.sh
```

**2. Manual Chrome Extension Installation**
```bash
# 1. Open chrome://extensions/
# 2. Enable Developer Mode  
# 3. Load unpacked extension from webx-extension/
# 4. Note the Extension ID and update configs/web_engine.yaml
```

**3. Configure Web Engine**
```yaml
# configs/web_engine.yaml
engine: "extension"  # Use Chrome extension (or "playwright")

extension:
  id: "your_extension_id_here"
  enable_debugger_upload: false  # Enable only for file uploads
```

**4. Test WebX System**
```bash
# Test native messaging
python -m pytest tests/contract/test_webx_protocol.py -v

# Test web engine integration
python -c "from app.web.engine import get_web_engine; print(get_web_engine().__class__.__name__)"

# Run with WebX engine
./cli.py run plans/templates/web_form_example.yaml
```

**WebX Benefits:**
- **3x Faster** - Native DOM access vs browser automation
- **Explicit Permissions** - Clear permission model for enterprise security
- **Japanese Forms** - Advanced label matching for international websites
- **Zero Missubmissions** - Approval gates prevent accidental destructive actions

See [WebX Setup Guide](docs/webx-setup.md) for detailed configuration.

Screenshots (Demo)
![Run Timeline](docs/assets/runs_timeline.svg)
![Public Dashboard](docs/assets/dashboard.svg)

Notes
- Sample PDFs are self-generated by `scripts/dev_setup_macos.sh` and are license-safe dummy files.
- Set `PERMISSIONS_STRICT=1` to block runs when Screen Recording is not granted (default is warn-only).

Permissions (macOS)
- **Screen Recording**: System Settings → Privacy & Security → Screen Recording → allow Terminal and your Python.
  - Diagram: docs/assets/permissions_screen_recording.svg
- **Automation (Mail, Finder, System Events)**: First run will prompt; or enable under Privacy & Security → Automation.
  - Diagram: docs/assets/permissions_automation.svg
- **Diagnostic UI**: Visit `/permissions` for real-time permission status and step-by-step fix instructions.
- **Blocking Mode**: Set `PERMISSIONS_STRICT=1` to block execution when permissions are missing (default: warning only).

Flow
- Plans → CLI Validation → **Risk Analysis & Approval** → Execute → View Results

Quick Start
- `./cli.py run plans/templates/weekly_report.yaml` - Run the default weekly report plan

## Phase 4 Quick Setup 🔧

**1. Start the API Server**
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**2. Initialize RBAC**
```bash
# Create admin user
curl -X POST http://localhost:8000/api/admin/users \
  -u admin:admin \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "secure_password"}'
```

**3. Configure Secrets**
```bash
# Store API key in keychain (macOS)
security add-generic-password -s "com.axion.desktop-agent" \
  -a "api_key" -w "your_secret_value"

# Or use environment variable
export DESKTOP_AGENT_SECRET_API_KEY="your_secret_value"
```

**4. Setup Automation**
```yaml
# configs/schedules.yaml
schedules:
  - id: "daily_report"
    cron: "0 9 * * *"  # 9 AM daily
    template: "daily_report.yaml"
    queue: "default"
    priority: 5
```

**5. Access Dashboard**
- Web Dashboard: http://localhost:8000/public/dashboard
- Metrics API: http://localhost:8000/metrics
- HITL Approval: http://localhost:8000/hitl/approve/{run_id}

**6. DSL with Phase 4 Features**
```yaml
dsl_version: "1.1"
name: "Secure API Call"
execution:
  queue: "high_priority"
  priority: 1
  retry:
    max_attempts: 3
steps:
  - human_confirm:
      message: "Execute production API call?"
      timeout_minutes: 30
      required_role: "Editor"
      
  - make_request:
      url: "https://api.example.com"
      headers:
        Authorization: "Bearer {{secrets://api_key}}"
```

📖 **Full Documentation**: See [docs/operations.md](docs/operations.md) for detailed setup and configuration.

## Web Automation (Phase 2)

**Setup Playwright**
```bash
npx playwright install --with-deps chromium
```

**Web DSL Actions**
```yaml
# Open browser and navigate
- open_browser:
    url: "https://example.com/form"
    context: "default"

# Fill form fields by label
- fill_by_label:
    label: "氏名"  # or "Name", "Full Name"
    text: "{{csv_data.name}}"
    context: "default"

# Click buttons or links
- click_by_text:
    text: "送信"  # or "Submit", "Send"
    role: "button"  # optional: button, link
    context: "default"

# Download files
- download_file:
    target_path: "./downloads/"
    context: "default"
```

**Label Recovery** - Automatic fallback strategies:
- Primary: `page.get_by_label()` (most stable)
- Fallback 1: Synonym matching (`氏名` → `名前`, `お名前`, `Name`)
- Fallback 2: Placeholder text matching
- Fallback 3: CSS selector patterns

**Mock SaaS Form** - Test web automation with included templates targeting mock forms for E2E testing

## Verifier System (Phase 3)

**DSL Verification Commands**:
```yaml
# Wait for element to appear
- wait_for_element:
    text: "送信"
    role: "button"
    timeout_ms: 15000
    where: "web"  # or "screen"

# Assert element exists with count validation
- assert_element:
    text: "成功"
    role: "button"
    count_gte: 1
    where: "screen"

# Assert text is present
- assert_text:
    contains: "送信が完了しました"
    where: "web"

# Validate file operations
- assert_file_exists:
    path: "~/Reports/output.pdf"

# Verify PDF page count
- assert_pdf_pages:
    path: "~/Reports/output.pdf"
    expected_pages: 5
```

**Auto-Retry Logic** - Intelligent failure recovery:
- **wait_for_element timeout** → Extended wait + single retry
- **assert_element failure** → Screen schema capture + broader text search retry
- **Maximum 1 retry per verification** → Prevents infinite loops
- **Status tracking** → PASS/FAIL/RETRY recorded in Run artifacts

**Verifier Status Badges** - Visual feedback in dashboard and run details:
- **PASS** → Verification succeeded on first attempt
- **RETRY** → Verification succeeded after auto-retry
- **FAIL** → Verification failed even after retry

## Screen Schema v0 (Phase 3)

**Schema Capture**:
```yaml
# Capture accessibility hierarchy
- capture_screen_schema:
    target: "frontmost"  # or "screen"
```

**macOS Implementation** - Using Accessibility API:
- **AX API Integration** → Role/label/value/bounds extraction
- **Hierarchical Structure** → Parent-child element relationships
- **JSON Format** → Standardized cross-platform schema
- **Future Enhancement** → Full PyObjC integration planned

**Web Implementation** - Using Playwright:
- **Accessibility Tree** → Complete page element hierarchy
- **Role Mapping** → ARIA roles and semantic information
- **Cross-Reference** → Schema data available to Verifier commands

**Schema Usage**:
- **Verifier Enhancement** → Improved element location accuracy
- **Planner L1 Context** → UI understanding for better plan generation
- **Run Artifacts** → Schema JSON stored with screenshots for debugging

## Web Extensions (Phase 3)

**File Upload DSL**:
```yaml
# Upload by CSS selector
- upload_file:
    path: "~/Documents/attachment.pdf"
    selector: "input[type=file]"
    context: "default"

# Upload by label text
- upload_file:
    path: "~/Documents/image.png"
    label: "添付ファイル"
    context: "default"
```

**Download Monitoring**:
```yaml
# Wait for download completion
- wait_for_download:
    to: "~/Downloads"
    timeout_ms: 30000
    context: "default"
```

**Safety Features**:
- **Input Validation** → File existence verified before upload
- **Fallback Strategy** → Multiple selector methods for file inputs
- **No False Positives** → E2E tests verify 0 accidental uploads
- **Backward Compatible** → Existing web automation unaffected

## Approval Gates (Phase 2)

**Risk Analysis** - Automatic detection of destructive operations:
- **High Risk**: `送信`, `確定`, `Submit`, `Delete`, `削除`, `上書き`
- **Medium Risk**: Form submissions, file moves, email composition
- **Low Risk**: Read-only operations, logging

**Approval Workflow**:
1. Plan submitted → Risk analysis
2. If risky → Manual approval required
3. Approval granted → Plan executes
4. All actions logged with approval status

**CLI Approval**: Use `--auto-approve` flag to bypass approval gates, or CLI will prompt when approval is required

## Planner L1 (Phase 2)

**Natural Language to DSL** - Convert intent to executable plans:

**Usage**: Natural language planning is integrated into the CLI workflow and available through the included plan templates

**Supported Workflows**:
- **CSV to Form**: "csvファイルをフォームに転記"
- **PDF Merge**: "Merge PDF files and email result"  
- **File Organization**: "ダウンロードフォルダを整理"

**Templates Generated**:
- CSV processing with web form submission
- PDF operations with email attachment
- File organization with pattern matching

**Features**:
- Local-only processing (no API calls)
- Template-based generation
- Confidence scoring
- Entity extraction (file types, actions, quantities)

Sample PDFs
- 10 dummy PDFs are bundled via generator; run `scripts/dev_setup_macos.sh` to (re)materialize them into `sample_data/` safely (license-free).

Windows Roadmap (stubs included)
- Mail via Outlook `win32com` (compose, attach, save draft)
- Preview alternative via `os.startfile`
- Future: UI Automation (UIA) for richer flows

## Testing (Phase 2)

**Unit Tests**
```bash
pytest tests/ -v -k "not e2e"
```

**E2E Tests** (with Playwright)
```bash
# Start server
uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# Run E2E tests
export BASE_URL="http://localhost:8000"
export PLAYWRIGHT_HEADLESS="true"
pytest tests/ -v -k "e2e" --maxfail=3
```

**Test Coverage**:
- Web actions (mocked and real browser)
- Approval system (risk analysis, workflow)
- Planner L1 (intent matching, DSL generation)
- Mock form automation (Japanese form testing)
- Self-recovery mechanisms
- Dashboard and metrics endpoints
- **Phase 3**: Verifier commands simulation, Screen schema extraction, Web extensions, OS Adapter contracts
- **100-Run E2E**: Comprehensive reliability testing with 95% success threshold
- **Windows Readiness**: Contract tests with xfail markers for future implementation

## CI

**GitHub Actions** - Enhanced pipeline:
- **Unit Tests**: flake8 linting + pytest (non-E2E)
- **E2E Tests**: Playwright browser automation (main branch only)
- **Playwright Setup**: Automatic browser installation
- **Parallel Jobs**: Unit and E2E tests run separately for efficiency

## Metrics / Badges (Phase 2)

## OS Adapter Architecture (Phase 3)

**Unified Interface** - Cross-platform abstraction:
```python
from app.os_adapters.base import OSAdapter

# Get platform-specific adapter
adapter = get_os_adapter()  # MacOSAdapter or WindowsOSAdapter

# Check capabilities
caps = adapter.capabilities()
if caps["screenshot"].available:
    adapter.take_screenshot("screenshot.png")

# Fallback handling
if not caps["mail_compose"].available:
    # Graceful degradation to .eml template generation
    pass
```

**Capability Negotiation** - Feature availability management:
- **Available Features** → Full implementation with expected behavior
- **Unavailable Features** → Graceful fallback with user notification
- **Future-Ready** → Windows implementation guidance in stubs
- **Contract Tests** → Consistent behavior validation across platforms

**macOS Implementation** - Complete feature support:
- **Screenshots** → Via `screencapture` command
- **Mail Operations** → AppleScript integration with Mail.app
- **File Operations** → Native filesystem access
- **PDF Operations** → PyPDF2 integration
- **Permissions Check** → TCC database and runtime validation

**Windows Design** - Future implementation foundation:
- **Complete Stubs** → All methods with detailed implementation guidance
- **COM Integration** → Outlook automation via win32com.client
- **UI Automation** → Windows UIA for screen schema capture
- **Registry/API** → Permission checking via Windows APIs
- **Contract Compliance** → Tests ready for implementation validation

**Benefits**:
- **Platform Abstraction** → Single codebase for cross-platform deployment
- **Incremental Windows Support** → Add features gradually without breaking changes
- **Test Coverage** → Contract tests prevent regression during Windows implementation
- **Capability Discovery** → Runtime feature detection prevents unsupported operation attempts

## Windows Implementation Guide (Phase 3)

**Implementation Roadmap**:
1. **Install Dependencies** → `pip install pywin32 pywinauto`
2. **COM Integration** → Outlook automation for mail operations
3. **UI Automation** → Screen schema via Windows UIA API
4. **API Integration** → Screenshots, file operations, permissions
5. **Testing** → Contract tests must pass (currently xfail)

**Key Implementation Files**:
- **`app/os_adapters/windows.py`** → Remove NotImplementedError, add real implementations
- **Windows UI Automation** → Replace screen schema placeholder
- **COM Objects** → Outlook.Application for mail operations
- **Win32 APIs** → Screenshots, permissions, file operations

**Future Implementation Notes** (embedded in stubs):
- Detailed docstrings with implementation guidance
- API references and code patterns
- Error handling strategies
- Integration points with existing codebase

**Enhanced Metrics** - `/metrics` exposes comprehensive JSON with Phase 3 indicators:
```json
{
  "success_rate_24h": 0.94,
  "median_duration_ms_24h": 18200,
  "p95_duration_ms_24h": 41000,
  "approvals_required_24h": 12,
  "approvals_granted_24h": 10,
  "web_step_success_rate_24h": 0.92,
  "recovery_applied_24h": 5,
  "verifier_pass_rate_24h": 0.89,
  "schema_captures_24h": 47,
  "web_upload_success_rate_24h": 0.96,
  "os_capability_miss_24h": 2,
  "top_errors_24h": [
    {"cluster": "PDF_PARSE_ERROR", "count": 3},
    {"cluster": "WEB_ELEMENT_NOT_FOUND", "count": 2},
    {"cluster": "VERIFIER_TIMEOUT", "count": 2},
    {"cluster": "APPROVAL_DENIED", "count": 1}
  ],
  "rolling_7d": {"success_rate": 0.93, "median_duration_ms": 19000}
}
```

**Phase 3 Metrics**:
- **Verifier Pass Rate**: Verification success rate including auto-retry recovery (24h)
- **Schema Captures**: Number of successful screen schema captures (24h)
- **Web Upload Success Rate**: File upload operation success rate (24h)
- **OS Capability Misses**: Count of unsupported feature encounters (24h)

**Phase 2 Metrics**:
- **Approval Metrics**: Required vs granted approvals (24h)
- **Web Success Rate**: Web automation step success rate (24h)
- **Recovery Applied**: Self-recovery actions triggered (24h)
- **Enhanced Errors**: Web-specific and verifier error clustering

**Dashboard** - Metrics available via API endpoint `/metrics` including:
- Traditional success rates and run counts
- Approval workflow statistics
- Web automation performance
- Recovery action frequency

Security & Privacy
- No external LLM/API calls. Public pages mask PII (emails, names, file paths).

Troubleshooting (macOS)

**Permissions Issues**
- **Screen Recording**: Black screenshots or blank captures → System Settings → Privacy & Security → Screen Recording → add Terminal/Python
- **Mail Automation**: "Not authorized" errors → System Settings → Privacy & Security → Automation → Terminal → Mail (enable)
- **Strict Mode**: Set `PERMISSIONS_STRICT=1` to block execution instead of warning

**Common Failures**
- **"No files found"** → Check query syntax and root paths in `find_files` steps
- **PDF errors** → Ensure input files exist and are valid PDFs
- **Path errors** → Use `~/` for home directory expansion, check file existence
- **AppleScript Mail** → Launch Mail.app once manually, then retry

**Self-Recovery Features** (Phase 2 Enhanced)
- **Auto-directory creation**: `move_to` creates missing output folders automatically
- **Search expansion**: `find_files` with 0 results widens search by one level (once)
- **Web field recovery**: Label synonyms and fallback strategies for web forms
- **Replay tracking**: Recovery actions are logged in step diffs for visibility

**Phase 2 Troubleshooting**

**Web Automation Issues**
- **"Browser not found"** → Run `npx playwright install --with-deps chromium`
- **"Element not found"** → Check label text, try synonyms (氏名 vs 名前 vs Name)
- **"Page timeout"** → Increase timeout in DSL or check network connectivity
- **"Context not found"** → Ensure `open_browser` step creates the context first

**Approval Workflow Issues**
- **"Approval required"** → Use `--auto-approve` flag or check plan for destructive keywords (送信, Submit, Delete)
- **"Approval denied"** → Review plan content and use `--auto-approve` if appropriate

**Template Issues**
- **"Template not found"** → Use `./cli.py templates` to list available templates
- **"Plan validation failed"** → Use `./cli.py validate <file>` to check syntax errors

**Logs & Debugging**
- Use `./cli.py show <run_id>` to view detailed run results
- Error details with line numbers in validation failures  
- Screenshots and step outputs stored in data directory

License
- MIT

## CLI Interface (NEW)

**Command Overview**:
```bash
# Template management
./cli.py templates                    # List available templates
./cli.py template <filename>          # Show template content

# Plan validation and execution  
./cli.py validate <file>              # Validate YAML plan
./cli.py run <file>                   # Execute plan
./cli.py run <file> --auto-approve    # Execute with auto-approval

# Run management
./cli.py list                         # List all runs
./cli.py show <run_id>                # Show run details
```

**Examples**:
```bash
# List available templates
./cli.py templates

# Validate a plan
./cli.py validate plans/templates/weekly_report.yaml

# Run a plan (will prompt for approval if needed)
./cli.py run plans/templates/weekly_report.yaml

# Run with auto-approval for high-risk operations
./cli.py run plans/templates/csv_to_form.yaml --auto-approve

# Check run history
./cli.py list
./cli.py show 1
```

**CLI Advantages**:
- **Pure CLI**: No web dependencies, perfect for automation and scripting
- **Headless Operation**: Ideal for server environments and CI/CD
- **Direct Execution**: Immediate feedback without browser overhead

## Legacy CLI Scripts
- Single run of the weekly template in dry-run mode with sample data:
  - `python scripts/run_plan.py plans/templates/weekly_report.yaml --dry-run --var inbox=./sample_data --var workdir=./data/work --var out_pdf=./data/weekly.pdf`
- Seed 20 runs (dry-run) to validate stability:
  - `python scripts/seed_runs.py plans/templates/weekly_report.yaml --dry-run --n 20 --var inbox=./sample_data --var workdir=./data/work --var out_pdf=./data/weekly.pdf`
- Seed 20 runs (REAL) to record in /runs (opens Preview, creates Mail drafts):
  - `python scripts/seed_runs_real.py plans/templates/weekly_report.yaml --n 20 --sleep 1 --var inbox=./sample_data --var workdir=./data/work --var out_pdf=./data/weekly.pdf`
  - Optional: `export PERMISSIONS_STRICT=1` to block if Screen Recording is missing.

Shields.io Badges
- Example (replace URL with your deployment):
  - Success rate: `https://img.shields.io/endpoint?url=https://your.host/metrics&label=success&query=$.success_rate&suffix=%25`
  - Total runs: `https://img.shields.io/endpoint?url=https://your.host/metrics&label=runs&query=$.total_runs`

## DSL v1.1 Features (Phase 2)

**Core Features**:
- **Version Declaration**: Plans must start with `dsl_version: "1.1"`
- **Conditional Execution**: `when:` expressions support step references like `"{{steps[0].found}} > 0"`
- **Step Output Access**: Reference previous step results via `{{steps[i].field}}` (e.g., `{{steps[0].found}}`, `{{steps[3].page_count}}`)
- **Static Validation**: Prevents referencing future steps in `when` conditions (compile-time check)

**Phase 2 Web Actions**:
- **`open_browser`**: Navigate to websites with context management
- **`fill_by_label`**: Fill form fields with intelligent label matching
- **`click_by_text`**: Click buttons/links with role-based targeting
- **`download_file`**: Download files to specified paths

**Enhanced Self-Recovery**: 
- Auto-directory creation (`move_to`) and search expansion (`find_files`)
- Web form field recovery with label synonyms
- All recovery actions logged in step diffs

**Templates** (Phase 2):
- **`csv_to_form.yaml`** - CSV data to web form submission with approval gates
- **`weekly_report.yaml`** - Updated for v1.1 with conditional steps
- **`weekly_report_split.yaml`** - PDF merge → extract → digest workflow  
- **`downloads_tidy.yaml`** - Automated file organization with pattern matching

**Approval Integration**:
- Automatic risk analysis for destructive actions
- Manual approval workflow for high-risk operations
- Risk categorization and detailed logging

Permissions
- CLI will check and warn about missing permissions; approval blocks if Mail Automation is denied (and optionally Screen Recording with `PERMISSIONS_STRICT=1`).
