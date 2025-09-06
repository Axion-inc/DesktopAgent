import os
from pathlib import Path

from app.policy.engine import PolicyEngine, PolicyDecision


def write_policy(tmp_path: Path, text: str) -> str:
    p = tmp_path / 'policy.yaml'
    p.write_text(text, encoding='utf-8')
    return str(p)


def test_policy_blocks_outside_domain_and_time(tmp_path, monkeypatch):
    policy_yaml = """
autopilot: true
allow_domains: ["partner.example.com"]
allow_risks: ["sends"]
window: "SUN 00:00-06:00 Asia/Tokyo"
require_signed_templates: true
require_capabilities: ["webx"]
"""
    path = write_policy(tmp_path, policy_yaml)
    pe = PolicyEngine.from_file(path)

    decision = pe.evaluate(
        url="https://evil.example.com/form",
        risks={"sends"},
        now_iso="2024-08-17T12:00:00+09:00",  # Saturday noon JST, outside window
        signed=False,
        capabilities={"webx"},
    )
    assert decision.allowed is False
    assert decision.reason
    assert 'domain' in decision.reason or 'window' in decision.reason


def test_policy_allows_inside_window_with_signature_and_caps(tmp_path):
    policy_yaml = """
autopilot: true
allow_domains: ["partner.example.com"]
allow_risks: ["sends"]
window: "SAT 11:00-13:00 Asia/Tokyo"
require_signed_templates: true
require_capabilities: ["webx"]
"""
    path = write_policy(tmp_path, policy_yaml)
    pe = PolicyEngine.from_file(path)

    decision = pe.evaluate(
        url="https://partner.example.com/form",
        risks={"sends"},
        now_iso="2024-08-17T12:00:00+09:00",  # Saturday noon JST
        signed=True,
        capabilities={"webx", "other"},
    )
    assert decision.allowed is True
    assert decision.autopilot is True

