from app.dsl.parser import parse_yaml, render_string, render_value


def test_render_string_basic_and_replace():
    vars = {"inbox": "~/Downloads", "out": "~/Reports/sample.pdf"}
    s = "{{inbox}}/{{date}}.pdf"
    out = render_string(s, vars)
    assert out.endswith(".pdf")
    s2 = "{{out | replace:'.pdf','_digest.pdf'}}"
    out2 = render_string(s2, vars)
    assert out2.endswith("_digest.pdf")


def test_parse_yaml_and_render_values():
    text = """
name: test
variables:
  inbox: "~/Downloads"
steps:
  - find_files: { query: "kind:pdf", roots: ["{{inbox}}"], limit: 10 }
    """
    plan = parse_yaml(text)
    assert plan["name"] == "test"
    step = plan["steps"][0]
    action, params = list(step.items())[0]
    assert action == "find_files"
    rendered = render_value(params, plan.get("variables", {}))
    assert "{{" not in str(rendered)
