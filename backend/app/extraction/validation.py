"""Partial validation: keep everything valid in an LLM payload and drop only what is not."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, cast

from pydantic import BaseModel, ValidationError

MAX_ROUNDS = 100


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str
    action: str


def format_errors(error: ValidationError, limit: int = 30) -> str:
    lines = [f"- {'.'.join(str(p) for p in e['loc']) or '<root>'}: {e['msg']}" for e in error.errors()[:limit]]
    if error.error_count() > limit:
        lines.append(f"- ... and {error.error_count() - limit} more")
    return "\n".join(lines)


def _existing_path(data: Any, loc: tuple[str | int, ...]) -> list[str | int]:
    """The longest prefix of `loc` that actually exists in `data` (skipping Pydantic union tags)."""
    path: list[str | int] = []
    node = data
    for part in loc:
        if (isinstance(node, dict) and isinstance(part, str) and part in node) or (
            isinstance(node, list) and isinstance(part, int) and 0 <= part < len(node)
        ):
            node = cast(Any, node)[part]
        else:
            continue
        path.append(part)
    return path


def _remove(data: Any, path: list[str | int]) -> None:
    parent = data
    for part in path[:-1]:
        parent = parent[part]
    del parent[path[-1]]


def validate_partially[M: BaseModel](
    model_cls: type[M], data: dict[str, Any]
) -> tuple[M | None, list[ValidationIssue]]:
    """Validate, removing one offending element per round until the payload is valid.

    Invalid optional fields are deleted (their default applies); list items that cannot be fixed are dropped.
    Returns (None, issues) when a required top-level field cannot be recovered.
    """
    payload = copy.deepcopy(data)
    issues: list[ValidationIssue] = []
    for _ in range(MAX_ROUNDS):
        try:
            return model_cls.model_validate(payload), issues
        except ValidationError as exc:
            error = exc.errors()[0]
            loc = tuple(error["loc"])
            # Remove the deepest element of the error path that exists. For a missing required field (or an
            # object-level validator error) that is the enclosing object; a removed required field surfaces as
            # "missing" on the next round, which then drops its enclosing object.
            target = _existing_path(payload, loc)
            if not target:
                issues.append(ValidationIssue(".".join(map(str, loc)), error["msg"], "unrecoverable"))
                return None, issues
            action = "dropped item" if isinstance(target[-1], int) else "dropped field"
            issues.append(ValidationIssue(".".join(map(str, target)), error["msg"], action))
            _remove(payload, target)
    return None, issues
