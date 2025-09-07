from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeviationVerdict:
    should_pause: bool
    reason: str | None = None


class AutoRunner:
    def notify(self, reason: str):
        # Placeholder for CLI/Slack notification hook
        try:
            from app.metrics import get_metrics_collector
            get_metrics_collector().mark_deviation_stop()
        except Exception:
            pass
        # Optional Slack webhook
        try:
            import os, json, urllib.request
            url = os.environ.get('SLACK_WEBHOOK_URL')
            if url:
                data = json.dumps({
                    'text': f":warning: L4 deviation stop: {reason}"
                }).encode('utf-8')
                req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
                urllib.request.urlopen(req, timeout=3)
        except Exception:
            pass

    def check_deviation(self, steps: list[dict], current_url: str, expected_domain: str,
                         downloads_failed: int = 0, retry_exceeded: bool = False) -> DeviationVerdict:
        # Verifier failure
        for s in steps:
            status = str(s.get('status', '')).upper()
            if status in ('FAIL', 'ERROR'):
                self.notify('verifier')
                return DeviationVerdict(True, reason='verifier')
        # Domain drift
        from urllib.parse import urlparse
        host = (urlparse(current_url).hostname or '')
        if not (host == expected_domain or host.endswith('.' + expected_domain)):
            self.notify('domain')
            return DeviationVerdict(True, reason='domain')
        # Download verification failed
        if downloads_failed and downloads_failed > 0:
            self.notify('download')
            return DeviationVerdict(True, reason='download')
        # Retry exceeded
        if retry_exceeded:
            self.notify('retry')
            return DeviationVerdict(True, reason='retry')
        return DeviationVerdict(False, reason=None)
