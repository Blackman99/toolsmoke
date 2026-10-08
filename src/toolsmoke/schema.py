"""A deliberately small JSON Schema subset validator (and sample generator).

Covers what tool parameter schemas and structured-output schemas use in
practice: type, properties, required, additionalProperties, enum, const,
items, minItems/maxItems, minimum/maximum, anyOf. No dependencies.
"""

from __future__ import annotations

from typing import Any, Dict, List

_TYPES = {
    "string": lambda v: isinstance(v, str),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "null": lambda v: v is None,
}


def validate(value: Any, schema: Dict[str, Any], path: str = "$") -> List[str]:
    """Return a list of human-readable violations (empty list == valid)."""
    errors: List[str] = []
    if not isinstance(schema, dict) or not schema:
        return errors

    if "anyOf" in schema:
        branches = [validate(value, s, path) for s in schema["anyOf"]]
        if all(branches):
            errors.append(f"{path}: matches none of anyOf")
        return errors

    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_TYPES.get(tt, lambda v: True)(value) for tt in types):
            errors.append(f"{path}: expected {'/'.join(types)}, got {_type_name(value)}")
            return errors

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in enum {schema['enum']}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} < minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value} > maximum {schema['maximum']}")

    if isinstance(value, dict):
        props = schema.get("properties", {})
        for req in schema.get("required", []):
            if req not in value:
                errors.append(f"{path}: missing required property '{req}'")
        for k, v in value.items():
            if k in props:
                errors.extend(validate(v, props[k], f"{path}.{k}"))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: unexpected property '{k}'")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: more than {schema['maxItems']} items")
        if isinstance(schema.get("items"), dict):
            for i, item in enumerate(value):
                errors.extend(validate(item, schema["items"], f"{path}[{i}]"))
    return errors


def _type_name(v: Any) -> str:
    for name in ("null", "boolean", "integer", "number", "string", "array", "object"):
        if _TYPES[name](v):
            return name
    return type(v).__name__


def sample(schema: Dict[str, Any], hints: Dict[str, Any] = None) -> Any:
    """Produce a value that satisfies `schema` (used by the mock server)."""
    hints = hints or {}
    if "const" in schema:
        return schema["const"]
    if "enum" in schema:
        return schema["enum"][0]
    if "anyOf" in schema:
        return sample(schema["anyOf"][0], hints)
    t = schema.get("type", "object")
    if isinstance(t, list):
        t = next((x for x in t if x != "null"), "null")
    if t == "object":
        out = {}
        props = schema.get("properties", {})
        for k, sub in props.items():
            out[k] = hints[k] if k in hints else sample(sub, hints)
        return out
    if t == "array":
        n = max(1, schema.get("minItems", 1))
        return [sample(schema.get("items", {"type": "string"}), hints) for _ in range(n)]
    if t == "string":
        return "example"
    if t == "integer":
        return int(schema.get("minimum", 1))
    if t == "number":
        return float(schema.get("minimum", 21.5))
    if t == "boolean":
        return True
    return None
