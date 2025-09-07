from app.web.engine import get_web_engine
from unittest.mock import patch


def test_transport_config_ws_default():
    cfg = {
        'web_engine': {
            'engine': 'cdp',
            'common': {},
            'transport': {'type': 'ws', 'ws_url': 'ws://127.0.0.1:8765', 'timeout_sec': 30},
        }
    }
    with patch('app.web.engine.get_config', return_value=cfg):
        engine = get_web_engine()
        assert engine.__class__.__name__ == 'CDPEngine'


def test_transport_config_playwright_explicit():
    cfg = {'web_engine': {'engine': 'playwright'}}
    with patch('app.web.engine.get_config', return_value=cfg):
        engine = get_web_engine()
        assert engine.__class__.__name__ == 'PlaywrightEngine'

