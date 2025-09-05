# Desktop Inspect (Phase 4)

Captures a desktop snapshot for planning/verification: a full-screen screenshot and a screen schema (accessibility tree summary).

## Usage

- CLI
  - `python -m app.cli desktop-inspect --target frontmost`
  - Options:
    - `--output-dir DIR`: where to save artifacts (default: `metrics.artifacts_directory/desktop/YYYYMMDD`)
    - `--target frontmost|screen`: scope for schema capture

- Output
  - Directory: `artifacts/desktop/YYYYMMDD/`
  - Files: `screenshot_HHMMSS.png`, `schema_HHMMSS.json`

## Notes
- macOS: Uses JavaScript for Automation (JXA) via System Events to capture roles/labels/bounds of UI elements (limited depth and children for performance). Requires Accessibility permissions (System Settings → Security & Privacy) and Screen Recording permission for screenshots.
- Windows: Not implemented in this phase.

