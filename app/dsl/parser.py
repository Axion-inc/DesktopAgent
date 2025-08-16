from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

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
    # Very small templating: {{var}} and {{ var | replace:'a','b' }}
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
            else:
                val = variables.get(key, "")
        out = out[: m.start()] + str(val) + out[m.end() :]
    return out


def parse_yaml(yaml_text: str) -> Dict[str, Any]:
    data = yaml.safe_load(yaml_text)
    if not isinstance(data, dict):
        raise ValueError("Invalid plan YAML: root must be mapping")
    return data
