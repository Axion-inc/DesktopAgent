import pytest
from unittest.mock import patch

from app.web.engine import exec_batch, get_web_engine, PlaywrightEngine, CDPEngine


def sample_batch():
    return (
        {"allowHosts": ["example.com"], "risk": ["sends"], "maxRetriesPerStep": 1},
        [
            {"id": "a1", "type": "goto", "url": "https://example.com/form"},
            {"id": "a2", "type": "fill_by_label", "label": "氏名", "text": "山田太郎"},
            {"id": "a3", "type": "click_by_text", "text": "提出", "role": "button"},
        ],
        {"screenshotEach": True, "domSchemaEach": True},
    )


def test_exec_batch_cdp_success():
    guards, actions, evidence = sample_batch()
    with patch('app.web.engine.get_config', return_value={
        'web_engine': {
            'engine': 'cdp',
            'cdp': {
                'extension_id': 'test',
                'handshake_token': 'token'
            }
        }
    }):
        res = exec_batch(guards, actions, evidence)
        assert res['status'] == 'success'
        assert res['engine'] == 'cdp'
        batch = res['result']['batch']
        assert len(batch['steps']) == len(actions)
        assert batch['guards']


def test_exec_batch_playwright_unsupported():
    guards, actions, evidence = sample_batch()
    with patch('app.web.engine.get_config', return_value={'web_engine': {'engine': 'playwright'}}):
        engine = get_web_engine()  # PlaywrightEngine
        assert isinstance(engine, PlaywrightEngine)
        res = exec_batch(guards, actions, evidence, engine='playwright')
        assert res['status'] == 'error'
        assert res['engine'] == 'playwright'
        assert 'not supported' in res['error']

