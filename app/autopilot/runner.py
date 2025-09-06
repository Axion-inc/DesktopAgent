from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeviationVerdict:
    should_pause: bool
    reason: str | None = None


class AutoRunner:
    def check_deviation(self, steps: list[dict], current_url: str, expected_domain: str) -> DeviationVerdict:
        # Verifier failure
        for s in steps:
            status = str(s.get('status', '')).upper()
            if status in ('FAIL', 'ERROR'):
                return DeviationVerdict(True, reason='verifier')
        # Domain drift
        from urllib.parse import urlparse
        host = (urlparse(current_url).hostname or '')
        if not (host == expected_domain or host.endswith('.' + expected_domain)):
            return DeviationVerdict(True, reason='domain')
        return DeviationVerdict(False, reason=None)

