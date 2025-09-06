from app.planner.l2 import propose_patches


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

