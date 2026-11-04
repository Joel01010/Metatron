from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


class SchemaError(ValueError):
    pass


def _type_name(tp: type | tuple[type, ...]) -> str:
    if isinstance(tp, tuple):
        return " or ".join(x.__name__ for x in tp)
    return tp.__name__


def require_object(value: Any, *, name: str = "value") -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SchemaError(f"{name} must be an object")
    return value


def validate_fields(
    value: Any,
    *,
    allowed: dict[str, type | tuple[type, ...]],
    required: tuple[str, ...] = (),
    name: str = "value",
) -> dict[str, Any]:
    obj = require_object(value, name=name)
    unknown = sorted(set(obj) - set(allowed))
    if unknown:
        raise SchemaError(f"{name} contains unknown field(s): {', '.join(unknown)}")
    missing = [k for k in required if k not in obj]
    if missing:
        raise SchemaError(f"{name} missing required field(s): {', '.join(missing)}")
    for key, expected in allowed.items():
        if key not in obj:
            continue
        if not isinstance(obj[key], expected):
            raise SchemaError(f"{name}.{key} must be {_type_name(expected)}")
    return obj


def validate_protocol_request(value: Any) -> tuple[Any, str, dict[str, Any]]:
    obj=require_object(value,name='request'); unknown=sorted(set(obj)-{'id','cmd','params'})
    if unknown: raise SchemaError(f"request contains unknown field(s): {', '.join(unknown)}")
    rid=obj.get('id')
    if isinstance(rid,bool) or (rid is not None and not isinstance(rid,(int,str))): raise SchemaError('request.id must be an integer, string, or null')
    if isinstance(rid,str) and len(rid)>128: raise SchemaError('request.id is too long')
    cmd=obj.get('cmd')
    if not isinstance(cmd,str) or not cmd.strip(): raise SchemaError('request.cmd must be a non-empty string')
    cmd=cmd.strip()
    if len(cmd)>128: raise SchemaError('request.cmd is too long')
    params=obj.get('params',{})
    if params is None: params={}
    return rid,cmd,require_object(params,name='request.params')
