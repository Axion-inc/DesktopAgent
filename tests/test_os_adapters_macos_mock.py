from app.dsl.runner import Runner


class DummyMail:
    def __init__(self):
        self.last_id = "123"
        self.attachments = []

    def compose(self, to, subject, body):
        return self.last_id

    def attach(self, draft_id, paths):
        self.attachments.extend(paths)

    def save_draft(self, draft_id):
        return None


class DummyPreview:
    def open(self, path):
        return None


def test_runner_with_mock_adapters(monkeypatch):
    plan = {
        "name": "mock run",
        "variables": {},
        "steps": [
            {"log": {"message": "hello"}},
            {"compose_mail": {"to": ["a@example.com"], "subject": "s", "body": "b"}},
            {"attach_files": {"paths": ["/tmp/a.pdf"]}},
            {"save_draft": {}},
        ],
    }
    r = Runner(plan, {}, dry_run=False)
    # Patch adapters
    r.mail = DummyMail()
    r.preview = DummyPreview()
    out1 = r.execute_step("log", {"message": "hello"})
    assert out1["message"] == "hello"
    r.execute_step("compose_mail", {"to": ["a@example.com"], "subject": "s", "body": "b"})
    assert r.state["draft_id"] == "123"
    out3 = r.execute_step("attach_files", {"paths": ["/tmp/a.pdf"]})
    assert "attached" in out3
    out4 = r.execute_step("save_draft", {})
    assert out4["saved"] is True
