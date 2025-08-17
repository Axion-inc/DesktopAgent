from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

import ast
import yaml


def render_value(val: Any, variables: Dict[str, Any]) -> Any:
    if isinstance(val, str):
        return render_string(val, variables)
    if isinstance(val, list):
        return [render_value(v, variables) for v in val]
    if isinstance(val, dict):
        return {k: render_value(v, variables) for k, v in val.items()}
    return val


def render_string(s: str, variables: Dict[str, Any]) -> str:
    # Enhanced templating: {{var}}, {{ var | replace:'a','b' }}, and {{steps[i].field}}
    out = s

    def current_date() -> str:
        return datetime.now().strftime("%Y-%m-%d")

    while True:
        import re

        m = re.search(r"{{\s*([^}]+)\s*}}", out)
        if not m:
            break
        expr = m.group(1).strip()
        val = None
        if "|" in expr:
            var_part, filt_part = [p.strip() for p in expr.split("|", 1)]
            if var_part == "date":
                val = current_date()
            elif var_part.startswith("steps["):
                # Handle steps[i].field with filters
                val = _resolve_steps_reference(var_part, variables)
            else:
                val = str(variables.get(var_part, ""))
            # only support replace:'x','y'
            if filt_part.startswith("replace"):
                args_m = re.search(r"replace\s*:\s*'([^']*)'\s*,\s*'([^']*)'", filt_part)
                if args_m:
                    a, b = args_m.group(1), args_m.group(2)
                    val = str(val).replace(a, b)
        else:
            key = expr
            if key == "date":
                val = current_date()
            elif key.startswith("steps["):
                # Handle steps[i].field references
                val = _resolve_steps_reference(key, variables)
            else:
                val = variables.get(key, "")
        out = out[: m.start()] + str(val) + out[m.end() :]
    return out


def _resolve_steps_reference(steps_ref: str, variables: Dict[str, Any]) -> Any:
    """Resolve steps[i].field references from step results."""
    import re
    
    # Parse steps[i].field format
    match = re.match(r"steps\[(\d+)\]\.(\w+)", steps_ref)
    if not match:
        return ""
    
    try:
        step_idx = int(match.group(1))
        field_name = match.group(2)
        
        # Get steps from variables context
        steps = variables.get("steps", [])
        if step_idx < len(steps) and isinstance(steps[step_idx], dict):
            return steps[step_idx].get(field_name, "")
        return ""
    except (ValueError, IndexError, KeyError):
        return ""


def parse_yaml(yaml_text: str) -> Dict[str, Any]:
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:  # type: ignore[attr-defined]
        # Include line/column if available
        msg = str(e)
        raise ValueError(f"YAML parse error: {msg}") from e
    if not isinstance(data, dict):
        raise ValueError("Invalid plan YAML: root must be mapping")
    return data


class SafeEval(ast.NodeVisitor):
    ALLOWED_NODES = (
        ast.Expression,
        ast.BoolOp,
        ast.BinOp,
        ast.UnaryOp,
        ast.Compare,
        ast.Name,
        ast.Load,
        ast.Constant,
        ast.Subscript,
        ast.Index,
        ast.Tuple,
        ast.List,
        ast.Dict,
        ast.And,
        ast.Or,
        ast.Not,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Mod,
    )

    def visit(self, node):  # type: ignore[override]
        if not isinstance(node, self.ALLOWED_NODES):
            raise ValueError("unsafe expression")
        return super().visit(node)


def safe_eval(expr: str, context: Dict[str, Any]) -> Any:
    tree = ast.parse(expr, mode="eval")
    SafeEval().visit(tree)
    code = compile(tree, "<expr>", "eval")
    return eval(code, {"__builtins__": {}}, context)
