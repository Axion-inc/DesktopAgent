"""
Execution Guard (Phase 7)
Pre-execution policy checks across domain/time/risk/signature/capabilities
and audit logging. Designed to be called before executing a template.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

import pytz

from .engine import PolicyEngine
from ..metrics import get_metrics_collector


@dataclass
class GuardResult:
    allowed: bool
    reasons: List[str] = field(default_factory=list)
    checks: Dict[str, Dict[str, Any]] = field(default_factory=dict)


def _weekday_from_str(s: str) -> int:
    mapping = {
        'MON': 0, 'TUE': 1, 'WED': 2, 'THU': 3, 'FRI': 4, 'SAT': 5, 'SUN': 6
    }
    return mapping.get(s.upper(), -1)


def _parse_time(hhmm: str) -> time:
    hh, mm = hhmm.split(':')
    return time(int(hh), int(mm))


def _in_time_window(window: str, now: Optional[datetime] = None) -> bool:
    """
    window format: "SUN 00:00-06:00 Asia/Tokyo"
    Supports single-day windows; treats times as local in given TZ.
    """
    try:
        parts = window.strip().split()
        if len(parts) < 3:
            return True  # no window or malformed -> allow by default

        day_str, range_str, tz_str = parts[0], parts[1], parts[2]
        start_str, end_str = range_str.split('-')
        tz = pytz.timezone(tz_str)
        now = now or datetime.now(tz)
        now_local = now.astimezone(tz)

        weekday_ok = now_local.weekday() == _weekday_from_str(day_str)
        if not weekday_ok:
            return False

        start_t = _parse_time(start_str)
        end_t = _parse_time(end_str)
        now_t = now_local.time()
        return start_t <= now_t <= end_t
    except Exception:
        return True  # be permissive if policy is malformed


def _domain_allowed(urls: List[str], allow_domains: List[str]) -> bool:
    if not urls:
        return True
    if not allow_domains:
        return True
    for u in urls:
        try:
            host = urlparse(u).netloc
            if not any(host.endswith(ad) for ad in allow_domains):
                return False
        except Exception:
            # If URL can't be parsed, treat as violation
            return False
    return True


def check_pre_execution(
    manifest: Dict[str, Any],
    urls: List[str],
    policy: Dict[str, Any],
    now: Optional[datetime] = None
) -> GuardResult:
    """
    Evaluate pre-execution policy: domain/time/risk/signature/capabilities.
    Returns GuardResult with per-check details for UI rendering.
    """
    checks: Dict[str, Dict[str, Any]] = {}
    reasons: List[str] = []
    allowed = True

    # Domains
    allow_domains = policy.get('allow_domains', [])
    domains_ok = _domain_allowed(urls, allow_domains)
    checks['allow_domains'] = {
        'passed': domains_ok,
        'message': ', '.join(allow_domains) if allow_domains else 'not restricted'
    }
    if not domains_ok:
        allowed = False
        reasons.append('Domain not permitted by policy')

    # Time window
    window_str = policy.get('window', '')
    window_ok = True if not window_str else _in_time_window(window_str, now)
    checks['time_window'] = {
        'passed': window_ok,
        'message': window_str or 'not restricted'
    }
    if not window_ok:
        allowed = False
        reasons.append('Outside allowed time window')

    # Risks
    allow_risks = set(policy.get('allow_risks', []))
    manifest_risks = set(manifest.get('risk_flags', []))
    risks_ok = manifest_risks.issubset(allow_risks) if allow_risks else True
    checks['risk_flags'] = {
        'passed': risks_ok,
        'message': f"required={sorted(manifest_risks)}; allow={sorted(allow_risks)}"
    }
    if not risks_ok:
        allowed = False
        reasons.append('Risk flags not permitted by policy')

    # Signature
    require_signed = policy.get('require_signed_templates', True)
    signature_ok = True if not require_signed else bool(manifest.get('signature_verified'))
    checks['signature'] = {
        'passed': signature_ok,
        'message': 'signature required' if require_signed else 'not required'
    }
    if not signature_ok:
        allowed = False
        reasons.append('Signature required but not verified')

    # Capabilities
    required_caps = set(policy.get('require_capabilities', []))
    manifest_caps = set(manifest.get('required_capabilities', []))
    caps_ok = manifest_caps.issubset(required_caps) if required_caps else True
    checks['capabilities'] = {
        'passed': caps_ok,
        'message': f"required={sorted(manifest_caps)}; policy={sorted(required_caps)}"
    }
    if not caps_ok:
        allowed = False
        reasons.append('Required capabilities not satisfied by policy')

    # Metrics & audit (only on block)
    if not allowed:
        try:
            get_metrics_collector().mark_policy_block()
        except Exception:
            pass
        _write_policy_audit('block', reasons=reasons, checks=checks, manifest=manifest, urls=urls)

    return GuardResult(allowed=allowed, reasons=reasons, checks=checks)


def _write_policy_audit(
    action: str,
    reasons: List[str],
    checks: Dict[str, Any],
    manifest: Dict[str, Any],
    urls: List[str]
) -> None:
    """Append a JSONL audit record under logs/policy_audit.log"""
    try:
        import json
        from pathlib import Path
        record = {
            'ts': datetime.utcnow().isoformat() + 'Z',
            'action': action,
            'reasons': reasons,
            'checks': checks,
            'manifest_keys': sorted(list(manifest.keys())),
            'urls': urls,
        }
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        with (log_dir / 'policy_audit.log').open('a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        # Best-effort; do not raise
        pass

