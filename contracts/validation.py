# -*- coding: utf-8 -*-
"""Tool Contract v1 validation."""

from contracts.tool_contract import ToolContract, AdapterType


def validate_contract(tc: ToolContract) -> list[str]:
    """Validate a ToolContract and return a list of error messages.

    Returns an empty list if the contract is valid.
    """
    errors = []

    if not tc.tool:
        errors.append("tool name is required")
    if not tc.adapter_type:
        errors.append("adapter.type is required")
    if tc.adapter_type not in _VALID_ADAPTER_TYPES:
        errors.append(
            f"Unknown adapter.type: {tc.adapter_type!r}. "
            f"Must be one of: {_VALID_ADAPTER_TYPES}"
        )

    # CLI adapters need execution config
    if tc.adapter_type == "cli_json":
        if tc.execution is None:
            errors.append("execution config is required for cli_json adapter")
        elif not tc.execution.executable:
            errors.append("execution.command.executable is required for cli_json adapter")

    # Async adapters need lifecycle config
    if tc.adapter_type in ("api_async_job", "api_platform"):
        if tc.lifecycle is None:
            errors.append("lifecycle config is required for async adapters")
        else:
            if not tc.lifecycle.submit or not tc.lifecycle.submit.url:
                errors.append("lifecycle.submit.url is required for async adapters")
            if tc.adapter_type == "api_async_job":
                if not tc.lifecycle.submit.job_id_path:
                    errors.append("lifecycle.submit.response.job_id_path is required for api_async_job")

    # Normalization config
    if tc.normalization:
        if not tc.normalization.format:
            errors.append("normalization.format is required")
        if not tc.normalization.normalizer:
            errors.append("normalization.normalizer is required")

    return errors


_VALID_ADAPTER_TYPES: set[str] = {
    "cli_json",
    "api_async_job",
    "api_platform",
    "api_issues",
    "api_crash_stats",
    "wrapper",
}
