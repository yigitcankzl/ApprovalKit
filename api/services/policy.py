"""Declarative policy engine — evaluate Cedar/Rego-style policy expressions.

Supports a simplified policy DSL that compiles to the existing rule engine
condition format.  This allows rules to be written as human-readable policy
strings instead of JSON condition arrays.

Syntax:
    "amount > 1000 AND connection == 'stripe-prod'"
    "amount > 5000 OR risk_level == 'critical'"
    "billing.country IN ['US', 'CA'] AND amount >= 100"
    "NOT (action == 'read')"

Compiles to the JSON condition format used by evaluate_conditions().
"""

import re
from typing import Any

_TOKEN_RE = re.compile(
    r"""
    (?P<string>'[^']*'|"[^"]*")  |  # quoted strings
    (?P<number>\d+(?:\.\d+)?)     |  # numbers
    (?P<list>\[[^\]]*\])          |  # lists
    (?P<op>>=|<=|!=|==|>|<)       |  # operators
    (?P<kw>AND|OR|NOT|IN|NOT_IN)  |  # keywords (case sensitive)
    (?P<field>[a-zA-Z_][\w.]*)    |  # field names (dot notation)
    (?P<lparen>\()                 |
    (?P<rparen>\))                 |
    \s+                               # whitespace (skip)
    """,
    re.VERBOSE,
)

_OP_MAP = {
    "==": "eq",
    "!=": "ne",
    ">": "gt",
    ">=": "gte",
    "<": "lt",
    "<=": "lte",
    "IN": "in",
    "NOT_IN": "not_in",
}


def _parse_value(raw: str) -> Any:
    """Parse a literal value from a policy expression."""
    raw = raw.strip()
    if raw.startswith(("'", '"')):
        return raw[1:-1]
    if raw.startswith("["):
        inner = raw[1:-1]
        items = [_parse_value(x.strip()) for x in inner.split(",") if x.strip()]
        return items
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def compile_policy(expression: str) -> list[dict]:
    """Compile a policy expression string into the JSON condition format.

    Returns a list of condition dicts compatible with evaluate_conditions().

    Examples:
        compile_policy("amount > 1000")
        → [{"field": "amount", "operator": "gt", "value": 1000}]

        compile_policy("amount > 1000 AND connection == 'stripe'")
        → [{"field": "amount", "operator": "gt", "value": 1000},
           {"field": "connection", "operator": "eq", "value": "stripe"}]

        compile_policy("amount > 5000 OR risk == 'critical'")
        → [{"logic": "or", "conditions": [...]}]
    """
    tokens = []
    for m in _TOKEN_RE.finditer(expression):
        for name in ("string", "number", "list", "op", "kw", "field", "lparen", "rparen"):
            val = m.group(name)
            if val is not None:
                tokens.append((name, val))
                break

    # Simple two-pass parser: split by OR first, then parse AND groups
    or_groups: list[list[tuple]] = [[]]
    for tok_type, tok_val in tokens:
        if tok_type == "kw" and tok_val == "OR":
            or_groups.append([])
        else:
            or_groups[-1].append((tok_type, tok_val))

    def _parse_and_group(toks: list[tuple]) -> list[dict]:
        conditions = []
        i = 0
        # Filter out AND keywords
        filtered = [(t, v) for t, v in toks if not (t == "kw" and v == "AND")]
        while i < len(filtered):
            t, v = filtered[i]
            if t == "field":
                field = v
                if i + 2 < len(filtered):
                    op_type, op_val = filtered[i + 1]
                    val_type, val_raw = filtered[i + 2]
                    if op_type == "op":
                        operator = _OP_MAP.get(op_val, "eq")
                        value = _parse_value(val_raw)
                        conditions.append({"field": field, "operator": operator, "value": value})
                        i += 3
                        continue
                    elif op_type == "kw" and op_val in ("IN", "NOT_IN"):
                        operator = _OP_MAP[op_val]
                        value = _parse_value(val_raw)
                        conditions.append({"field": field, "operator": operator, "value": value})
                        i += 3
                        continue
            i += 1
        return conditions

    and_groups = [_parse_and_group(g) for g in or_groups]

    if len(and_groups) == 1:
        return and_groups[0]
    else:
        # Multiple OR groups → wrap in OR logic
        all_conditions = []
        for group in and_groups:
            if len(group) == 1:
                all_conditions.extend(group)
            else:
                all_conditions.append({"logic": "and", "conditions": group})
        return [{"logic": "or", "conditions": all_conditions}]


def validate_policy(expression: str) -> dict:
    """Validate a policy expression and return compilation result.

    Returns {"valid": bool, "conditions": list|None, "error": str|None}.
    """
    try:
        conditions = compile_policy(expression)
        return {"valid": True, "conditions": conditions, "error": None}
    except Exception as e:
        return {"valid": False, "conditions": None, "error": str(e)}
