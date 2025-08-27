# Phase 6: WebX Ecosystem & Security Documentation

## Overview

Phase 6 implements a comprehensive security framework for template distribution and WebX plugin management, featuring Ed25519 digital signatures, trust management, marketplace β, and plugin sandboxing.

## Core Components

### 1. Template Signing System

**Files:**
- `scripts/da_keygen.py` - Ed25519 key generation
- `scripts/da_sign.py` - Template signing  
- `scripts/da_verify.py` - Signature verification

**Usage:**
```bash
# Generate key pair
python scripts/da_keygen.py da:2025:alice

# Sign template
python scripts/da_sign.py plans/templates/example.yaml keys/da_2025_alice_private.pem

# Verify signature
python scripts/da_verify.py plans/templates/example.yaml
```

### 2. Trust Store & Policy Engine

**Files:**
- `configs/trust_store.yaml` - Trusted keys registry
- `configs/policy.yaml` - Security policies  
- `app/security/policy_engine.py` - Policy enforcement

**Trust Levels:**
- `system` (100) - Highest trust, auto-execute
- `commercial` (80) - Verified publishers
- `development` (60) - Dev keys, requires confirmation
- `community` (40) - Community developers
- `unknown` (0) - Unsigned templates

### 3. Template Manifest System

**Files:**
- `app/security/template_manifest.py` - Manifest management

**CLI Commands:**
```bash
# Generate manifest
python -m app.cli manifest generate plans/templates/example.yaml

# Validate manifest  
python -m app.cli manifest validate example.manifest.json

# List capabilities
python -m app.cli manifest capabilities
```

**Manifest Structure:**
```json
{
  "manifest_version": "1.0",
  "name": "example_template",
  "version": "1.0.0", 
  "capabilities": [
    {
      "name": "ui_interaction",
      "risk_level": "low",
      "justification": "Required for form filling"
    }
  ],
  "signature_info": {
    "algorithm": "ed25519",
    "key_id": "da:2025:alice"
  }
}
```

### 4. Marketplace β

**Files:**
- `app/webx/marketplace_beta.py` - Submission pipeline
- `app/api/marketplace_beta.py` - API endpoints

**Pipeline:** `submit → verify → dry-run → install`

**API Endpoints:**
- `POST /api/marketplace-beta/submit` - Submit template
- `GET /api/marketplace-beta/submissions` - List submissions
- `POST /api/marketplace-beta/submissions/{id}/review` - Review (admin)
- `POST /api/marketplace-beta/submissions/{id}/publish` - Publish (admin)

### 5. WebX Integrity & Permission System

**Files:**
- `app/webx/integrity_checker.py` - Component integrity verification
- `app/webx/plugin_sandbox.py` - Plugin sandboxing

**Permission Levels:**
- `none` - No restrictions
- `minimal` - Basic APIs only
- `standard` - UI interaction allowed
- `strict` - Read-only DOM
- `maximum` - Minimal API access

**Sandbox Configurations:**
- Memory limits: 64MB - 512MB
- Time limits: 30s - 300s
- API restrictions per level
- DOM access controls

## Security Features

### Runtime Verification
- Templates verified before execution
- Hash integrity checking
- Trust level enforcement
- Policy violation blocking

### Plugin Security
- Capability-based permissions
- Sandboxed execution environments
- API access control
- Resource limits

### Monitoring & Metrics
Phase 6 adds 8 new KPIs to the dashboard:
- `templates_verified_24h` - Templates verified daily
- `unsigned_blocked_24h` - Unsigned templates blocked
- `trust_keys_active` - Active trust keys
- `marketplace_submissions_24h` - Daily submissions
- `marketplace_approval_rate` - Approval percentage
- `webx_plugins_sandboxed` - Plugins in sandbox
- `webx_blocked_plugins` - Blocked plugins
- `webx_sandbox_success_rate` - Sandbox execution success

## Integration

### Template Execution Flow
1. Load template file
2. Check for `.manifest.json` file
3. Validate manifest and capabilities
4. Verify signature if present
5. Check policy (allow/block/confirm)
6. Execute in appropriate sandbox level

### WebX Extension Flow  
1. Extension connects via native messaging
2. Integrity checker verifies components
3. Permissions granted based on capabilities
4. Requests validated against permissions
5. Plugin code executed in sandbox

## Configuration

### Trust Store Entry Example
```yaml
trusted_keys:
  "da:2025:primary":
    public_key: "b8f5d2c4e7a9b1c6d3f8e4a7b2c9d6f1e8a5b2c9d6f3e0a7b4c1d8e5a2b9c6f3"
    key_type: "ed25519"
    trust_level: "system"
    valid_from: "2025-01-01T00:00:00+09:00"
    valid_until: "2026-12-31T23:59:59+09:00"
```

### Policy Configuration Example
```yaml
template_execution:
  signature_required: true
  allow_unsigned: false
  trust_level_policies:
    system:
      execution: "auto"
      sandbox_level: "none"
    unknown:
      execution: "block"
      sandbox_level: "maximum"
```

## Security Model

### Defense in Depth
1. **Code Signing** - Ed25519 signatures verify authenticity
2. **Trust Management** - Hierarchical trust levels
3. **Capability System** - Explicit permission declarations  
4. **Sandboxing** - Isolated execution environments
5. **Policy Enforcement** - Configurable security policies
6. **Integrity Checking** - Runtime component verification
7. **Audit Logging** - Comprehensive security event logs

### Threat Mitigation
- **Supply Chain Attacks** - Signature verification blocks tampered templates
- **Privilege Escalation** - Capability system limits access
- **Code Injection** - Sandboxing contains malicious code  
- **Resource Exhaustion** - Resource limits prevent DoS
- **Data Exfiltration** - Permission system controls data access

## Deployment

### Production Setup
1. Generate production signing keys with `da_keygen.py`
2. Configure `trust_store.yaml` with authorized keys
3. Set `policy.yaml` to enforce signature requirements
4. Enable marketplace β for template distribution
5. Configure WebX extensions with integrity hashes

### Development Setup
1. Set `dev_mode_enabled: true` in policy configuration
2. Allow unsigned templates for testing
3. Use lower trust levels for development keys
4. Enable debug logging for troubleshooting

## Compliance

Phase 6 provides security controls supporting:
- **SOC 2** - Access control, logging, monitoring
- **GDPR** - Data protection and audit trails  
- **Zero Trust** - Verify everything, trust nothing
- **Enterprise Security** - RBAC integration, centralized policies

## API Reference

All Phase 6 APIs are documented with OpenAPI schemas and protected by RBAC. Access the interactive documentation at `/docs` when running the application.

Key API groups:
- `/api/webx/plugins/*` - Plugin management
- `/api/marketplace-beta/*` - Template marketplace
- Authentication required for all endpoints
- Admin privileges needed for publishing and system configuration