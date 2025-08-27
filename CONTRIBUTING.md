# Contributing to Desktop Agent

Thank you for your interest in contributing to Desktop Agent! This document outlines how to contribute effectively to our enterprise automation platform.

## Development Workflow

### Branching Strategy
- **Main Branch**: `main` - Production-ready code with comprehensive CI validation
- **Feature Branches**: `feat/<short-description>` - New features and enhancements
- **Bugfix Branches**: `fix/<issue-description>` - Bug fixes and patches
- **Phase Branches**: `phase/<number>-<feature>` - Major phase development (Phase 6 Marketplace β)

### Commit Standards
**Use Conventional Commits format:**
```
<type>: <description>

[optional body]

[optional footer]
```

**Types:**
- `feat:` - New feature (marketplace, signing, plugins)
- `fix:` - Bug fix
- `docs:` - Documentation updates
- `test:` - Adding or updating tests (TDD methodology)
- `refactor:` - Code refactoring without behavior changes
- `security:` - Security-related changes (signatures, sandbox, RBAC)

**Examples:**
```
feat: implement Ed25519 template signing system
fix: resolve manifest validation schema errors
security: add plugin sandbox network restrictions
test: add TDD tests for marketplace submission flow
docs: update Phase 6 setup instructions
```

## Code Quality Standards

### Linting and Formatting
```bash
# Run flake8 linter
flake8 app/ tests/ --max-line-length=100

# Check import sorting
isort app/ tests/ --check-only

# Format code (if using black)
black app/ tests/ --line-length=100
```

### Testing Requirements

**Test-Driven Development (TDD)**
We follow red→green→refactor TDD methodology:

1. **Red**: Write failing tests first
2. **Green**: Implement minimal code to make tests pass  
3. **Refactor**: Improve code while keeping tests green

**Test Coverage Requirements:**
- **Unit Tests**: All new functionality must have unit tests
- **Integration Tests**: API endpoints and system integrations
- **End-to-End Tests**: Critical user flows (marketplace submission→installation)
- **Security Tests**: Authentication, authorization, and sandbox validation

**Running Tests:**
```bash
# Unit tests only
pytest tests/unit/ -v

# All tests except E2E
pytest tests/ -v -k "not e2e"

# E2E tests (requires running server)
uvicorn app.main:app --port 8000 &
pytest tests/e2e/ -v --maxfail=3

# Phase 6 specific tests
pytest tests/unit/test_signing.py tests/unit/test_manifest.py -v
```

### Code Organization

**Application Structure:**
```
app/
├── security/           # Phase 6: Signing, manifest, trust store
├── webx/              # Phase 5: WebX marketplace integration  
├── plugins/           # Phase 6: Plugin system and sandbox
├── review/            # Phase 6: Enhanced review UI components
├── web/               # WebX integrity, engine config
├── middleware/        # Phase 4: RBAC authentication
├── queue/             # Phase 4: Queue management
└── metrics/           # Monitoring and analytics

tests/
├── unit/              # Unit tests (TDD methodology)
├── e2e/               # End-to-end integration tests
├── contract/          # Cross-platform contract tests
└── security/          # Security-focused test suites
```

## Phase 6 Development Guidelines

### Template Marketplace β

**Submission Pipeline Development:**
- Templates must pass validation, manifest generation, and dry-run testing
- Integration with Ed25519 signing system required
- Risk analysis and approval gate integration mandatory
- UI components must support Japanese and English localization

**Security Requirements:**
- All marketplace operations require RBAC authentication
- Template submissions must validate against manifest schema
- High-risk templates (sends/deletes/overwrites) require approval workflow
- Trust store validation for all signed templates

### Ed25519 Signing System

**Cryptographic Standards:**
- Use only Ed25519 elliptic curve cryptography
- SHA-256 for template content hashing
- Base64 encoding for signature serialization
- JSON signature format with metadata (key_id, created_at, algo)

**Trust Store Management:**
- YAML-based trust store configuration
- Hierarchical trust levels: system > commercial > development > community > unknown
- Key rotation and revocation support
- Author identity validation with da:YYYY:author format

### Plugin System Development

**Security Sandbox Requirements:**
- Network access must be completely blocked
- File IO restricted to ~/PluginsWork/ directory only
- Execution timeouts enforced (default: 30 seconds)
- Import validation against dangerous patterns (subprocess, eval, exec)
- Plugin allowlist enforcement with admin approval

**Plugin Interface Standards:**
```python
def register(actions_registry):
    """Required registration function for all plugins"""
    actions_registry.register('action_name', action_function)

def action_function(*args, **kwargs):
    """Plugin actions must return success/error dict format"""
    return {"success": True, "result": "action completed"}
```

### WebX Integrity Checking

**Host Permissions Validation:**
- Template URLs must be validated against extension host_permissions
- Risk-based safety: block high-risk templates on permission mismatch
- Warning-only for low-risk templates with mismatched permissions
- Engine-agnostic design supporting Extension and Playwright modes

## Pull Request Guidelines

### PR Requirements

**Before Submitting:**
1. **Code Quality**: Pass all linting checks (flake8, isort)
2. **Test Coverage**: Include comprehensive test suite (TDD methodology)
3. **Security Review**: Consider security implications for all changes
4. **Documentation**: Update relevant documentation (README, SECURITY, this file)
5. **Performance**: Ensure no regression in metrics or performance

**PR Description Template:**
```markdown
## Summary
Brief description of changes and motivation

## Phase 6 Components
- [ ] Marketplace β functionality
- [ ] Ed25519 signing system
- [ ] Plugin system changes
- [ ] WebX integrity checking
- [ ] Enhanced review UI

## Testing
- [ ] Unit tests added (TDD methodology)
- [ ] Integration tests added
- [ ] E2E tests updated
- [ ] Security tests included
- [ ] Manual testing completed

## Security Considerations
Any security implications or changes to threat model

## Screenshots
For UI changes, include before/after screenshots

## Breaking Changes
List any breaking changes and migration path
```

### Review Process

**Review Criteria:**
1. **Code Quality**: Readable, maintainable, follows project conventions
2. **Security**: No introduction of security vulnerabilities
3. **Test Coverage**: Comprehensive test suite with TDD methodology
4. **Documentation**: Up-to-date documentation and comments
5. **Performance**: No significant performance regression
6. **Backwards Compatibility**: Maintain compatibility where possible

**Required Reviewers:**
- **Security Changes**: Require security-focused review
- **Phase 6 Features**: Core maintainer review required
- **Breaking Changes**: Multiple maintainer approval
- **Plugin System**: Sandbox security validation required

## Development Environment

### Setup Instructions
```bash
# Clone repository
git clone https://github.com/Axion-inc/DesktopAgent.git
cd DesktopAgent

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Setup development data
./scripts/dev_setup_macos.sh
```

### Pre-commit Hooks
```bash
# Install and configure pre-commit
pip install pre-commit
pre-commit install

# Pre-commit configuration includes:
# - flake8 linting
# - isort import sorting
# - Security scanning (bandit)
# - Test validation
```

### Phase 6 Development Setup
```bash
# Initialize signing keys for development
./scripts/init_signing_keys.sh --dev

# Create development trust store
./cli.py admin trust-store init --dev-mode

# Configure plugin allowlist
./cli.py admin plugins allowlist add clipboard_actions

# Start development server with marketplace
uvicorn app.main:app --reload --port 8000

# Access marketplace UI
open http://localhost:8000/market
```

## Community Guidelines

### Issue Reporting
- **Bug Reports**: Include reproduction steps, logs, and system information
- **Feature Requests**: Describe use case and expected behavior clearly
- **Security Issues**: Use GitHub Security Advisory or private email
- **Phase 6 Feedback**: Tag issues with `phase-6` label for marketplace/security features

### Feature Development Priority
1. **Phase 6 Completion**: Marketplace β, signing system, plugins, WebX integrity
2. **Security Enhancements**: RBAC, sandbox improvements, trust store management  
3. **UI/UX Improvements**: Review interface, marketplace browsing, approval workflows
4. **Performance Optimization**: Template validation, signature verification, plugin loading
5. **Cross-platform Support**: Windows implementation, contract test compliance

### Getting Help
- **Documentation**: Check README.md and docs/ directory first
- **Issues**: Search existing issues before creating new ones
- **Discussions**: Use GitHub Discussions for questions and architecture discussions
- **Security**: Contact f.kazuma0917@gmail.com for security-related questions

## License
By contributing to Desktop Agent, you agree that your contributions will be licensed under the MIT License.

