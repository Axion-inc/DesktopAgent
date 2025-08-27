# Security Policy

## Reporting Security Vulnerabilities

**Please report security vulnerabilities responsibly:**

- **GitHub Security Advisory**: Use [GitHub Security Advisory](https://github.com/Axion-inc/DesktopAgent/security/advisories) for public coordination
- **Private Email**: f.kazuma0917@gmail.com for sensitive issues
- **Response Time**: We aim to acknowledge reports within 72 hours

## Phase 6 Security Features 🔒

### Template Marketplace β Security

**Ed25519 Digital Signatures**
- All templates support cryptographic signing with Ed25519 private keys
- SHA-256 hash verification ensures template integrity
- Trust store system with hierarchical trust levels (system/commercial/development/community/unknown)
- Runtime signature verification before template execution

**Risk Analysis & Approval Gates**
- Automatic detection of high-risk operations (sends/deletes/overwrites)
- Mandatory approval workflow for templates with critical risk flags  
- Risk-based execution blocking with configurable enterprise policies
- Template capability manifests with required permission declarations

**Plugin Security Sandbox**
- Network access blocking for all plugin code execution
- File IO restrictions limited to ~/PluginsWork/ directory sandbox
- Execution timeout limits prevent infinite loops and resource exhaustion
- Plugin allowlist system with admin-controlled security approval
- Dynamic code validation against dangerous import patterns

### WebX Integration Security

**Host Permissions Validation**
- Template URL validation against Chrome extension host_permissions
- Permission mismatch detection with risk-based safety enforcement
- High-risk templates blocked on permission violations (sends/deletes/overwrites)
- Low-risk templates show warnings but allow execution
- Engine-agnostic security model supporting Extension and Playwright modes

### Enterprise Security Controls

**Role-Based Access Control (RBAC)**
- Hierarchical user roles: Admin > Editor > Runner > Viewer
- FastAPI middleware with endpoint-level authorization
- Audit logging for all security-sensitive operations
- Session management with request-scoped authentication contexts

**Secrets Management**
- Multi-backend secure credential storage (Keychain/Keyring/encrypted files)
- Template DSL integration with `{{secrets://key}}` syntax
- Automatic secret masking in logs and error outputs
- Compile-time validation of secret references

## Security Best Practices

### For Template Authors

**Template Security Guidelines:**
1. **Sign Templates**: Use Ed25519 signing for template integrity verification
2. **Declare Capabilities**: Specify all required capabilities in template manifests
3. **Minimize Permissions**: Request only necessary capabilities (webx/fs/pdf/mail_draft)
4. **Risk Awareness**: Understand risk flags and approval requirements for destructive operations
5. **Test Thoroughly**: Validate templates in dry-run mode before publishing

### For System Administrators

**Deployment Security:**
1. **Configure RBAC**: Set appropriate user roles and permissions
2. **Plugin Allowlist**: Explicitly approve plugins before enabling
3. **Trust Store Management**: Maintain Ed25519 key trust levels appropriately
4. **WebX Permissions**: Configure extension host_permissions accurately
5. **Audit Logging**: Monitor security events and approval workflows

### For End Users

**Execution Safety:**
1. **Verify Signatures**: Only execute templates with valid Ed25519 signatures
2. **Review Risk Flags**: Understand template capabilities before approval
3. **Plugin Awareness**: Be conscious of enabled plugins and their capabilities
4. **Permission Grants**: Only grant necessary macOS permissions (Screen Recording, Automation)

## Threat Model

### Defended Against

**Template Tampering**
- Ed25519 signatures prevent malicious template modification
- SHA-256 integrity checking detects any content changes
- Trust store validation ensures only approved authors

**Malicious Plugins**
- Security sandbox prevents network access and file system escapes
- Plugin allowlist blocks unapproved code execution
- Code validation detects dangerous import patterns

**Permission Escalation**
- RBAC prevents unauthorized admin operations
- WebX permission validation blocks unauthorized domain access
- Capability manifests enforce least-privilege execution

**Data Exfiltration**
- Risk analysis detects templates with "sends" operations
- Approval gates block high-risk templates without explicit approval
- Plugin sandbox prevents network-based data exfiltration

### Known Limitations

**Local System Access**
- Templates executed with user permissions can access user files
- macOS permission grants (Screen Recording/Automation) provide broad system access
- Plugin sandbox relies on Python execution environment isolation

**Social Engineering**
- Users may approve high-risk templates without understanding implications
- Ed25519 signatures only verify integrity, not template safety
- Community templates may contain legitimate but destructive operations

## Security Updates

**Vulnerability Response Process:**
1. **Triage**: Security reports reviewed within 72 hours
2. **Assessment**: Impact analysis and CVSS scoring
3. **Development**: Coordinated fix development with reporter
4. **Testing**: Comprehensive security regression testing
5. **Disclosure**: Coordinated public disclosure with security advisory

**Supported Versions:**
- Latest stable release receives security updates
- Phase 6 introduces enhanced security model
- Legacy versions (Phase 1-5) receive critical security fixes only

