# -*- coding: utf-8 -*-
"""Shared helpers for orchestrator stage result views.

The orchestrator stores public tool statuses together with sidecar data such as
``*_detail`` and ``*_canonical``. Downstream consumers should use this module
instead of duplicating suffix filtering rules.
"""

from typing import Any, Iterator, TypedDict


INTERNAL_STAGE_RESULT_SUFFIXES = (
    "_status",
    "_detail",
    "_canonical",
    "_canonical_error",
)


class PublicToolResult(TypedDict, total=False):
    stage: str
    tool: str
    status: str
    detail: dict[str, Any]


def is_internal_stage_result_key(key: str) -> bool:
    """Return True for stage result sidecar keys."""
    return key.endswith(INTERNAL_STAGE_RESULT_SUFFIXES)


def iter_public_tool_results(stage_results: dict) -> Iterator[PublicToolResult]:
    """Yield public tool status entries from an orchestrator stage result map."""
    for stage_name, stage_data in stage_results.items():
        if not isinstance(stage_data, dict):
            continue
        tools = stage_data.get("tools", {})
        if not isinstance(tools, dict):
            continue

        for key, val in tools.items():
            if not isinstance(key, str):
                continue
            if is_internal_stage_result_key(key):
                continue
            if not isinstance(val, str):
                continue

            detail = tools.get(f"{key}_detail", {})
            yield PublicToolResult(
                stage=stage_name,
                tool=key,
                status=val,
                detail=detail if isinstance(detail, dict) else {},
            )
