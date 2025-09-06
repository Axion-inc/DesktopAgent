from __future__ import annotations

from dataclasses import dataclass
from typing import Set, Dict, Any
from urllib.parse import urlparse
import yaml
import datetime as dt
import zoneinfo


@dataclass
class PolicyDecision:
    allowed: bool
    autopilot: bool
    reason: str | None = None


class PolicyEngine:
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg or {}

    @classmethod
    def from_file(cls, path: str) -> 'PolicyEngine':
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        return cls(data)

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

        return PolicyDecision(True, autopilot_flag, reason=None)

