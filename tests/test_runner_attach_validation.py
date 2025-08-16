from app.dsl.runner import Runner


class DummyMail:
    def __init__(self):
        self.attached = []

    def compose(self, to, subject, body):
        return "1"

    def attach(self, draft_id, paths):
        self.attached.extend(paths)

    def save_draft(self, draft_id):
        return None


class DummyPreview:
    def open(self, path):
        return None


def test_attach_files_missing_path_raises():
    plan = {"name": "t", "variables": {}, "steps": []}
    r = Runner(plan, {}, dry_run=False)
    r.mail = DummyMail()
    r.preview = DummyPreview()
    r.state["draft_id"] = "1"
    try:
        r.execute_step("attach_files", {"paths": ["/path/not/exist.pdf"]})
        assert False, "expected FileNotFoundError"
    except FileNotFoundError as e:
        assert "missing paths" in str(e)

