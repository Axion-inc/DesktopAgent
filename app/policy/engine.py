from __future__ import annotations

from dataclasses import dataclass
from typing import Set, Dict, Any, List, Optional
from urllib.parse import urlparse
import yaml
import datetime as dt
import zoneinfo


@dataclass
class PolicyDecision:
    allowed: bool
    autopilot: bool
    reason: str | None = None
    warnings: Optional[List[str]] = None

    # Back-compat alias for Phase 7 L4 autopilot code
    @property
    def autopilot_enabled(self) -> bool:  # pragma: no cover - simple alias
        return self.autopilot


class PolicyViolation(Exception):
    """Exception describing a policy violation with typed category.

    Also used as a simple data holder in tests.
    """

    def __init__(self, type: str, message: str, suggested_action: Optional[str] = None):
        super().__init__(message)
        self.type = type
        self.message = message
        self.suggested_action = suggested_action


class PolicyEngine:
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg or {}

    @classmethod
    def from_file(cls, path: str) -> 'PolicyEngine':
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        return cls(data)

    @classmethod
    def from_dict(cls, cfg: Dict[str, Any]) -> 'PolicyEngine':
        """Construct directly from a config dict (Phase 7 helper)."""
        return cls(cfg or {})

    def evaluate(self, url: str, risks: Set[str], now_iso: str, signed: bool,
                 capabilities: Set[str]) -> PolicyDecision:
        autopilot_flag = bool(self.cfg.get('autopilot', False))

        # Domain check
        host = urlparse(url).hostname or ''
        domains = set(self.cfg.get('allow_domains', []) or [])
        in_domain = any(host == d or host.endswith('.' + d) for d in domains)
        if not in_domain:
            return PolicyDecision(False, False, reason='domain')

        # Time window check e.g. "SUN 00:00-06:00 Asia/Tokyo"
        window = str(self.cfg.get('window', '') or '')
        try:
            day, hhmm, tz = window.split(' ', 2)
            hrs = hhmm.split(' ')[0]
            start_s, end_s = hrs.split('-')
            start_h, start_m = map(int, start_s.split(':'))
            end_h, end_m = map(int, end_s.split(':'))
            tzname = tz.strip()
        except Exception:
            return PolicyDecision(False, False, reason='window_format')

        try:
            now = dt.datetime.fromisoformat(now_iso)
        except Exception:
            now = dt.datetime.now(dt.timezone.utc)
        # Normalize to target TZ
        try:
            tzinfo = zoneinfo.ZoneInfo(tzname)
            now_tz = now.astimezone(tzinfo)
        except Exception:
            now_tz = now

        weekday_map = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
        day_ok = weekday_map[now_tz.weekday()] == day
        start_ok = (now_tz.hour, now_tz.minute) >= (start_h, start_m)
        end_ok = (now_tz.hour, now_tz.minute) <= (end_h, end_m)
        if not (day_ok and start_ok and end_ok):
            return PolicyDecision(False, False, reason='window')

        # Signature
        if self.cfg.get('require_signed_templates', False) and not signed:
            return PolicyDecision(False, False, reason='signature')

        # Capabilities subset
        req_caps = set(self.cfg.get('require_capabilities', []) or [])
        if not req_caps.issubset(capabilities):
            return PolicyDecision(False, False, reason='capabilities')

        # Risks allowed
        allow_risks = set(self.cfg.get('allow_risks', []) or [])
        if not risks.issubset(allow_risks):
            return PolicyDecision(False, False, reason='risk')

        return PolicyDecision(True, autopilot_flag, reason=None, warnings=[])

    # Phase 7: template-manifest based validation used by L4 autopilot
    def validate_execution(self, template_manifest: Dict[str, Any],
                           current_time: Optional[dt.datetime] = None) -> PolicyDecision:
        """Validate a template manifest against policy.

        Expected manifest fields:
        - required_capabilities: List[str]
        - risk_flags: List[str]
        - webx_urls: List[str]
        - signature_verified: bool
        """
        cfg = self.cfg or {}
        warnings: List[str] = []

        # 1) Domains
        urls = list(template_manifest.get('webx_urls') or [])
        domains = set(cfg.get('allow_domains', []) or [])
        if urls and domains:
            def host_ok(u: str) -> bool:
                h = urlparse(u).hostname or ''
                return any(h == d or h.endswith('.' + d) for d in domains)

            if not all(host_ok(u) for u in urls):
                raise PolicyViolation(
                    type="domain_violation",
                    message="Domain not allowed",
                    suggested_action="Update policy allow_domains or change template URLs",
                )

        # 2) Signature requirement
        if cfg.get('require_signed_templates', False):
            if not bool(template_manifest.get('signature_verified', False)):
                raise PolicyViolation(
                    type="signature_violation",
                    message="Template signature verification required",
                    suggested_action="Provide a signed template or disable signature requirement",
                )

        # 3) Capabilities
        req_caps = set(cfg.get('require_capabilities', []) or [])
        tmpl_caps = set(template_manifest.get('required_capabilities', []) or [])
        if not req_caps.issubset(tmpl_caps):
            missing = sorted(req_caps - tmpl_caps)
            raise PolicyViolation(
                type="capability_violation",
                message=f"Missing required capabilities: {', '.join(missing)}",
                suggested_action="Add required_capabilities to template",
            )

        # 4) Risks
        allow_risks = set(cfg.get('allow_risks', []) or [])
        tmpl_risks = set(template_manifest.get('risk_flags', []) or [])
        if not tmpl_risks.issubset(allow_risks):
            blocked = sorted(tmpl_risks - allow_risks)
            raise PolicyViolation(
                type="risk_violation",
                message=f"Blocked risks: {', '.join(blocked)}",
                suggested_action="Adjust allow_risks or modify template actions",
            )

        # 5) Time window (supports "always" or "MON-FRI HH:MM-HH:MM TZ")
        window = str(cfg.get('window', 'always') or 'always')
        if window.lower() != 'always':
            now = current_time or dt.datetime.now(dt.timezone.utc)
            allowed = self._within_window(window, now)
            if not allowed:
                raise PolicyViolation(
                    type="window_violation",
                    message="Execution outside allowed window",
                    suggested_action="Adjust policy window or run within allowed time",
                )

        return PolicyDecision(
            allowed=True,
            autopilot=bool(cfg.get('autopilot', False)),
            reason=None,
            warnings=warnings,
        )

    def _within_window(self, window: str, now: dt.datetime) -> bool:
        """Check if `now` falls within a policy window.

        Supports formats like:
        - "always"
        - "MON-FRI 09:00-17:00 Asia/Tokyo"
        - "MON 09:00-17:00 Asia/Tokyo"
        """
        try:
            days_part, rest = window.split(' ', 1)
            hours_part, tz_part = rest.rsplit(' ', 1)
            start_s, end_s = hours_part.split('-')
            start_h, start_m = map(int, start_s.split(':'))
            end_h, end_m = map(int, end_s.split(':'))
            tzinfo = zoneinfo.ZoneInfo(tz_part)
        except Exception:
            # On format issues, be conservative: deny
            return False

        # Normalize now to target timezone
        try:
            now_tz = now.astimezone(tzinfo)
        except Exception:
            now_tz = now

        weekday_map = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
        today = weekday_map[now_tz.weekday()]

        def day_in_range(spec: str, day: str) -> bool:
            if '-' in spec:
                a, b = spec.split('-', 1)
                try:
                    ia = weekday_map.index(a)
                    ib = weekday_map.index(b)
                    iday = weekday_map.index(day)
                except ValueError:
                    return False
                if ia <= ib:
                    return ia <= iday <= ib
                # Wrap-around (e.g., FRI-MON)
                return iday >= ia or iday <= ib
            return spec == day

        if not day_in_range(days_part, today):
            return False

        start_ok = (now_tz.hour, now_tz.minute) >= (start_h, start_m)
        end_ok = (now_tz.hour, now_tz.minute) <= (end_h, end_m)
        return bool(start_ok and end_ok)
