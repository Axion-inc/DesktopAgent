from types import SimpleNamespace
from pathlib import Path
from app.desktop.inspect import desktop_inspect


class FakeAdapter:
    def __init__(self, root: Path):
        self.root = root
    def take_screenshot(self, dest_path: str) -> None:
        p = Path(dest_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"PNG")
    def capture_screen_schema(self, target: str = "frontmost"):
        return {"platform": "macos", "target": target, "elements": []}


def test_desktop_inspect_saves_files(tmp_path):
    def get_adapter():
        return FakeAdapter(tmp_path)

    res = desktop_inspect(output_dir=str(tmp_path / 'out'), target='frontmost', get_adapter=get_adapter)
    assert Path(res['dir']).exists()
    assert Path(res['screenshot']).exists()
    assert Path(res['schema']).exists()
