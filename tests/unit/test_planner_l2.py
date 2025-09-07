from app.planner.l2 import propose_patches
from app.planner.l2 import should_adopt_patch


def test_propose_replace_text_for_synonyms():
    schema = {
        "elements": [
            {"role": "AXWindow", "children": [
                {"role": "AXButton", "label": "提出"}
            ]}
        ]
    }
    failure = {"type": "assert_text", "goal": "送信", "role": "button"}
    patch = propose_patches(schema, failure)
    assert 'replace_text' in patch
    repl = patch['replace_text'][0]
    assert repl['find'] == '送信'
    assert repl['with'] == '提出'
    assert repl['confidence'] >= 0.85


def test_adopt_low_risk_patch_when_confident():
    patch = {
        'replace_text': [{
            'find': '送信', 'with': '提出', 'role': 'button', 'confidence': 0.9
        }]
    }
    policy = {
        'low_risk_auto': True,
        'min_confidence': 0.85
    }
    assert should_adopt_patch(patch, policy) is True


def test_dont_adopt_when_confidence_low():
    patch = {'replace_text': [{'find': '送信', 'with': '提出', 'role': 'button', 'confidence': 0.8}]}
    policy = {'low_risk_auto': True, 'min_confidence': 0.85}
    assert should_adopt_patch(patch, policy) is False
